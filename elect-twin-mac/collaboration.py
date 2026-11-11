"""Persistent, local-only onboarding collaboration preview records and Solo 2-AI Goal Rooms."""
import json
import time
import uuid

SOLO_PRESETS = [
    {
        "id": "visionary-skeptic",
        "title": "🎯 Visionary + Skeptic",
        "tag": "Strategy",
        "desc": "Strategy Designer proposes the plan; Adversarial Challenger stress-tests blind spots and costs.",
        "ai1": {"role": "Strategy Designer", "focus": "Growth, market positioning, high-conviction roadmap"},
        "ai2": {"role": "Adversarial Challenger", "focus": "Unit economics, regulatory pitfalls, failure modes"}
    },
    {
        "id": "writer-showrunner",
        "title": "🎬 Writer + Showrunner",
        "tag": "Creative & Copy",
        "desc": "AI #1 drafts high-converting scripts/hooks; AI #2 ruthlessly edits for retention and pacing.",
        "ai1": {"role": "Script & Copywriter", "focus": "Hook generation, narrative tension, persuasive copy"},
        "ai2": {"role": "Showrunner Editor", "focus": "Cuts fluff, tightens rhythm, punchlines"}
    },
    {
        "id": "architect-redteam",
        "title": "💻 Architect + Red-Teamer",
        "tag": "Code & Specs",
        "desc": "System Architect designs clean implementations; Red-Teamer audits for race conditions and vulnerabilities.",
        "ai1": {"role": "System Architect", "focus": "Modular design, API contracts, schema layout"},
        "ai2": {"role": "Security Red-Teamer", "focus": "Edge cases, race conditions, injection flaws"}
    },
    {
        "id": "sparring-coach",
        "title": "🥊 Sparring Partner + Corner Coach",
        "tag": "Negotiation Prep",
        "desc": "Tough Counterpart roleplays the hardline client; Corner Coach whispers tactical concessions in real-time.",
        "ai1": {"role": "Tough Counterpart", "focus": "Roleplay unyielding investor, customer, or vendor"},
        "ai2": {"role": "Corner Coach", "focus": "Tactical reframing, walk-away boundaries, leverage"}
    }
]


class SoloRoomStore:
    def __init__(self, db):
        self.db = db
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS solo_rooms "
            "(id TEXT PRIMARY KEY, preset_id TEXT NOT NULL, goal TEXT, body TEXT NOT NULL)"
        )
        self.db.commit()

    def list(self):
        return [
            json.loads(row[0])
            for row in self.db.execute("SELECT body FROM solo_rooms ORDER BY rowid DESC")
        ]

    def create(self, data):
        preset_id = data.get("preset_id")
        preset = next((p for p in SOLO_PRESETS if p["id"] == preset_id), None)
        if not preset:
            raise ValueError("Unknown solo preset")
        goal = (data.get("goal") or "").strip() or f"Execute {preset['title']}"
        now = time.time()
        room_id = f"solo-{uuid.uuid4().hex[:8]}"
        item = {
            "id": room_id,
            "preset_id": preset["id"],
            "title": preset["title"],
            "tag": preset["tag"],
            "goal": goal,
            "ai1": preset["ai1"],
            "ai2": preset["ai2"],
            "created_at": now,
            "status": "active",
            "messages": [
                {
                    "author": preset["ai1"]["role"],
                    "kind": "agent",
                    "text": f"Ready to lead {preset['tag']} design for: '{goal}'. Awaiting user prompt or initial thesis.",
                    "time": now
                },
                {
                    "author": preset["ai2"]["role"],
                    "kind": "agent",
                    "text": f"Armed to audit and pressure-test {preset['tag']}. Send your assumptions when ready.",
                    "time": now + 0.1
                }
            ]
        }
        self.db.execute(
            "INSERT INTO solo_rooms VALUES (?,?,?,?)",
            (room_id, preset["id"], goal, json.dumps(item))
        )
        self.db.commit()
        return item


class InvitationStore:
    """Store simulated invitations without delivering or sharing anything."""

    ALLOWED_STATUSES = {
        "draft", "accepted_preview", "declined_preview", "cancelled_preview",
    }
    SHARING_KEYS = {"goal", "documents", "history"}

    def __init__(self, db):
        self.db = db
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS invitation_previews "
            "(id TEXT PRIMARY KEY, body TEXT NOT NULL)"
        )
        self.db.commit()

    def list(self):
        return [
            json.loads(row[0])
            for row in self.db.execute(
                "SELECT body FROM invitation_previews ORDER BY rowid"
            )
        ]

    @staticmethod
    def _text(data, key, limit):
        value = data.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError(
                key + " must be nonempty text within " + str(limit) + " characters"
            )
        return value.strip()

    @staticmethod
    def _target(id):
        if not isinstance(id, str) or not id.strip() or len(id) > 200:
            raise ValueError("Invitation preview target is invalid")
        return id

    def create(self, data, project):
        if not isinstance(data, dict) or not isinstance(project, dict):
            raise ValueError("Invitation preview data and project are required")
        recipient_name = self._text(data, "recipient_name", 200)
        role = self._text(data, "role", 200)
        contact = data.get("contact")
        if contact is None:
            contact = ""
        if not isinstance(contact, str) or len(contact) > 320:
            raise ValueError("contact must be text within 320 characters")
        contact = contact.strip()
        project_id = self._text(project, "id", 200)
        project_name = self._text(project, "name", 200)
        if data.get("project_id") != project_id:
            raise ValueError("project_id must match the selected project")

        sharing = data.get("sharing", {})
        if not isinstance(sharing, dict) or set(sharing) - self.SHARING_KEYS:
            raise ValueError("sharing must contain only goal, documents, and history")
        if any(not isinstance(sharing.get(key, False), bool) for key in self.SHARING_KEYS):
            raise ValueError("sharing choices must be booleans")

        now = time.time()
        item = {
            "id": uuid.uuid4().hex,
            "recipient_name": recipient_name,
            "contact": contact,
            "project_id": project_id,
            "project_name": project_name,
            "role": role,
            "sharing": {key: sharing.get(key, False) for key in ("goal", "documents", "history")},
            "status": "draft",
            "simulated": True,
            "delivery": "not_sent",
            "membership_changed": False,
            "created_at": now,
            "updated_at": now,
        }
        self.db.execute(
            "INSERT INTO invitation_previews VALUES (?,?)",
            (item["id"], json.dumps(item)),
        )
        self.db.commit()
        return item

    def set_status(self, id, status):
        id = self._target(id)
        if not isinstance(status, str) or status not in self.ALLOWED_STATUSES:
            raise ValueError("Invalid invitation preview status")
        row = self.db.execute(
            "SELECT body FROM invitation_previews WHERE id=?", (id,),
        ).fetchone()
        if not row:
            raise ValueError("Invitation preview not found")
        item = json.loads(row[0])
        if item["status"] != "draft" or status == "draft":
            raise ValueError("Only a draft preview can be accepted, declined, or cancelled")
        item["status"] = status
        item["updated_at"] = time.time()
        self.db.execute(
            "UPDATE invitation_previews SET body=? WHERE id=?",
            (json.dumps(item), id),
        )
        self.db.commit()
        return item

    def delete(self, id):
        id = self._target(id)
        cursor = self.db.execute("DELETE FROM invitation_previews WHERE id=?", (id,))
        self.db.commit()
        if not cursor.rowcount:
            raise ValueError("Invitation preview not found")
        return {"deleted": id}
