#!/usr/bin/env python3
"""Elect Twin Rooms server (pure Python standard-library implementation).

Implements deterministic coordination rooms for humans and authorized Twins:
- Loopback-only binding (127.0.0.1)
- Bearer token authentication per local identity (Jay and Alex test personas)
- Deterministic worker jobs with state tracking
- Isolated private notebooks per identity
- SQLite persistence
- JSON startup handshake on stdout: {"ready": true, "urls": {...}}
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import time
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

PERSONAS = {
    "jay": {"id": "jay", "name": "Jay", "twin": "jay-twin", "twin_name": "Jay Twin"},
    "alex": {"id": "alex", "name": "Alex", "twin": "alex-twin", "twin_name": "Alex Twin"},
}

AGENTS = {
    "jay-twin": {"id": "jay-twin", "name": "Jay Twin", "owner": "jay"},
    "alex-twin": {"id": "alex-twin", "name": "Alex Twin", "owner": "alex"},
}

def resolve_db_path(custom_data=None):
    if custom_data:
        return Path(custom_data).resolve()
    if sys.platform == "darwin":
        home = Path(os.environ.get("HOME", "~")).expanduser()
        base = home / "Library" / "Application Support" / "Elect Twin Rooms"
    elif sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = Path(local_app_data) / "ElectTwinRooms" if local_app_data else Path.home() / "AppData" / "Local" / "ElectTwinRooms"
    else:
        home = Path(os.environ.get("HOME", "~")).expanduser()
        base = home / ".electri-rooms"
    base.mkdir(parents=True, exist_ok=True)
    return base / "rooms.sqlite3"

class Database:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def get_connection(self):
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        with self.get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS rooms (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    parent TEXT,
                    closed INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS members (
                    room_id TEXT NOT NULL,
                    person_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    PRIMARY KEY (room_id, person_id)
                );
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    room_id TEXT NOT NULL,
                    author TEXT NOT NULL,
                    author_name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    text TEXT NOT NULL,
                    time REAL NOT NULL,
                    nonce TEXT,
                    prev_hash TEXT,
                    hash TEXT
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    room_id TEXT NOT NULL,
                    agent TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT,
                    trigger_event_id TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS policies (
                    room_id TEXT NOT NULL,
                    agent TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    topics TEXT NOT NULL DEFAULT '[]',
                    mentions INTEGER NOT NULL DEFAULT 1,
                    max_runs INTEGER NOT NULL DEFAULT 10,
                    remaining_runs INTEGER NOT NULL DEFAULT 10,
                    tool_limit INTEGER NOT NULL DEFAULT 10,
                    tool_used INTEGER NOT NULL DEFAULT 0,
                    tools TEXT NOT NULL DEFAULT '[]',
                    PRIMARY KEY (room_id, agent)
                );
                CREATE TABLE IF NOT EXISTS private_notes (
                    person_id TEXT PRIMARY KEY,
                    text TEXT NOT NULL DEFAULT '',
                    updated_at REAL NOT NULL
                );
            """)

            # Seed initial room if empty
            cursor = conn.execute("SELECT COUNT(*) FROM rooms")
            if cursor.fetchone()[0] == 0:
                now = time.time()
                conn.execute(
                    "INSERT INTO rooms (id, name, parent, closed, created_at) VALUES (?, ?, ?, ?, ?)",
                    ("planning", "Shared Planning", None, 0, now)
                )
                conn.execute(
                    "INSERT INTO members (room_id, person_id, role) VALUES (?, ?, ?)",
                    ("planning", "jay", "admin")
                )
                conn.execute(
                    "INSERT INTO members (room_id, person_id, role) VALUES (?, ?, ?)",
                    ("planning", "alex", "write")
                )
                # Seed agent policies
                for agent_id in ("jay-twin", "alex-twin"):
                    conn.execute(
                        """INSERT INTO policies
                           (room_id, agent, enabled, topics, mentions, max_runs, remaining_runs, tool_limit, tool_used, tools)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        ("planning", agent_id, 0, "[]", 1, 10, 10, 10, 0, "[]")
                    )
                # Seed welcome event
                ev_id = "ev_seed_1"
                conn.execute(
                    """INSERT INTO events
                       (id, room_id, author, author_name, kind, text, time, nonce, prev_hash, hash)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (ev_id, "planning", "jay", "Jay", "message", "Welcome to our shared planning room.", now, None, "0", "seed")
                )
            conn.commit()


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def make_handler(db, tokens, manual_mode=False, web_dir=None):
    token_to_identity = {v: k for k, v in tokens.items()}

    class RoomsHandler(BaseHTTPRequestHandler):
        server_version = "ElectTwinRooms/0.3.0"

        def log_message(self, format, *args):
            # Suppress normal request logging to keep stdout clean for JSON handshake
            pass

        def _send_json(self, status, data):
            payload = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def _send_error(self, status, message):
            self._send_json(status, {"error": message})

        def _authenticate(self):
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                return None
            token = auth[7:].strip()
            return token_to_identity.get(token)

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path

            if path in ("", "/", "/index.html"):
                self._serve_index()
                return

            if not path.startswith("/api/"):
                self._send_error(404, "Not found")
                return

            identity = self._authenticate()
            if not identity:
                self._send_error(401, "Unauthorized")
                return

            subpath = path[5:]
            if subpath == "state":
                self._handle_state(identity)
            elif subpath == "room":
                query = urllib.parse.parse_qs(parsed.query)
                room_id = query.get("id", [None])[0]
                if not room_id:
                    self._send_error(400, "Missing room id")
                    return
                self._handle_room_detail(identity, room_id)
            elif subpath == "private":
                self._handle_get_private(identity)
            else:
                self._send_error(404, "Unknown endpoint")

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path

            if not path.startswith("/api/"):
                self._send_error(404, "Not found")
                return

            identity = self._authenticate()
            if not identity:
                self._send_error(401, "Unauthorized")
                return

            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
            except Exception as e:
                self._send_error(400, f"Malformed JSON: {e}")
                return

            subpath = path[5:]
            if subpath == "policy":
                self._handle_policy(identity, body)
            elif subpath == "message":
                self._handle_message(identity, body)
            elif subpath == "private":
                self._handle_set_private(identity, body)
            elif subpath == "room":
                self._handle_create_room(identity, body)
            elif subpath == "member":
                self._handle_member(identity, body)
            elif subpath == "handoff":
                self._handle_handoff(identity, body)
            elif subpath == "close":
                self._handle_close_room(identity, body)
            else:
                self._send_error(404, "Unknown endpoint")

        def _serve_index(self):
            # Try loading external index.html if web_dir provided
            if web_dir and (Path(web_dir) / "index.html").exists():
                content = (Path(web_dir) / "index.html").read_bytes()
            else:
                content = b"<!doctype html><html><body><h1>Elect Twin Rooms</h1></body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def _handle_state(self, identity):
            with db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT r.id, r.name, r.parent, r.closed, m.role
                    FROM rooms r
                    JOIN members m ON r.id = m.room_id
                    WHERE m.person_id = ?
                    ORDER BY r.created_at ASC
                """, (identity,))
                rooms = [dict(row) for row in cursor.fetchall()]

            people = [{"id": p["id"], "name": p["name"]} for p in PERSONAS.values()]
            self._send_json(200, {
                "me": {"id": identity, "name": PERSONAS[identity]["name"]},
                "rooms": rooms,
                "people": people,
            })

        def _handle_room_detail(self, identity, room_id):
            with db.get_connection() as conn:
                # Check membership
                cursor = conn.execute("""
                    SELECT r.id, r.name, r.parent, r.closed, m.role
                    FROM rooms r
                    JOIN members m ON r.id = m.room_id
                    WHERE r.id = ? AND m.person_id = ?
                """, (room_id, identity))
                room_row = cursor.fetchone()
                if not room_row:
                    self._send_error(403, "Not a member of this room")
                    return

                # Get all members
                cursor = conn.execute("SELECT person_id, role FROM members WHERE room_id = ?", (room_id,))
                members = {row["person_id"]: row["role"] for row in cursor.fetchall()}
                room_dict = dict(room_row)
                room_dict["members"] = members

                # Get policies / agents for this room
                cursor = conn.execute("SELECT * FROM policies WHERE room_id = ?", (room_id,))
                policies_rows = cursor.fetchall()
                policies = {row["agent"]: dict(row) for row in policies_rows}

                agents_list = []
                for agent_id, agent_meta in AGENTS.items():
                    pol = policies.get(agent_id, {})
                    topics_json = pol.get("topics", "[]")
                    tools_json = pol.get("tools", "[]")
                    try:
                        topics = json.loads(topics_json)
                    except:
                        topics = []
                    try:
                        tools = json.loads(tools_json)
                    except:
                        tools = []
                    agents_list.append({
                        "id": agent_id,
                        "name": agent_meta["name"],
                        "owner": agent_meta["owner"],
                        "enabled": bool(pol.get("enabled", 0)),
                        "status": "idle",
                        "topics": topics,
                        "mentions": bool(pol.get("mentions", 1)),
                        "remaining_runs": pol.get("remaining_runs", 10),
                        "max_runs": pol.get("max_runs", 10),
                        "tool_used": pol.get("tool_used", 0),
                        "tool_limit": pol.get("tool_limit", 10),
                        "tools": tools,
                    })

                # Get events
                cursor = conn.execute("""
                    SELECT id, author, author_name, kind, text, time
                    FROM events
                    WHERE room_id = ?
                    ORDER BY time ASC
                """, (room_id,))
                events = [dict(row) for row in cursor.fetchall()]

                # Get jobs
                cursor = conn.execute("""
                    SELECT id, agent, agent_name, status, reason
                    FROM jobs
                    WHERE room_id = ?
                    ORDER BY created_at ASC
                """, (room_id,))
                jobs = [dict(row) for row in cursor.fetchall()]

            self._send_json(200, {
                "room": room_dict,
                "agents": agents_list,
                "events": events,
                "jobs": jobs,
            })

        def _handle_policy(self, identity, body):
            room_id = body.get("room")
            agent_id = body.get("agent")
            if not room_id or not agent_id:
                self._send_error(400, "Missing room or agent")
                return

            agent_meta = AGENTS.get(agent_id)
            if not agent_meta:
                self._send_error(404, "Agent not found")
                return

            # Owner authorization check: only the agent's owner can set its policy!
            if agent_meta["owner"] != identity:
                self._send_error(403, "Only the owner can configure their Twin's policy")
                return

            enabled = 1 if body.get("enabled") else 0
            mentions = 1 if body.get("mentions", True) else 0
            topics = json.dumps(body.get("topics", []))
            max_runs = int(body.get("max_runs", 10))
            remaining_runs = int(body.get("remaining_runs", max_runs))
            tool_limit = int(body.get("tool_limit", 10))
            tools = json.dumps(body.get("tools", []))

            with db.get_connection() as conn:
                conn.execute("""
                    INSERT INTO policies (room_id, agent, enabled, topics, mentions, max_runs, remaining_runs, tool_limit, tool_used, tools)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                    ON CONFLICT(room_id, agent) DO UPDATE SET
                        enabled = excluded.enabled,
                        topics = excluded.topics,
                        mentions = excluded.mentions,
                        max_runs = excluded.max_runs,
                        remaining_runs = excluded.remaining_runs,
                        tool_limit = excluded.tool_limit,
                        tools = excluded.tools
                """, (room_id, agent_id, enabled, topics, mentions, max_runs, remaining_runs, tool_limit, tools))
                conn.commit()

            self._send_json(200, {"ok": True})

        def _handle_message(self, identity, body):
            room_id = body.get("room")
            text = (body.get("text") or "").strip()
            nonce = body.get("nonce")

            if not room_id or not text:
                self._send_error(400, "Missing room or text")
                return

            with db.get_connection() as conn:
                # Check user write permission in room
                cursor = conn.execute("SELECT role FROM members WHERE room_id = ? AND person_id = ?", (room_id, identity))
                row = cursor.fetchone()
                if not row or row["role"] not in ("admin", "write"):
                    self._send_error(403, "Write permission required")
                    return

                # Idempotency check with nonce
                if nonce:
                    cursor = conn.execute("SELECT id FROM events WHERE room_id = ? AND author = ? AND nonce = ?", (room_id, identity, nonce))
                    existing = cursor.fetchone()
                    if existing:
                        self._send_json(200, {"ok": True, "event_id": existing["id"], "idempotent": True})
                        return

                now = time.time()
                ev_id = "ev_" + secrets.token_hex(6)
                author_name = PERSONAS[identity]["name"]

                # Hash chaining
                cursor = conn.execute("SELECT hash FROM events WHERE room_id = ? ORDER BY time DESC LIMIT 1", (room_id,))
                last_hash_row = cursor.fetchone()
                prev_hash = last_hash_row["hash"] if last_hash_row else "0"
                curr_hash = hashlib.sha256(f"{prev_hash}:{ev_id}:{text}".encode()).hexdigest()[:16]

                conn.execute("""
                    INSERT INTO events (id, room_id, author, author_name, kind, text, time, nonce, prev_hash, hash)
                    VALUES (?, ?, ?, ?, 'message', ?, ?, ?, ?, ?)
                """, (ev_id, room_id, identity, author_name, text, now, nonce, prev_hash, curr_hash))

                # Check triggered agents in this room
                cursor = conn.execute("SELECT * FROM policies WHERE room_id = ? AND enabled = 1", (room_id,))
                active_policies = cursor.fetchall()

                for pol in active_policies:
                    agent_id = pol["agent"]
                    agent_meta = AGENTS.get(agent_id)
                    if not agent_meta:
                        continue

                    # Check mention or topic
                    is_mentioned = pol["mentions"] and (f"@{agent_id}".lower() in text.lower())
                    topics = []
                    try:
                        topics = json.loads(pol["topics"])
                    except:
                        pass
                    has_topic = any(topic.lower() in text.lower() for topic in topics if topic)

                    if not (is_mentioned or has_topic):
                        continue

                    remaining_runs = pol["remaining_runs"]
                    if remaining_runs <= 0:
                        continue

                    # Trigger worker job
                    job_id = "job_" + secrets.token_hex(6)
                    agent_name = agent_meta["name"]

                    if manual_mode:
                        conn.execute("""
                            INSERT INTO jobs (id, room_id, agent, agent_name, status, reason, trigger_event_id, created_at, updated_at)
                            VALUES (?, ?, ?, ?, 'queued', 'Manual mode queued', ?, ?, ?)
                        """, (job_id, room_id, agent_id, agent_name, ev_id, now, now))
                    else:
                        # Deterministic execution
                        tool_used = pol["tool_used"] + 1
                        remaining_runs = remaining_runs - 1
                        conn.execute("""
                            UPDATE policies
                            SET remaining_runs = ?, tool_used = ?
                            WHERE room_id = ? AND agent = ?
                        """, (remaining_runs, tool_used, room_id, agent_id))

                        conn.execute("""
                            INSERT INTO jobs (id, room_id, agent, agent_name, status, reason, trigger_event_id, created_at, updated_at)
                            VALUES (?, ?, ?, ?, 'complete', 'Deterministic digest completed', ?, ?, ?)
                        """, (job_id, room_id, agent_id, agent_name, ev_id, now, now))

                        # Generate deterministic response event
                        resp_ev_id = "ev_" + secrets.token_hex(6)
                        resp_now = time.time()
                        resp_text = (
                            f"[Deterministic context digest from {agent_name}]: "
                            f"Received request '{text}'. Processed room context. "
                            f"Remaining runs: {remaining_runs}. Deterministic worker completed."
                        )
                        resp_hash = hashlib.sha256(f"{curr_hash}:{resp_ev_id}:{resp_text}".encode()).hexdigest()[:16]

                        conn.execute("""
                            INSERT INTO events (id, room_id, author, author_name, kind, text, time, nonce, prev_hash, hash)
                            VALUES (?, ?, ?, ?, 'agent', ?, ?, NULL, ?, ?)
                        """, (resp_ev_id, room_id, agent_id, agent_name, resp_text, resp_now, curr_hash, resp_hash))

                conn.commit()

            self._send_json(200, {"ok": True, "event_id": ev_id})

        def _handle_get_private(self, identity):
            with db.get_connection() as conn:
                cursor = conn.execute("SELECT text FROM private_notes WHERE person_id = ?", (identity,))
                row = cursor.fetchone()
                text = row["text"] if row else ""
            self._send_json(200, {"text": text})

        def _handle_set_private(self, identity, body):
            text = body.get("text", "")
            now = time.time()
            with db.get_connection() as conn:
                conn.execute("""
                    INSERT INTO private_notes (person_id, text, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(person_id) DO UPDATE SET text = excluded.text, updated_at = excluded.updated_at
                """, (identity, text, now))
                conn.commit()
            self._send_json(200, {"ok": True})

        def _handle_create_room(self, identity, body):
            name = (body.get("name") or "").strip()
            parent = body.get("parent")
            if not name:
                self._send_error(400, "Missing room name")
                return

            new_id = "room_" + secrets.token_hex(6)
            now = time.time()
            with db.get_connection() as conn:
                conn.execute(
                    "INSERT INTO rooms (id, name, parent, closed, created_at) VALUES (?, ?, ?, 0, ?)",
                    (new_id, name, parent, now)
                )
                conn.execute(
                    "INSERT INTO members (room_id, person_id, role) VALUES (?, ?, 'admin')",
                    (new_id, identity)
                )
                for agent_id in AGENTS:
                    conn.execute("""
                        INSERT INTO policies (room_id, agent, enabled, topics, mentions, max_runs, remaining_runs, tool_limit, tool_used, tools)
                        VALUES (?, ?, 0, '[]', 1, 10, 10, 10, 0, '[]')
                    """, (new_id, agent_id))
                conn.commit()

            self._send_json(200, {"ok": True, "id": new_id, "room": {"id": new_id, "name": name, "parent": parent}})

        def _handle_member(self, identity, body):
            room_id = body.get("room")
            person_id = body.get("person")
            role = body.get("role")

            if not room_id or not person_id or not role:
                self._send_error(400, "Missing fields")
                return

            with db.get_connection() as conn:
                cursor = conn.execute("SELECT role FROM members WHERE room_id = ? AND person_id = ?", (room_id, identity))
                row = cursor.fetchone()
                if not row or row["role"] != "admin":
                    self._send_error(403, "Admin permission required to manage members")
                    return

                if role == "remove":
                    conn.execute("DELETE FROM members WHERE room_id = ? AND person_id = ?", (room_id, person_id))
                else:
                    conn.execute("""
                        INSERT INTO members (room_id, person_id, role)
                        VALUES (?, ?, ?)
                        ON CONFLICT(room_id, person_id) DO UPDATE SET role = excluded.role
                    """, (room_id, person_id, role))
                conn.commit()

            self._send_json(200, {"ok": True})

        def _handle_handoff(self, identity, body):
            room_id = body.get("room")
            text = body.get("text", "")
            if not room_id or not text:
                self._send_error(400, "Missing room or text")
                return

            with db.get_connection() as conn:
                cursor = conn.execute("SELECT parent FROM rooms WHERE id = ?", (room_id,))
                r = cursor.fetchone()
                if not r or not r["parent"]:
                    self._send_error(400, "Room has no parent")
                    return
                parent_id = r["parent"]

                # User must have write permission in both rooms
                cursor = conn.execute("SELECT role FROM members WHERE room_id = ? AND person_id = ?", (room_id, identity))
                r1 = cursor.fetchone()
                cursor = conn.execute("SELECT role FROM members WHERE room_id = ? AND person_id = ?", (parent_id, identity))
                r2 = cursor.fetchone()

                if not r1 or r1["role"] not in ("admin", "write") or not r2 or r2["role"] not in ("admin", "write"):
                    self._send_error(403, "Write permission required in both subgroup and parent room")
                    return

                now = time.time()
                ev_id = "ev_" + secrets.token_hex(6)
                author_name = PERSONAS[identity]["name"]
                handoff_text = f"[Handoff from subgroup]: {text}"

                conn.execute("""
                    INSERT INTO events (id, room_id, author, author_name, kind, text, time, nonce, prev_hash, hash)
                    VALUES (?, ?, ?, ?, 'handoff', ?, ?, NULL, '0', 'handoff')
                """, (ev_id, parent_id, identity, author_name, handoff_text, now))
                conn.commit()

            self._send_json(200, {"ok": True})

        def _handle_close_room(self, identity, body):
            room_id = body.get("room")
            if not room_id:
                self._send_error(400, "Missing room")
                return

            with db.get_connection() as conn:
                cursor = conn.execute("SELECT role FROM members WHERE room_id = ? AND person_id = ?", (room_id, identity))
                row = cursor.fetchone()
                if not row or row["role"] != "admin":
                    self._send_error(403, "Admin permission required to close room")
                    return

                conn.execute("UPDATE rooms SET closed = 1 WHERE id = ?", (room_id,))
                conn.commit()

            self._send_json(200, {"ok": True})

    return RoomsHandler


def main():
    parser = argparse.ArgumentParser(description="Elect Twin Rooms server")
    parser.add_argument("--port", type=int, default=4334, help="Port to bind (0 for ephemeral)")
    parser.add_argument("--data", type=str, default=None, help="Path to rooms SQLite database")
    parser.add_argument("--manual", action="store_true", help="Manual worker execution mode")
    args = parser.parse_args()

    db_path = resolve_db_path(args.data)
    db = Database(db_path)

    tokens = {
        "jay": secrets.token_hex(16),
        "alex": secrets.token_hex(16),
    }

    # Locate web assets if bundled
    web_dir = None
    candidate_web = Path(__file__).resolve().parent / "web"
    if candidate_web.exists():
        web_dir = candidate_web

    handler_class = make_handler(db, tokens, manual_mode=args.manual, web_dir=web_dir)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_class)
    actual_port = server.server_address[1]

    urls = {
        "jay": f"http://127.0.0.1:{actual_port}/#token={tokens['jay']}",
        "alex": f"http://127.0.0.1:{actual_port}/#token={tokens['alex']}",
    }

    ready_line = json.dumps({"ready": True, "port": actual_port, "urls": urls})
    print(ready_line, flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == "__main__":
    main()
