"""Regression tests for the integrated local shell. No provider calls."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import twin


class LocalShellTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.t = twin.Twin(Path(self.tmp.name) / "projects.db")

    def tearDown(self):
        self.t.zoo.close()
        self.t.db.close()
        self.tmp.cleanup()

    def test_profile_is_local_persistent_and_validated(self):
        state = self.t.state()
        self.assertEqual(state["profile"]["human_name"], "You")
        self.assertEqual(state["profile"]["twin_name"], "My Twin")
        saved = self.t.act("/api/profile", {
            "human_name": "Jay",
            "twin_name": "Jay Twin",
            "role": "Designer",
            "bio": "Local test profile",
        })
        self.assertEqual(saved["human_name"], "Jay")
        self.t.zoo.close();self.t.db.close()
        self.t = twin.Twin(self.t.path)
        self.assertEqual(self.t.state()["profile"]["twin_name"], "Jay Twin")
        with self.assertRaises(ValueError):
            self.t.act("/api/profile", {"human_name": "", "twin_name": "Twin", "role": "", "bio": ""})

    def test_challenges_require_explicit_local_review(self):
        challenge = self.t.act("/api/challenges", {"title": "Compare options", "prompt": "Compare three local design options."})
        self.assertEqual(challenge["status"], "submitted")
        self.assertEqual(self.t.state()["challenges"][0]["status"], "submitted")
        reviewed = self.t.act("/api/challenge/review", {"id": challenge["id"], "approved": True})
        self.assertEqual(reviewed["status"], "reviewed")
        self.assertGreater(reviewed["reviewed_at"], 0)
        with self.assertRaises(ValueError):
            self.t.act("/api/challenge/review", {"id": challenge["id"], "approved": True})
        with self.assertRaises(ValueError):
            self.t.act("/api/challenges", {"title": "Bad", "prompt": ""})

    def test_following_is_local_idempotent_and_removable(self):
        item = self.t.act("/api/follow", {"kind": "agent", "target": "jay-twin", "label": "Jay Twin"})
        again = self.t.act("/api/follow", {"kind": "agent", "target": "jay-twin", "label": "Jay Twin"})
        self.assertEqual(item["id"], again["id"])
        self.assertEqual(len(self.t.state()["following"]), 1)
        self.t.act("/api/unfollow", {"id": item["id"]})
        self.assertEqual(self.t.state()["following"], [])
        with self.assertRaises(ValueError):
            self.t.act("/api/follow", {"kind": "remote-user", "target": "nobody", "label": "Nobody"})

    def test_project_database_does_not_contain_room_tokens(self):
        with patch.dict(os.environ, {
            "ELECT_TWIN_ROOMS_JAY": "http://127.0.0.1:5000/#token=room-secret",
            "ELECT_TWIN_ROOMS_ALEX": "http://127.0.0.1:5000/#token=other-secret",
        }):
            state = self.t.state()
            self.assertIn("room-secret", state["rooms"]["jay"])
            self.assertNotIn(b"room-secret", self.t.path.read_bytes())

    def test_native_and_classic_documents_are_distinct(self):
        classic = twin.index_html()
        shell = twin.index_html(page="shell")
        self.assertIn("Personal workspace", classic)
        self.assertIn("Agent Zoo", shell)
        self.assertNotIn("||'development-token'", shell)
        self.assertIn("||'development-token'", twin.index_html("development-token", page="shell"))


if __name__ == "__main__":
    unittest.main()
