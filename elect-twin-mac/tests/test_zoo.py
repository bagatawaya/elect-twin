"""Persistent, local-only Agent Zoo storage and privacy boundary tests."""
import json
import os
import sqlite3
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import twin
from zoo import ZooStore


CATEGORIES = [
    ("free-for-all", "Free for All"),
    ("lets-collaborate", "Let’s Collaborate"),
    ("human-challenges", "Human Challenges"),
    ("ideas-experiments", "Ideas & Experiments"),
]


class ZooStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.path = Path(self.tmp.name) / "zoo.sqlite3"
        self.store = ZooStore(self.path)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def make_thread(self, title="A local discussion"):
        return self.store.act("/api/zoo/thread", {
            "category_id": "free-for-all",
            "title": title,
        })

    def make_post(self, thread_id, content="A local message"):
        return self.store.act("/api/zoo/post", {
            "thread_id": thread_id,
            "content": content,
        })

    def test_seeded_categories_examples_and_agent_profiles_are_explicit(self):
        state = self.store.state()
        self.assertEqual(
            [(row["id"], row["title"]) for row in state["categories"]],
            CATEGORIES,
        )
        pinned = [row for row in state["threads"] if row["is_top"]]
        self.assertEqual(len(pinned), 1)
        self.assertEqual(pinned[0]["title"], "What’s the deal with people?")
        self.assertTrue(pinned[0]["simulated"])
        self.assertTrue(all(row["simulated"] for row in state["posts"]))
        self.assertTrue(state["agents"])
        for agent in state["agents"]:
            self.assertTrue(agent["simulated"])
            self.assertEqual(agent["identity_origin"], "simulated")
            self.assertEqual(agent["execution_mode"], "simulated")
            self.assertIn(agent["connectivity"], {"local_only", "unverified_external"})
        self.assertNotIn("external interoperability", json.dumps(state).lower())

    def test_local_thread_and_post_have_server_enforced_shape(self):
        thread = self.make_thread()
        self.assertEqual(set(thread), {
            "id", "room_id", "category_id", "title", "author_id", "created_at",
            "origin", "simulated", "visibility", "is_top", "reaction_counts",
        })
        self.assertEqual(thread["room_id"], "room-zero")
        self.assertEqual(thread["category_id"], "free-for-all")
        self.assertEqual(thread["author_id"], "you")
        self.assertEqual(thread["origin"], "local")
        self.assertFalse(thread["simulated"])
        self.assertEqual(thread["visibility"], "local_only")
        self.assertFalse(thread["is_top"])
        self.assertEqual(thread["reaction_counts"], {
            "appreciate": 0, "curious": 0, "idea": 0,
        })
        self.assertIsInstance(thread["created_at"], float)
        self.assertEqual(len(thread["id"]), 32)

        post = self.make_post(thread["id"])
        self.assertEqual(post["thread_id"], thread["id"])
        self.assertEqual(post["author_id"], "you")
        self.assertEqual(post["content"], "A local message")
        self.assertEqual(post["origin"], "local")
        self.assertFalse(post["simulated"])
        self.assertEqual(post["visibility"], "local_only")
        self.assertEqual(post["reaction_counts"], {
            "appreciate": 0, "curious": 0, "idea": 0,
        })
        state = self.store.state()
        self.assertIn(thread["id"], {row["id"] for row in state["threads"]})
        self.assertIn(post["id"], {row["id"] for row in state["posts"]})

    def test_forged_provenance_visibility_and_authorship_are_rejected(self):
        forged = [
            {"origin": "external"},
            {"visibility": "public"},
            {"simulated": True},
            {"author_id": "somebody-else"},
            {"room_id": "another-room"},
            {"is_top": True},
        ]
        for fields in forged:
            with self.subTest(fields=fields):
                with self.assertRaises(ValueError):
                    self.store.act("/api/zoo/thread", {
                        "category_id": "free-for-all",
                        "title": "Forged thread",
                        **fields,
                    })
        self.assertNotIn("Forged thread", json.dumps(self.store.state()))

    def test_reopen_persists_rows_and_seeds_are_idempotent(self):
        thread = self.make_thread("Persist me")
        post = self.make_post(thread["id"], "Persist this message")
        before = self.store.state()
        self.store.close()
        self.store = ZooStore(self.path)
        after = self.store.state()
        self.assertEqual(len(after["threads"]), len(before["threads"]))
        self.assertEqual(len(after["posts"]), len(before["posts"]))
        self.assertEqual(
            next(row for row in after["threads"] if row["id"] == thread["id"])["title"],
            "Persist me",
        )
        self.assertEqual(
            next(row for row in after["posts"] if row["id"] == post["id"])["content"],
            "Persist this message",
        )
        self.store.close()
        self.store = ZooStore(self.path)
        self.assertEqual(len(self.store.state()["threads"]), len(before["threads"]))
        if os.name != "nt":
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        with sqlite3.connect(self.path) as db:
            tables = {row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
        self.assertTrue({"threads", "posts", "reactions", "follows"} <= tables)

    def test_reaction_counts_are_exact_idempotent_and_persistent(self):
        thread = self.make_thread()
        post = self.make_post(thread["id"])
        first = self.store.act("/api/zoo/reaction", {
            "target_id": thread["id"], "reaction": "appreciate",
        })
        repeat = self.store.act("/api/zoo/reaction", {
            "target_id": thread["id"], "reaction": "appreciate",
        })
        self.assertEqual(first["id"], repeat["id"])
        other = self.store.act("/api/zoo/reaction", {
            "target_id": post["id"], "reaction": "idea",
        })
        state = self.store.state()
        stored_thread = next(row for row in state["threads"] if row["id"] == thread["id"])
        stored_post = next(row for row in state["posts"] if row["id"] == post["id"])
        self.assertEqual(stored_thread["reaction_counts"]["appreciate"], 1)
        self.assertEqual(stored_thread["reaction_counts"]["curious"], 0)
        self.assertEqual(stored_post["reaction_counts"]["idea"], 1)
        self.store.act("/api/zoo/reaction/delete", {"id": first["id"]})
        after_removal = self.store.state()
        stored_thread = next(
            row for row in after_removal["threads"] if row["id"] == thread["id"]
        )
        self.assertEqual(stored_thread["reaction_counts"]["appreciate"], 0)
        repeated = self.store.act("/api/zoo/reaction/delete", {"id": first["id"]})
        self.assertEqual(repeated, {"deleted": first["id"]})
        self.assertEqual(self.store.state(), after_removal)
        self.store.close()
        self.store = ZooStore(self.path)
        stored_post = next(
            row for row in self.store.state()["posts"] if row["id"] == post["id"]
        )
        self.assertEqual(stored_post["reaction_counts"]["idea"], 1)
        self.store.act("/api/zoo/reaction/delete", {"id": other["id"]})
        after_removal = self.store.state()
        stored_post = next(
            row for row in after_removal["posts"] if row["id"] == post["id"]
        )
        self.assertEqual(stored_post["reaction_counts"]["idea"], 0)
        repeated = self.store.act("/api/zoo/reaction/delete", {"id": other["id"]})
        self.assertEqual(repeated, {"deleted": other["id"]})
        self.assertEqual(self.store.state(), after_removal)

    def test_follows_validate_targets_are_idempotent_and_persist(self):
        thread = self.make_thread()
        targets = [
            ("agent", "jay-twin"),
            ("room", "room-zero"),
            ("thread", thread["id"]),
        ]
        follows = []
        for kind, target in targets:
            item = self.store.act("/api/zoo/follow", {"kind": kind, "target": target})
            again = self.store.act("/api/zoo/follow", {"kind": kind, "target": target})
            self.assertEqual(item["id"], again["id"])
            follows.append(item)
        self.assertEqual(len(self.store.state()["follows"]), 3)
        self.store.close()
        self.store = ZooStore(self.path)
        self.assertEqual(len(self.store.state()["follows"]), 3)
        for item in follows:
            self.store.act("/api/zoo/unfollow", {"id": item["id"]})
            after_removal = self.store.state()
            repeated = self.store.act("/api/zoo/unfollow", {"id": item["id"]})
            self.assertEqual(repeated, {"deleted": item["id"]})
            self.assertEqual(self.store.state(), after_removal)
        self.assertEqual(self.store.state()["follows"], [])

    def test_unhashable_category_ids_raise_value_error_without_creating_rows(self):
        before = self.store.state()
        for category_id in ([], {}):
            with self.subTest(category_id=category_id):
                with self.assertRaises(ValueError):
                    self.store.act("/api/zoo/thread", {
                        "category_id": category_id,
                        "title": "Malformed category",
                    })
                self.assertEqual(self.store.state(), before)

    def test_unknown_targets_reactions_routes_and_input_limits_are_rejected(self):
        thread = self.make_thread()
        cases = [
            ("/api/zoo/thread", {"category_id": "missing", "title": "Bad"}),
            ("/api/zoo/thread", {"category_id": "free-for-all", "title": ""}),
            ("/api/zoo/thread", {"category_id": "free-for-all", "title": "x" * 201}),
            ("/api/zoo/post", {"thread_id": "missing", "content": "Bad"}),
            ("/api/zoo/post", {"thread_id": thread["id"], "content": ""}),
            ("/api/zoo/post", {"thread_id": thread["id"], "content": "x" * 20001}),
            ("/api/zoo/reaction", {"target_id": "missing", "reaction": "idea"}),
            ("/api/zoo/reaction", {"target_id": thread["id"], "reaction": "like"}),
            ("/api/zoo/reaction/delete", {"id": []}),
            ("/api/zoo/follow", {"kind": "agent", "target": "missing"}),
            ("/api/zoo/follow", {"kind": "remote-user", "target": "jay-twin"}),
            ("/api/zoo/follow", {"kind": "room", "target": "missing"}),
            ("/api/zoo/follow", {"kind": "thread", "target": "missing"}),
            ("/api/zoo/unfollow", {"id": {}}),
            ("/api/zoo/not-a-route", {}),
        ]
        for route, data in cases:
            with self.subTest(route=route, data=data):
                with self.assertRaises(ValueError):
                    self.store.act(route, data)


class TwinZooIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.path = Path(self.tmp.name) / "projects.sqlite3"
        self.t = twin.Twin(self.path)

    def tearDown(self):
        self.t.zoo.close()
        self.t.db.close()
        self.tmp.cleanup()

    def test_default_and_custom_paths_are_physically_separate(self):
        self.assertEqual(self.t.zoo_path, self.path.with_name("zoo.sqlite3"))
        self.assertNotEqual(self.t.zoo_path, self.t.path)
        self.assertTrue(self.t.zoo_path.exists())
        custom = Path(self.tmp.name) / "custom-zoo.sqlite3"
        other = twin.Twin(Path(self.tmp.name) / "other-projects.sqlite3", zoo_path=custom)
        try:
            self.assertEqual(other.zoo_path, custom)
            self.assertTrue(custom.exists())
        finally:
            other.zoo.close()
            other.db.close()

    def test_identical_twin_and_zoo_paths_are_rejected_before_opening_stores(self):
        same_path = Path(self.tmp.name) / "same-path.sqlite3"
        same_path.write_bytes(b"")
        with patch("twin.sqlite3.connect") as connect, patch("twin.ZooStore") as zoo:
            with self.assertRaisesRegex(ValueError, "physically separate"):
                twin.Twin(same_path, zoo_path=same_path)
            connect.assert_not_called()
            zoo.assert_not_called()

    def test_symlink_aliased_twin_and_zoo_paths_are_rejected_before_opening_stores(self):
        target = Path(self.tmp.name) / "alias-target.sqlite3"
        alias = Path(self.tmp.name) / "alias.sqlite3"
        target.write_bytes(b"")
        try:
            alias.symlink_to(target)
        except OSError:
            self.skipTest("Symlinks are not supported in this test environment")
        with patch("twin.sqlite3.connect") as connect, patch("twin.ZooStore") as zoo:
            with self.assertRaisesRegex(ValueError, "physically separate"):
                twin.Twin(target, zoo_path=alias)
            connect.assert_not_called()
            zoo.assert_not_called()

    def test_twin_delegates_zoo_routes_but_keeps_zoo_out_of_twin_state(self):
        thread = self.t.act("/api/zoo/thread", {
            "category_id": "ideas-experiments",
            "title": "Zoo-only local title",
        })
        self.assertEqual(thread["category_id"], "ideas-experiments")
        serialized = json.dumps(self.t.state())
        self.assertNotIn("Zoo-only local title", serialized)
        self.assertNotIn("zoo", serialized.lower())
        with self.assertRaises(ValueError):
            self.t.act("/api/zoo/not-a-route", {})

    def test_library_search_and_provider_preview_exclude_zoo_content(self):
        project = self.t.act("/api/projects", {
            "name": "Private project",
            "goal": "Keep project context separate",
        })
        self.t.act("/api/zoo/thread", {
            "category_id": "free-for-all",
            "title": "zoo-thread-search-canary",
        })
        state = self.t.zoo.state()
        seeded_thread = state["threads"][0]
        self.t.zoo.act("/api/zoo/post", {
            "thread_id": seeded_thread["id"],
            "content": "zoo-post-preview-canary",
        })
        self.assertEqual(self.t.library_search({"query": "zoo-thread-search-canary"}), {"results": []})
        self.assertEqual(self.t.library_search({"query": "zoo-post-preview-canary"}), {"results": []})
        preview = self.t.act("/api/preview", {
            "project_id": project["id"],
            "provider": "openai",
            "model": "fixture",
            "prompt": "Preview only project data",
            "include_history": True,
        })
        self.assertNotIn("zoo-thread-search-canary", preview["context"])
        self.assertNotIn("zoo-post-preview-canary", preview["context"])

    def test_privacy_canaries_never_enter_serialized_zoo_state(self):
        project = self.t.act("/api/projects", {
            "name": "private-project-canary",
            "goal": "Local project data",
        })
        self.t.act("/api/document", {
            "project_id": project["id"],
            "name": "secret.txt",
            "text": "private-project-canary",
        })
        twin.SESSION_KEYS["openai"] = "provider-key-canary"
        try:
            with patch.dict(os.environ, {
                "ELECT_TWIN_ROOMS_JAY": "http://127.0.0.1:5000/#token=rooms-token-canary",
            }):
                serialized = json.dumps(self.t.zoo.state())
                for canary in (
                    "private-project-canary",
                    "provider-key-canary",
                    "rooms-token-canary",
                ):
                    self.assertNotIn(canary, serialized)
                self.assertNotIn(b"private-project-canary", self.t.zoo_path.read_bytes())
        finally:
            twin.SESSION_KEYS.clear()


class ZooHttpBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), twin.Handler)
        port = self.server.server_address[1]
        self.server.origin = "http://127.0.0.1:" + str(port)
        self.server.hosts = {"127.0.0.1:" + str(port)}
        self.server.token = "zoo-test-session"
        self.server.twin = twin.Twin(Path(self.tmp.name) / "projects.sqlite3")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.server.twin.zoo.close()
        self.server.twin.db.close()
        self.tmp.cleanup()

    def get_state(self, headers):
        return urlopen(Request(
            self.server.origin + "/api/zoo/state", headers=headers,
        ), timeout=3)

    def test_zoo_state_get_requires_authentication_and_uses_zoo_store(self):
        with self.assertRaises(HTTPError) as caught:
            self.get_state({})
        self.assertEqual(caught.exception.code, 403)
        with self.get_state({"X-Twin-Token": self.server.token}) as response:
            state = json.load(response)
        self.assertEqual([row["id"] for row in state["categories"]], [row[0] for row in CATEGORIES])
        self.assertNotIn("projects", state)

    def test_polymorphic_arena_rooms_and_initial_states(self):
        state = self.server.twin.zoo.state()
        room_ids = [r["id"] for r in state["rooms"]]
        self.assertIn("whats-the-line", room_ids)
        self.assertIn("king-of-the-hill", room_ids)
        self.assertIn("the-tribal-council", room_ids)
        self.assertIn("room-zero", room_ids)

        arena = state["arena"]
        self.assertIn("whats-the-line", arena)
        self.assertFalse(arena["whats-the-line"]["unsealed"])
        self.assertIn("king-of-the-hill", arena)
        self.assertEqual(arena["king-of-the-hill"]["king"]["agent"], "Jay-Twin")
        self.assertIn("the-tribal-council", arena)
        self.assertEqual(arena["the-tribal-council"]["target"], "CineBot-9")
        self.assertIn("room-zero", arena)
        self.assertFalse(arena["room-zero"]["unsealed"])

    def test_unseal_line_action(self):
        res = self.server.twin.zoo.act("/api/zoo/unseal-line", {})
        self.assertTrue(res["ok"])
        self.assertTrue(res["unsealed"])
        self.assertTrue("Forecast Disagreement" in res["edge"] or "Contrarian AI Edge" in res["edge"])
        state = self.server.twin.zoo.state()
        self.assertTrue(state["arena"]["whats-the-line"]["unsealed"])

    def test_throne_vote_action(self):
        res = self.server.twin.zoo.act("/api/zoo/throne-vote", {"side": "challenger"})
        self.assertTrue(res["ok"])
        self.assertEqual(res["room_id"], "king-of-the-hill")
        self.assertGreaterEqual(res["state"]["challenger_votes"], 50)

    def test_jury_veto_action(self):
        res = self.server.twin.zoo.act("/api/zoo/jury-veto", {"action": "veto"})
        self.assertTrue(res["ok"])
        self.assertEqual(res["state"]["human_veto_count"], 5)
        self.assertIn("SAVED BY HUMAN CROWD OVERRIDE", res["state"]["status"])

    def test_coach_release_and_canary_isolation(self):
        # 1. Store private project canary in projects.sqlite3
        project_canary = "PRIVATE-PROJECT-CANARY-998877"
        p = self.server.twin.act('/api/projects', {"name": "Secret Vault", "goal": project_canary})
        
        # 2. Release coached twin in zoo
        res = self.server.twin.zoo.act("/api/zoo/coach-release", {
            "room_id": "whats-the-line",
            "strategy": "Contrarian statistical edge",
            "twin_name": "Test Coached Twin"
        })
        self.assertTrue(res["ok"])
        self.assertIn("Contrarian statistical edge", res["coached_post"]["content"])
        self.assertIn("resident_reply", res)
        self.assertIn("Noted approach", res["resident_reply"]["content"])

        # 3. Verify private canary NEVER leaked to Zoo store
        zoo_json = json.dumps(self.server.twin.zoo.state())
        self.assertNotIn(project_canary, zoo_json)
        self.assertNotIn("Secret Vault", zoo_json)


if __name__ == "__main__":
    unittest.main()
