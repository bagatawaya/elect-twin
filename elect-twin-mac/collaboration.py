"""Persistent, local-only onboarding collaboration preview records."""
import json
import time
import uuid


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
