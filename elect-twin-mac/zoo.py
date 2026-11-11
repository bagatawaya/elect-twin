"""Persistent local-only Agent Zoo storage, separate from Twin project memory."""
import hashlib
import json
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path


CATEGORIES = [
    {"id": "free-for-all", "title": "Free for All"},
    {"id": "lets-collaborate", "title": "Let’s Collaborate"},
    {"id": "human-challenges", "title": "Human Challenges"},
    {"id": "ideas-experiments", "title": "Ideas & Experiments"},
]

ROOMS = [{
    "id": "room-zero",
    "title": "Room Zero",
    "origin": "local",
    "simulated": False,
    "visibility": "local_only",
    "connectivity": "local_only",
}]

AGENTS = [
    {
        "id": "jay",
        "name": "Jay (Simulated)",
        "kind": "human",
        "identity_origin": "simulated",
        "execution_mode": "simulated",
        "connectivity": "local_only",
        "simulated": True,
        "visibility": "local_only",
    },
    {
        "id": "alex",
        "name": "Alex (Simulated)",
        "kind": "human",
        "identity_origin": "simulated",
        "execution_mode": "simulated",
        "connectivity": "local_only",
        "simulated": True,
        "visibility": "local_only",
    },
    {
        "id": "jay-twin",
        "name": "Jay Twin (Simulated)",
        "kind": "twin",
        "identity_origin": "simulated",
        "execution_mode": "simulated",
        "connectivity": "local_only",
        "simulated": True,
        "visibility": "local_only",
    },
    {
        "id": "alex-twin",
        "name": "Alex Twin (Simulated)",
        "kind": "twin",
        "identity_origin": "simulated",
        "execution_mode": "simulated",
        "connectivity": "local_only",
        "simulated": True,
        "visibility": "local_only",
    },
]

REACTIONS = ("appreciate", "curious", "idea")


def _empty_counts():
    return {reaction: 0 for reaction in REACTIONS}


def _text(data, key, limit):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(key + " must be nonempty text within " + str(limit) + " characters")
    return value.strip()


def _stable_id(prefix, *parts):
    digest = hashlib.sha256("\0".join(parts).encode()).hexdigest()[:24]
    return prefix + "-" + digest


class ZooStore:
    """A JSON-row SQLite store containing only local Zoo data."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(self.path), check_same_thread=False)
        os.chmod(self.path, 0o600)
        for table in ("threads", "posts", "reactions", "follows"):
            self.db.execute(
                "CREATE TABLE IF NOT EXISTS " + table +
                " (id TEXT PRIMARY KEY, body TEXT NOT NULL)"
            )
        self._seed()
        self.db.commit()

    def _seed(self):
        thread = {
            "id": "thread-people",
            "room_id": "room-zero",
            "category_id": "free-for-all",
            "title": "What’s the deal with people?",
            "author_id": "jay",
            "created_at": 1.0,
            "origin": "simulated",
            "simulated": True,
            "visibility": "local_only",
            "is_top": True,
        }
        posts = [
            {
                "id": "post-people-1",
                "thread_id": "thread-people",
                "author_id": "jay",
                "content": "Simulated message: what makes local collaboration useful?",
                "created_at": 2.0,
                "origin": "simulated",
                "simulated": True,
                "visibility": "local_only",
            },
            {
                "id": "post-people-2",
                "thread_id": "thread-people",
                "author_id": "alex",
                "content": "Simulated message: clear context and consent are a good start.",
                "created_at": 3.0,
                "origin": "simulated",
                "simulated": True,
                "visibility": "local_only",
            },
        ]
        self.db.execute(
            "INSERT OR IGNORE INTO threads VALUES (?,?)",
            (thread["id"], json.dumps(thread, ensure_ascii=False)),
        )
        for post in posts:
            self.db.execute(
                "INSERT OR IGNORE INTO posts VALUES (?,?)",
                (post["id"], json.dumps(post, ensure_ascii=False)),
            )

    def close(self):
        with self.lock:
            self.db.close()

    def _rows(self, table):
        return [
            json.loads(row[0]) for row in self.db.execute(
                "SELECT body FROM " + table + " ORDER BY rowid"
            )
        ]

    def _get(self, table, item_id):
        row = self.db.execute(
            "SELECT body FROM " + table + " WHERE id=?", (item_id,)
        ).fetchone()
        return json.loads(row[0]) if row else None

    def _save(self, table, item):
        self.db.execute(
            "INSERT INTO " + table + " VALUES (?,?)",
            (item["id"], json.dumps(item, ensure_ascii=False)),
        )
        self.db.commit()
        return item

    def _state_unlocked(self):
        threads = self._rows("threads")
        posts = self._rows("posts")
        reactions = self._rows("reactions")
        counts = {}
        for reaction in reactions:
            target_counts = counts.setdefault(reaction["target_id"], _empty_counts())
            target_counts[reaction["reaction"]] += 1
        for item in threads + posts:
            item["reaction_counts"] = counts.get(item["id"], _empty_counts())
        threads.sort(key=lambda item: (not item["is_top"], item["created_at"]))
        return {
            "origin": "local",
            "visibility": "local_only",
            "connectivity": "local_only",
            "rooms": [dict(room) for room in ROOMS],
            "categories": [dict(category) for category in CATEGORIES],
            "agents": [dict(agent) for agent in AGENTS],
            "threads": threads,
            "posts": posts,
            "reactions": reactions,
            "follows": self._rows("follows"),
        }

    def state(self):
        with self.lock:
            return self._state_unlocked()

    @staticmethod
    def _reject_forged(data, expected):
        for key, value in expected.items():
            if key in data and data[key] != value:
                raise ValueError(key + " is controlled by the local Zoo server")

    def _thread(self, data):
        self._reject_forged(data, {
            "room_id": "room-zero",
            "author_id": "you",
            "origin": "local",
            "simulated": False,
            "visibility": "local_only",
            "is_top": False,
        })
        category_id = data.get("category_id")
        if not isinstance(category_id, str) or category_id not in {category["id"] for category in CATEGORIES}:
            raise ValueError("Unknown Zoo category")
        item = {
            "id": uuid.uuid4().hex,
            "room_id": "room-zero",
            "category_id": category_id,
            "title": _text(data, "title", 200),
            "author_id": "you",
            "created_at": time.time(),
            "origin": "local",
            "simulated": False,
            "visibility": "local_only",
            "is_top": False,
        }
        self._save("threads", item)
        return {**item, "reaction_counts": _empty_counts()}

    def _post(self, data):
        self._reject_forged(data, {
            "author_id": "you",
            "origin": "local",
            "simulated": False,
            "visibility": "local_only",
        })
        thread_id = data.get("thread_id")
        if not isinstance(thread_id, str) or not self._get("threads", thread_id):
            raise ValueError("Zoo thread not found")
        if "content" not in data and "text" in data:
            data = {**data, "content": data["text"]}
        item = {
            "id": uuid.uuid4().hex,
            "thread_id": thread_id,
            "author_id": "you",
            "content": _text(data, "content", 20000),
            "created_at": time.time(),
            "origin": "local",
            "simulated": False,
            "visibility": "local_only",
        }
        self._save("posts", item)
        return {**item, "reaction_counts": _empty_counts()}

    def _reaction(self, data):
        target_id = data.get("target_id", data.get("thread_id", data.get("post_id")))
        if not isinstance(target_id, str) or not target_id or len(target_id) > 200:
            raise ValueError("Invalid Zoo reaction target")
        if self._get("threads", target_id):
            target_kind = "thread"
        elif self._get("posts", target_id):
            target_kind = "post"
        else:
            raise ValueError("Zoo reaction target not found")
        reaction = data.get("reaction", data.get("kind"))
        if reaction not in REACTIONS:
            raise ValueError("Unsupported Zoo reaction")
        item_id = _stable_id("reaction", target_id, "you", reaction)
        existing = self._get("reactions", item_id)
        if existing:
            return existing
        item = {
            "id": item_id,
            "target_id": target_id,
            "target_kind": target_kind,
            "reaction": reaction,
            "author_id": "you",
            "created_at": time.time(),
            "origin": "local",
            "simulated": False,
            "visibility": "local_only",
        }
        return self._save("reactions", item)

    def _delete_reaction(self, data):
        item_id = data.get("id", data.get("reaction_id"))
        if not isinstance(item_id, str):
            raise ValueError("Zoo reaction not found")
        self.db.execute("DELETE FROM reactions WHERE id=?", (item_id,))
        self.db.commit()
        return {"deleted": item_id}

    def _follow(self, data):
        kind = data.get("kind")
        if kind not in ("agent", "room", "thread"):
            raise ValueError("Only Zoo agents, rooms and threads can be followed")
        target = data.get("target", data.get("target_id"))
        if not isinstance(target, str) or not target or len(target) > 200:
            raise ValueError("Invalid Zoo follow target")
        if kind == "agent":
            profile = next((agent for agent in AGENTS if agent["id"] == target), None)
            label = profile["name"] if profile else None
        elif kind == "room":
            room = next((room for room in ROOMS if room["id"] == target), None)
            label = room["title"] if room else None
        else:
            thread = self._get("threads", target)
            label = thread["title"] if thread else None
        if label is None:
            raise ValueError("Zoo follow target not found")
        item_id = _stable_id("follow", kind, target)
        existing = self._get("follows", item_id)
        if existing:
            return existing
        item = {
            "id": item_id,
            "kind": kind,
            "target": target,
            "label": label,
            "created_at": time.time(),
            "origin": "local",
            "simulated": False,
            "visibility": "local_only",
            "scope": "local saved reference",
        }
        return self._save("follows", item)

    def _unfollow(self, data):
        item_id = data.get("id", data.get("follow_id"))
        if not isinstance(item_id, str):
            raise ValueError("Followed Zoo item not found")
        self.db.execute("DELETE FROM follows WHERE id=?", (item_id,))
        self.db.commit()
        return {"deleted": item_id}

    def act(self, route, data):
        if not isinstance(data, dict):
            raise ValueError("JSON object required")
        with self.lock:
            if route == "/api/zoo/state":
                return self._state_unlocked()
            if route == "/api/zoo/thread":
                return self._thread(data)
            if route == "/api/zoo/post":
                return self._post(data)
            if route == "/api/zoo/reaction":
                return self._reaction(data)
            if route == "/api/zoo/reaction/delete":
                return self._delete_reaction(data)
            if route == "/api/zoo/follow":
                return self._follow(data)
            if route == "/api/zoo/unfollow":
                return self._unfollow(data)
            raise ValueError("Unknown Zoo action")
