"""Authenticated localhost OS APIs, bounded public cache, and privacy isolation."""
import json
import os
import stat
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from model_router import OpenRouterIndex
from twin import Handler, Twin


class OpenRouterIndexTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "openrouter-index.json"
        self.calls = []

        def transport(url, timeout, limit):
            self.calls.append((url, timeout, limit))
            return json.dumps({"data": [
                {"id": "vendor/model-one", "pricing": {"prompt": "0.1", "completion": "0.2", "private": "discard"}, "secret": "discard"},
                {"id": "vendor/model-two", "pricing": {"prompt": "0", "completion": "0"}},
            ]}).encode()

        self.transport = transport

    def tearDown(self):
        self.temporary.cleanup()

    def test_consent_fetch_then_24_hour_atomic_cache(self):
        index = OpenRouterIndex(self.path, transport=self.transport)
        denied = index.get(consent=False)
        self.assertFalse(denied["available"])
        self.assertEqual(self.calls, [])
        first = index.get(consent=True, now=1000)
        self.assertTrue(first["available"])
        self.assertFalse(first["cached"])
        self.assertEqual(len(first["models"]), 2)
        self.assertNotIn("secret", json.dumps(first))
        self.assertNotIn("private", json.dumps(first))
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        second = index.get(consent=False, now=1000 + 86399)
        self.assertTrue(second["cached"])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][0], "https://openrouter.ai/api/v1/models")
        self.assertEqual(self.calls[0][2], 5000000)

    def test_expired_or_failed_fetch_is_honest_and_not_retried(self):
        index = OpenRouterIndex(self.path, transport=self.transport)
        index.get(consent=True, now=1000)
        expired = index.get(consent=False, now=1000 + 86401)
        self.assertFalse(expired["available"])
        self.assertEqual(len(self.calls), 1)

        def failing(*args):
            self.calls.append(args)
            raise TimeoutError("offline")

        fallback = OpenRouterIndex(Path(self.temporary.name) / "other.json", transport=failing)
        result = fallback.get(consent=True)
        self.assertFalse(result["available"])
        self.assertIn("offline", result["reason"].lower())
        self.assertEqual(len(self.calls), 2)


class OSAPIIntegrationTests(unittest.TestCase):
    CANARY = "private-vault-canary-os-51d7"

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        port = self.server.server_address[1]
        self.server.origin = "http://127.0.0.1:" + str(port)
        self.server.hosts = {"127.0.0.1:" + str(port)}
        self.server.token = "private-os-test-session"
        self.server.twin = Twin(Path(self.temporary.name) / "projects.sqlite3", transport=lambda *args: ("", {}))
        project = self.server.twin.act("/api/projects", {"name": self.CANARY, "goal": self.CANARY})
        self.server.twin.act("/api/decision", {"project_id": project["id"], "text": self.CANARY})
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.server.twin.close()
        self.temporary.cleanup()

    def request(self, method, path, payload=None, token=True):
        headers = {"X-Twin-Token": self.server.token} if token else {}
        data = json.dumps(payload).encode() if payload is not None else None
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = Request(self.server.origin + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode())
        except HTTPError as error:
            return error.code, json.loads(error.read().decode())

    def test_unauthorized_post_and_get_are_rejected(self):
        status, _ = self.request("POST", "/api/swarm/evaluate", {"prompt": "Compare $A and $B"}, token=False)
        self.assertEqual(status, 403)
        status, _ = self.request("GET", "/api/skills/search?query=security", token=False)
        self.assertEqual(status, 403)

    def test_swarm_router_and_news_routes(self):
        status, swarm = self.request("POST", "/api/swarm/evaluate", {
            "prompt": "Research $NVDA $BTC $AAPL", "targets": ["$NVDA", "$BTC", "$AAPL"],
            "swarm_policy": "notify_accept", "tier": "free",
        })
        self.assertEqual(status, 200)
        self.assertTrue(swarm["requires_acceptance"])
        self.assertFalse(swarm["execution_started"])
        status, route = self.request("POST", "/api/models/route-version", {
            "family": "kimi", "connected_models": ["kimi-k2.8", "kimi-k3.1-pro"],
            "prompt": "Refactor multi-file architecture and audit security",
        })
        self.assertEqual(status, 200)
        self.assertEqual(route["selected_model"], "kimi-k3.1-pro")
        status, news = self.request("POST", "/api/dashboard/open-news", {"url_or_headline": "https://example.com/story"})
        self.assertEqual(status, 200)
        self.assertFalse(news["source_text_available"])
        self.assertIn("not fetched", news["method"])

    def test_get_and_post_skills_never_return_unselected_playbooks(self):
        path = "/api/skills/search?" + urlencode({"query": "security architecture", "limit": 3})
        status, body = self.request("GET", path)
        self.assertEqual(status, 200)
        self.assertTrue(body["skills"])
        self.assertNotIn("builder_instructions", json.dumps(body))
        skill_id = body["skills"][0]["id"]
        status, bundle = self.request("POST", "/api/skills/optimize-prompt", {
            "query": "security architecture", "skill_ids": [skill_id],
        })
        self.assertEqual(status, 200)
        self.assertIn("builder_instructions", bundle["selected"][0])
        status, learned = self.request("POST", "/api/skills/learn-preference", {"rule": "Label uncertainty plainly."})
        self.assertEqual(status, 200)
        self.assertEqual(learned["rule_count"], 1)

    def test_layout_and_private_canary_isolation(self):
        status, layout = self.request("GET", "/api/dashboard/layout")
        self.assertEqual(status, 200)
        self.assertEqual(len(layout["tabs"]), 5)
        responses = [layout]
        responses.append(self.request("GET", "/api/skills/search?query=security")[1])
        responses.append(self.request("POST", "/api/models/route-version", {
            "family": "kimi", "connected_models": ["kimi-k2.8"], "prompt": "Summary",
        })[1])
        responses.append(self.request("POST", "/api/dashboard/open-news", {"url_or_headline": "A reported survey"})[1])
        responses.append(self.request("GET", "/api/zoo/state")[1])
        self.assertNotIn(self.CANARY, json.dumps(responses))

    def test_market_route_uses_injected_cache_transport(self):
        calls = []

        def transport(url, timeout, limit):
            calls.append(url)
            return b'{"data":[{"id":"public/model","pricing":{"prompt":"0","completion":"0"}}]}'

        self.server.twin._market_index = OpenRouterIndex(Path(self.temporary.name) / "market.json", transport=transport)
        status, first = self.request("POST", "/api/models/market-index", {"consent": True})
        self.assertEqual(status, 200)
        self.assertTrue(first["available"])
        status, second = self.request("POST", "/api/models/market-index", {"consent": True})
        self.assertEqual(status, 200)
        self.assertTrue(second["cached"])
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
