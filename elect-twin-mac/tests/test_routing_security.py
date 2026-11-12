"""Shared route and native security regression tests; no provider calls."""
import contextlib
import io
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import twin


class RouteSecurityTests(unittest.TestCase):
    def setUp(self):
        twin.SESSION_KEYS.clear()
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), twin.Handler)
        port = self.server.server_address[1]
        self.server.origin = "http://127.0.0.1:" + str(port)
        self.server.hosts = {"127.0.0.1:" + str(port)}
        self.server.token = "routing-test-session"
        self.server.native_mode = False
        self.server.twin = twin.Twin(
            Path(self.tmp.name) / "projects.sqlite3",
            zoo_path=Path(self.tmp.name) / "zoo.sqlite3",
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.server.twin.zoo.close()
        self.server.twin.db.close()
        self.tmp.cleanup()
        twin.SESSION_KEYS.clear()

    def get(self, path, token=None, headers=None):
        request_headers = dict(headers or {})
        if token is not None:
            request_headers["X-Twin-Token"] = token
        request = Request(self.server.origin + path, headers=request_headers)
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, response.headers.get_content_type(), response.read().decode()
        except HTTPError as error:
            return error.code, error.headers.get_content_type(), error.read().decode()

    def post(self, path, data, token=None):
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["X-Twin-Token"] = token
        request = Request(
            self.server.origin + path,
            data=json.dumps(data).encode(),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def assert_not_found(self, path):
        status, _, _ = self.get(path, token=self.server.token)
        self.assertEqual(status, 404)

    def test_existing_and_twin_documents_accept_queries(self):
        cases = {
            "/": "Personal workspace",
            "/home": "Agent Zoo",
            "/projects": "Personal workspace",
            "/twin": "Personal workspace",
            "/twin/projects": "Personal workspace",
        }
        for path, marker in cases.items():
            for suffix in ("", "?view=compact"):
                with self.subTest(path=path + suffix):
                    status, content_type, body = self.get(path + suffix)
                    self.assertEqual(status, 200)
                    self.assertEqual(content_type, "text/html")
                    self.assertIn(marker, body)

    def test_zoo_fixed_and_existing_routes_serve_shell(self):
        paths = [
            "/zoo",
            "/zoo/rooms/room-zero",
            "/zoo/categories/free-for-all",
            "/zoo/categories/lets-collaborate",
            "/zoo/categories/human-challenges",
            "/zoo/categories/ideas-experiments",
            "/zoo/threads/thread-people",
            "/zoo/agents/jay",
            "/zoo/agents/alex",
            "/zoo/agents/jay-twin",
            "/zoo/agents/alex-twin",
        ]
        for path in paths:
            with self.subTest(path=path):
                status, content_type, body = self.get(path + "?from=test")
                self.assertEqual(status, 200)
                self.assertEqual(content_type, "text/html")
                self.assertIn("Agent Zoo", body)

    def test_local_thread_route_uses_current_zoo_store(self):
        item = self.server.twin.zoo.act("/api/zoo/thread", {
            "category_id": "ideas-experiments",
            "title": "Route to this local thread",
        })
        status, content_type, body = self.get(
            "/zoo/threads/" + item["id"] + "?view=full",
        )
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "text/html")
        self.assertIn("Agent Zoo", body)

    def test_malformed_unknown_and_unimplemented_asset_routes_remain_404(self):
        paths = [
            "/zoo/",
            "/zoo/unknown",
            "/zoo/rooms/missing",
            "/zoo/rooms/room-zero/extra",
            "/zoo/categories/missing",
            "/zoo/categories/free-for-all/extra",
            "/zoo/threads/missing",
            "/zoo/threads/thread-people/extra",
            "/zoo/agents/missing",
            "/zoo/agents/jay/extra",
            "/zoo/categories/free-for-all%2F..%2Fagents%2Fjay",
            "/twin/",
            "/twin/projects/extra",
            "/favicon.ico",
            "/zoo.js",
            "/zoo.css",
            "/onboarding.js",
            "/api/zoo/state/extra",
            "/not-a-route?next=/zoo",
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assert_not_found(path)

    def test_zoo_get_api_requires_auth_and_parses_queries(self):
        for token in (None, "wrong-token"):
            with self.subTest(token=token):
                status, _, _ = self.get("/api/zoo/state?full=1", token=token)
                self.assertEqual(status, 403)
        status, content_type, body = self.get(
            "/api/zoo/state?full=1", token=self.server.token,
        )
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "application/json")
        self.assertIn("categories", json.loads(body))
        status, _, _ = self.get(
            "/api/zoo/state",
            token=self.server.token,
            headers={"Origin": "https://evil.example"},
        )
        self.assertEqual(status, 403)

    def test_product_is_selected_by_path_not_public_hostnames(self):
        self.assertEqual(self.get("/twin")[0], 200)
        self.assertEqual(self.get("/zoo")[0], 200)
        for host in ("twin.electri.ai", "zoo.electri.ai"):
            for path in ("/twin", "/zoo", "/api/zoo/state"):
                with self.subTest(host=host, path=path):
                    status, _, _ = self.get(
                        path, token=self.server.token, headers={"Host": host},
                    )
                    self.assertEqual(status, 403)

    def test_zoo_document_and_api_exclude_private_canaries(self):
        project = self.server.twin.act("/api/projects", {
            "name": "private-project-route-canary",
            "goal": "Keep Twin content outside Zoo",
        })
        self.server.twin.act("/api/document", {
            "project_id": project["id"],
            "name": "private.txt",
            "text": "private-document-route-canary",
        })
        twin.SESSION_KEYS["openai"] = "provider-key-route-canary"
        canaries = (
            "private-project-route-canary",
            "private-document-route-canary",
            "provider-key-route-canary",
            "rooms-token-route-canary",
        )
        with patch.dict(os.environ, {
            "ELECT_TWIN_ROOMS_JAY": (
                "http://127.0.0.1:5000/#token=rooms-token-route-canary"
            ),
        }):
            for path, token in (
                ("/zoo", None),
                ("/zoo/threads/thread-people", None),
                ("/api/zoo/state", self.server.token),
            ):
                with self.subTest(path=path):
                    status, _, body = self.get(path, token=token)
                    self.assertEqual(status, 200)
                    for canary in canaries:
                        self.assertNotIn(canary, body)

    def test_post_api_uses_parsed_path(self):
        status, body = self.post(
            "/api/zoo/thread?source=route-test",
            {"category_id": "free-for-all", "title": "Created through query route"},
            token=self.server.token,
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["title"], "Created through query route")

    def test_zoo_data_argument_is_parsed_forwarded_and_closed(self):
        data = Path(self.tmp.name) / "argument-projects.sqlite3"
        zoo_data = Path(self.tmp.name) / "argument-zoo.sqlite3"
        argv = [
            "twin.py", "--native", "--port", "0", "--data", str(data),
            "--zoo-data", str(zoo_data),
        ]
        with (
            patch("sys.argv", argv),
            patch("twin.ThreadingHTTPServer") as server_type,
            patch("twin.Twin") as twin_type,
        ):
            server = server_type.return_value
            server.server_address = ("127.0.0.1", 4321)
            server.serve_forever.return_value = None
            try:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    twin.main()
            except SystemExit as error:
                self.fail("--zoo-data was not accepted: " + str(error))
            self.assertEqual(twin_type.call_args.args, (str(data),))
            self.assertEqual(twin_type.call_args.kwargs["catalog"], None)
            self.assertEqual(twin_type.call_args.kwargs["zoo_path"], str(zoo_data))
            server.serve_forever.assert_called_once_with()
            server.server_close.assert_called_once_with()
            twin_type.return_value.zoo.close.assert_called_once_with()
            twin_type.return_value.db.close.assert_called_once_with()


class NativeSourceSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.native = (root / "native" / "AppDelegate.swift").read_text(encoding="utf-8")
        rooms_ref = (
            root / "rooms-reference" / "Elect Twin Rooms.app" / "Contents" /
            "Resources" / "server" / "_internal" / "web" / "index.html"
        )
        if not rooms_ref.exists():
            rooms_ref = root.parent / "elect-twin-windows" / "web" / "index.html"
        cls.rooms = rooms_ref.read_text(encoding="utf-8")

    def test_rooms_provider_environment_is_scrubbed_before_launch(self):
        for key in (
            "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
            "MISTRAL_API_KEY", "GROQ_API_KEY",
        ):
            self.assertIn('"' + key + '"', self.native)
        scrub = "providerEnvironmentKeys.forEach { roomsEnvironment.removeValue(forKey: $0) }"
        self.assertIn(scrub, self.native)
        self.assertLess(
            self.native.index(scrub),
            self.native.index("rooms.environment = roomsEnvironment"),
        )
        self.assertLess(
            self.native.index("rooms.environment = roomsEnvironment"),
            self.native.index("try rooms.run()"),
        )

    def test_native_twin_receives_separate_zoo_store(self):
        normalized = " ".join(self.native.split())
        self.assertIn(
            'let zooData = root.appendingPathComponent("zoo.sqlite3").path',
            normalized,
        )
        self.assertIn(
            'twin.arguments = ["--native", "--port", "0", "--data", twinData, '
            '"--zoo-data", zooData]',
            normalized,
        )

    def test_native_zoo_deep_link_preserves_session_and_has_home_fallback(self):
        self.assertIn('if url.host == "zoo" { goZoo() }', self.native)
        self.assertIn("private func goZoo()", self.native)
        self.assertIn("URLComponents(url: homeURL", self.native)
        self.assertIn('components.path = "/zoo"', self.native)
        self.assertIn("components.url", self.native)
        self.assertIn("isLoopback(zooURL)", self.native)
        self.assertIn("goHome()", self.native)

    def test_rooms_header_exposes_visible_zoo_return_beside_home(self):
        header = self.rooms.split("<header>", 1)[1].split("</header>", 1)[0]
        home = header.index('href="elect-twin://home"')
        self.assertIn('href="elect-twin://zoo"', header)
        zoo = header.index('href="elect-twin://zoo"')
        self.assertLess(home, zoo)
        self.assertRegex(
            header,
            r'<a href="elect-twin://zoo"[^>]*>[^<]*Zoo[^<]*</a>',
        )


if __name__ == "__main__":
    unittest.main()
