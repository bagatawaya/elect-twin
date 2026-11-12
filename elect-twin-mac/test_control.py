"""Offline regression tests for local data controls and provider boundaries."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request

import twin


class Response:
    def __init__(self, body):
        self.body = body if isinstance(body, bytes) else body.encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, limit=-1):
        return self.body if limit < 0 else self.body[:limit]


class DataControlTests(unittest.TestCase):
    def setUp(self):
        twin.SESSION_KEYS.clear()
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.path = Path(self.tmp.name) / "projects.db"
        self.calls = []

        def transport(provider, model, context):
            self.calls.append(context)
            return "Stored answer", {"output_tokens": 3}

        self.t = twin.Twin(self.path, transport=transport)
        self.p = self.t.act("/api/projects", {"name": "Alpha", "goal": "Keep useful memory"})

    def tearDown(self):
        self.t.zoo.close()
        self.t.db.close()
        self.tmp.cleanup()
        twin.SESSION_KEYS.clear()

    def preview(self, **extra):
        data = {"project_id": self.p["id"], "provider": "openai", "model": "fixture", "prompt": "Help"}
        data.update(extra)
        return self.t.act("/api/preview", data)

    def test_document_and_decision_update_delete(self):
        doc = self.t.act("/api/document", {"project_id": self.p["id"], "name": "old.txt", "text": "old"})
        dec = self.t.act("/api/decision", {"project_id": self.p["id"], "text": "old decision"})
        self.t.act("/api/document/update", {"project_id": self.p["id"], "id": doc["id"], "name": "new.md", "text": "new text"})
        self.t.act("/api/decision/update", {"project_id": self.p["id"], "id": dec["id"], "text": "new decision"})
        current = self.t.project(self.p["id"])
        self.assertEqual(current["documents"][0]["name"], "new.md")
        self.assertEqual(current["documents"][0]["text"], "new text")
        self.assertEqual(current["decisions"][0]["text"], "new decision")
        self.t.act("/api/document/delete", {"project_id": self.p["id"], "id": doc["id"]})
        self.t.act("/api/decision/delete", {"project_id": self.p["id"], "id": dec["id"]})
        current = self.t.project(self.p["id"])
        self.assertEqual(current["documents"], [])
        self.assertEqual(current["decisions"], [])

    def test_mutations_invalidate_project_previews_only(self):
        other = self.t.act("/api/projects", {"name": "Beta", "goal": "Separate"})
        kept = self.t.act("/api/preview", {"project_id": other["id"], "provider": "openai", "model": "fixture", "prompt": "Keep"})
        stale = self.preview()
        doc = self.t.act("/api/document", {"project_id": self.p["id"], "name": "a.txt", "text": "a"})
        self.t.act("/api/document/delete", {"project_id": self.p["id"], "id": doc["id"]})
        with self.assertRaises(ValueError):
            self.t.act("/api/send", {"preview_id": stale["preview_id"], "consent": True})
        result = self.t.act("/api/send", {"preview_id": kept["preview_id"], "consent": True})
        self.assertEqual(result["answer"], "Stored answer")

    def test_library_search_and_project_isolation(self):
        other = self.t.act("/api/projects", {"name": "Beta", "goal": "Private other goal"})
        self.t.act("/api/document", {"project_id": self.p["id"], "name": "roadmap.md", "text": "Launch the orchard pilot"})
        self.t.act("/api/decision", {"project_id": other["id"], "text": "Keep beta separate"})
        result = self.t.act("/api/library/search", {"query": "orchard"})
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["type"], "document")
        self.assertEqual(result["results"][0]["project_id"], self.p["id"])
        scoped = self.t.act("/api/library/search", {"query": "", "project_id": self.p["id"]})
        self.assertTrue(scoped["results"])
        self.assertTrue(all(row["project_id"] == self.p["id"] for row in scoped["results"]))
        self.assertNotIn("Private other goal", json.dumps(scoped))

    def test_disconnect_removes_only_session_key(self):
        self.t.act("/api/connect", {"provider": "openai", "key": "temporary-secret"})
        with patch.dict(os.environ, {}, clear=True):
            result = self.t.act("/api/disconnect", {"provider": "openai"})
            self.assertFalse(result["configured"])
            self.assertNotIn("openai", twin.SESSION_KEYS)

    def test_project_delete_removes_assets_and_other_projects_remain(self):
        other = self.t.act("/api/projects", {"name": "Beta", "goal": "Keep"})
        asset_id = "asset-fixture"
        self.t.db.execute("INSERT INTO assets VALUES (?,?,?)", (asset_id, self.p["id"], b"png"))
        self.t.db.commit()
        self.t.act("/api/project/delete", {"id": self.p["id"]})
        self.assertEqual([p["id"] for p in self.t.projects()], [other["id"]])
        self.assertIsNone(self.t.db.execute("SELECT data FROM assets WHERE id=?", (asset_id,)).fetchone())

    def test_project_order_is_stable_after_update(self):
        other = self.t.act("/api/projects", {"name": "Beta", "goal": "Second"})
        self.t.act("/api/project", {"id": self.p["id"], "name": "Alpha updated"})
        self.assertEqual([p["id"] for p in self.t.projects()], [self.p["id"], other["id"]])

    def test_active_run_does_not_consume_new_preview(self):
        active = self.preview()
        p = self.t.project(self.p["id"])
        p["runs"].append({"id": "active", "status": "running"})
        self.t.save(p)
        with self.assertRaises(ValueError):
            self.t.act("/api/send", {"preview_id": active["preview_id"], "consent": True})
        p = self.t.project(self.p["id"])
        p["runs"] = []
        self.t.save(p)
        result = self.t.act("/api/send", {"preview_id": active["preview_id"], "consent": True})
        self.assertEqual(result["answer"], "Stored answer")


class ProviderBoundaryTests(unittest.TestCase):
    def setUp(self):
        twin.SESSION_KEYS.clear()
        twin.SESSION_KEYS["openai"] = "fixture-key"

    def tearDown(self):
        twin.SESSION_KEYS.clear()

    def test_text_response_is_bounded(self):
        oversized = Response(b" " * (5 * 1024 * 1024 + 1))
        with patch.object(twin, "urlopen", return_value=oversized):
            with self.assertRaisesRegex(RuntimeError, "too large"):
                twin.provider_call("openai", "fixture", "context")

    def test_redirect_handler_rejects_instead_of_forwarding_credentials(self):
        request = Request("https://api.openai.com/v1/chat/completions", data=b"{}", headers={"Authorization": "Bearer fixture-key"})
        redirect = HTTPError(request.full_url, 302, "redirect", {"Location": "http://untrusted.invalid/collect"}, None)
        with patch.object(twin._provider_opener, "open", side_effect=redirect):
            with self.assertRaises(RuntimeError) as caught:
                twin.provider_call("openai", "fixture", "context")
        self.assertIn("302", str(caught.exception))
        self.assertNotIn("fixture-key", str(caught.exception))

    def test_default_opener_has_no_redirect_handler(self):
        handlers = twin._provider_opener.handlers
        self.assertFalse(any(type(handler).__name__ == "HTTPRedirectHandler" for handler in handlers))
        self.assertTrue(any(type(handler).__name__ == "NoRedirect" for handler in handlers))

    def test_development_token_is_opt_in(self):
        self.assertNotIn("||'development-token'", twin.index_html())
        self.assertIn("||'development-token'", twin.index_html("development-token"))


if __name__ == "__main__":
    unittest.main()
