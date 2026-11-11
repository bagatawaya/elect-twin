"""Offline onboarding and simulated invitation-preview regression tests."""
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import twin


class OnboardingInvitationTests(unittest.TestCase):
    def setUp(self):
        twin.SESSION_KEYS.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "projects.sqlite3"
        self.transport = Mock(return_value=("unused", {}))
        self.network = patch("twin.urlopen").start()
        self.t = twin.Twin(self.path, transport=self.transport)
        self.project = self.t.act("/api/projects", {
            "name": "Collaboration project",
            "goal": "Keep all invitation activity simulated",
        })

    def tearDown(self):
        self.t.zoo.close()
        self.t.db.close()
        patch.stopall()
        self.tmp.cleanup()
        twin.SESSION_KEYS.clear()

    def reopen(self):
        self.t.zoo.close()
        self.t.db.close()
        self.t = twin.Twin(self.path, transport=self.transport)

    def create(self, **overrides):
        data = {
            "recipient_name": "Ada",
            "contact": "",
            "project_id": self.project["id"],
            "role": "Reviewer",
        }
        data.update(overrides)
        return self.t.act("/api/invitation-preview", data)

    def test_onboarding_defaults_persists_skipped_and_completed(self):
        initial = self.t.profile()["onboarding"]
        self.assertEqual(initial, {"status": "not_started", "updated_at": None})

        self.t.act("/api/onboarding", {"status": "skipped"})
        skipped = self.t.profile()["onboarding"]
        self.assertEqual(skipped["status"], "skipped")
        self.assertIsInstance(skipped["updated_at"], float)
        self.reopen()
        self.assertEqual(self.t.profile()["onboarding"], skipped)

        self.t.act("/api/onboarding", {"status": "completed"})
        completed = self.t.profile()["onboarding"]
        self.assertEqual(completed["status"], "completed")
        self.assertGreaterEqual(completed["updated_at"], skipped["updated_at"])
        self.reopen()
        self.assertEqual(self.t.profile()["onboarding"], completed)

    def test_onboarding_rejects_invalid_status_without_changes(self):
        before = self.t.profile()
        for status in ("not_started", "draft", "", "skipped ", None, True, 1, [], {}):
            with self.subTest(status=status):
                with self.assertRaisesRegex(ValueError, "onboarding status"):
                    self.t.act("/api/onboarding", {"status": status})
                self.assertEqual(self.t.profile(), before)

    def test_two_provider_keys_are_independent_and_onboarding_does_not_change_them(self):
        with patch.dict(os.environ, {}, clear=True):
            self.t.act("/api/connect", {"provider": "openai", "key": "fixture-openai-key"})
            self.t.act("/api/connect", {"provider": "anthropic", "key": "fixture-anthropic-key"})
            configured = lambda: {
                row["id"]: row["configured"] for row in self.t.state()["providers"]
            }
            self.assertTrue(configured()["openai"])
            self.assertTrue(configured()["anthropic"])

            self.t.act("/api/onboarding", {"status": "skipped"})
            self.assertEqual(twin.SESSION_KEYS["openai"], "fixture-openai-key")
            self.assertEqual(twin.SESSION_KEYS["anthropic"], "fixture-anthropic-key")

            self.t.act("/api/disconnect", {"provider": "openai"})
            self.assertFalse(configured()["openai"])
            self.assertTrue(configured()["anthropic"])
            self.assertEqual(twin.SESSION_KEYS["anthropic"], "fixture-anthropic-key")
            self.t.act("/api/onboarding", {"status": "completed"})
            self.assertTrue(configured()["anthropic"])

            self.t.act("/api/disconnect", {"provider": "anthropic"})
            self.assertFalse(configured()["anthropic"])
            serialized = json.dumps(self.t.state())
            self.assertNotIn("fixture-openai-key", serialized)
            self.assertNotIn("fixture-anthropic-key", serialized)
            self.assertNotIn(b"fixture-openai-key", self.path.read_bytes())
            self.assertNotIn(b"fixture-anthropic-key", self.path.read_bytes())
        self.transport.assert_not_called()
        self.network.assert_not_called()

    def test_create_has_server_controlled_shape_and_unchecked_sharing_defaults(self):
        item = self.create(
            recipient_name="  Ada Lovelace  ",
            id="forged-id",
            project_name="Forged project",
            status="accepted_preview",
            simulated=False,
            delivery="sent",
            membership_changed=True,
            created_at=0,
            updated_at=0,
        )
        self.assertEqual(set(item), {
            "id", "recipient_name", "contact", "project_id", "project_name",
            "role", "sharing", "status", "simulated", "delivery",
            "membership_changed", "created_at", "updated_at",
        })
        self.assertEqual(item["recipient_name"], "Ada Lovelace")
        self.assertEqual(item["contact"], "")
        self.assertEqual(item["project_id"], self.project["id"])
        self.assertEqual(item["project_name"], "Collaboration project")
        self.assertEqual(item["role"], "Reviewer")
        self.assertEqual(item["sharing"], {
            "goal": False, "documents": False, "history": False,
        })
        self.assertEqual(item["status"], "draft")
        self.assertTrue(item["simulated"])
        self.assertEqual(item["delivery"], "not_sent")
        self.assertFalse(item["membership_changed"])
        self.assertEqual(len(item["id"]), 32)
        self.assertNotEqual(item["id"], "forged-id")
        self.assertIsInstance(item["created_at"], float)
        self.assertIsInstance(item["updated_at"], float)
        self.assertEqual(self.t.state()["invitation_previews"], [item])

    def test_optional_contact_and_recipient_role_project_limits_are_validated(self):
        item = self.create(contact="  ada@example.test  ")
        self.assertEqual(item["contact"], "ada@example.test")
        self.assertEqual(self.create(contact=None)["contact"], "")

        invalid = [
            {"recipient_name": ""},
            {"recipient_name": "   "},
            {"recipient_name": "x" * 201},
            {"recipient_name": None},
            {"recipient_name": 7},
            {"contact": "x" * 321},
            {"contact": 7},
            {"contact": []},
            {"role": ""},
            {"role": "x" * 201},
            {"role": None},
            {"project_id": "missing"},
            {"project_id": ""},
            {"project_id": None},
            {"project_id": []},
            {"project_id": {}},
        ]
        for fields in invalid:
            with self.subTest(fields=fields):
                before = self.t.state()["invitation_previews"]
                with self.assertRaises(ValueError):
                    self.create(**fields)
                self.assertEqual(self.t.state()["invitation_previews"], before)

    def test_sharing_choices_are_strict_boolean_consent_flags(self):
        item = self.create(sharing={"goal": True, "history": True})
        self.assertEqual(item["sharing"], {
            "goal": True, "documents": False, "history": True,
        })
        for sharing in (
            None, [], "sharing", 1,
            {"goal": "true"}, {"goal": 1}, {"goal": None},
            {"documents": 0}, {"history": "false"}, {"unknown": True},
        ):
            with self.subTest(sharing=sharing):
                with self.assertRaises(ValueError):
                    self.create(sharing=sharing)

    def test_create_list_and_reopen_persist_records_in_twin_database(self):
        first = self.create(recipient_name="First")
        second = self.create(recipient_name="Second")
        self.assertEqual(
            [row["id"] for row in self.t.invitations.list()],
            [first["id"], second["id"]],
        )
        with sqlite3.connect(self.path) as db:
            tables = {row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
        self.assertIn("invitation_previews", tables)
        self.reopen()
        self.assertEqual(self.t.state()["invitation_previews"], [first, second])
        self.assertEqual(self.t.invitations.list(), [first, second])

    def test_allowed_statuses_and_invalid_transitions_statuses_and_targets(self):
        records = {
            status: self.create(recipient_name=status)
            for status in ("accepted_preview", "declined_preview", "cancelled_preview")
        }
        for status, record in records.items():
            with self.subTest(status=status):
                changed = self.t.act("/api/invitation-preview/status", {
                    "id": record["id"], "status": status,
                })
                self.assertEqual(changed["status"], status)
                self.assertEqual(changed["created_at"], record["created_at"])
                self.assertGreaterEqual(changed["updated_at"], record["updated_at"])
                for target in (
                    "draft", "accepted_preview", "declined_preview", "cancelled_preview",
                ):
                    with self.assertRaises(ValueError):
                        self.t.act("/api/invitation-preview/status", {
                            "id": record["id"], "status": target,
                        })

        draft = self.create(recipient_name="Draft")
        for status in ("", "accepted", "DRAFT", None, True, 1, [], {}):
            with self.subTest(invalid_status=status):
                with self.assertRaises(ValueError):
                    self.t.act("/api/invitation-preview/status", {
                        "id": draft["id"], "status": status,
                    })
        for target in ("missing", "", None, True, 1, [], {}):
            with self.subTest(invalid_target=target):
                with self.assertRaises(ValueError):
                    self.t.act("/api/invitation-preview/status", {
                        "id": target, "status": "accepted_preview",
                    })
        self.assertEqual(self.t.invitations.list()[-1]["status"], "draft")

    def test_delete_and_reopen_remove_only_the_selected_record(self):
        first = self.create(recipient_name="First")
        second = self.create(recipient_name="Second")
        self.assertEqual(
            self.t.act("/api/invitation-preview/delete", {"id": first["id"]}),
            {"deleted": first["id"]},
        )
        self.assertEqual(self.t.invitations.list(), [second])
        self.reopen()
        self.assertEqual(self.t.invitations.list(), [second])
        for target in (first["id"], "missing", "", None, True, 1, [], {}):
            with self.subTest(target=target):
                with self.assertRaises(ValueError):
                    self.t.act("/api/invitation-preview/delete", {"id": target})

    def test_accept_decline_and_cancel_never_change_projects_or_rooms(self):
        private = self.t.project(self.project["id"])
        private["messages"].append({"role": "user", "content": "private-message-canary"})
        self.t.save(private)
        with patch.dict(os.environ, {
            "ELECT_TWIN_ROOMS_JAY": "http://127.0.0.1:5000/#token=rooms-token-canary",
            "ELECT_TWIN_ROOMS_ALEX": "",
        }):
            rooms = self.t.room_urls()
            projects = self.t.projects()
            for status in ("accepted_preview", "declined_preview", "cancelled_preview"):
                with self.subTest(status=status):
                    item = self.create(sharing={
                        "goal": True, "documents": True, "history": True,
                    })
                    self.assertEqual(self.t.projects(), projects)
                    self.assertEqual(self.t.room_urls(), rooms)
                    changed = self.t.act("/api/invitation-preview/status", {
                        "id": item["id"], "status": status,
                    })
                    self.assertEqual(changed["status"], status)
                    self.assertEqual(changed["delivery"], "not_sent")
                    self.assertFalse(changed["membership_changed"])
                    self.assertEqual(self.t.projects(), projects)
                    self.assertEqual(self.t.room_urls(), rooms)
        self.transport.assert_not_called()
        self.network.assert_not_called()

    def test_private_canaries_never_appear_in_preview_output_or_listing(self):
        self.t.act("/api/document", {
            "project_id": self.project["id"],
            "name": "private.txt",
            "text": "private-document-canary",
        })
        self.t.act("/api/decision", {
            "project_id": self.project["id"],
            "text": "private-decision-canary",
        })
        private = self.t.project(self.project["id"])
        private["messages"].append({"role": "user", "content": "private-message-canary"})
        self.t.save(private)
        twin.SESSION_KEYS["openai"] = "provider-key-canary"
        with patch.dict(os.environ, {
            "ELECT_TWIN_ROOMS_JAY": "http://127.0.0.1:5000/#token=rooms-token-canary",
        }):
            item = self.create(
                private_note="private-note-canary",
                document_body="private-document-canary",
                decisions="private-decision-canary",
                messages="private-message-canary",
                provider_key="provider-key-canary",
                bearer_link="rooms-token-canary",
            )
            output = json.dumps(item)
            listing = json.dumps(self.t.state()["invitation_previews"])
            stored = self.t.db.execute(
                "SELECT body FROM invitation_previews WHERE id=?", (item["id"],),
            ).fetchone()[0]
            for canary in (
                "private-document-canary", "private-decision-canary",
                "private-message-canary", "provider-key-canary",
                "rooms-token-canary", "private-note-canary",
            ):
                self.assertNotIn(canary, output)
                self.assertNotIn(canary, listing)
                self.assertNotIn(canary, stored)


if __name__ == "__main__":
    unittest.main()
