"""Studio Dashboard layout persistence, widget operations, and strict store isolation."""
import json
import os
import stat
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from twin import Twin, Handler, default_dashboard_layout, DASHBOARD_WIDGET_TYPES, DASHBOARD_DAY_ONE


def sample_widgets():
    return [
        {"id": "dash-morning_postcard", "type": "morning_postcard", "title": "While You Were Out", "span": "1x1", "config": {}, "order": 0},
        {"id": "dash-project_decisions", "type": "project_decisions", "title": "Pinned Decisions", "span": "2x1", "config": {"project_id": "p1"}, "order": 1},
        {"id": "dash-zoo_odds_watch", "type": "zoo_odds_watch", "title": "Arena Odds Watch", "span": "1x1", "config": {}, "order": 2},
    ]


class DashboardLayoutPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.twin = Twin(Path(self.tmp.name) / "projects.sqlite3", transport=lambda *a: ("", {}))

    def tearDown(self):
        self.twin.db.close()
        self.twin.zoo.close()
        self.tmp.cleanup()

    def test_default_layout_seeds_day_one_value_widgets_first(self):
        layout = default_dashboard_layout()
        day_one = [t for t, _ in DASHBOARD_DAY_ONE]
        self.assertEqual([w["type"] for w in layout][:4], day_one)
        self.assertEqual({w["type"] for w in layout}, set(DASHBOARD_WIDGET_TYPES))
        self.assertEqual(len(layout), len(DASHBOARD_WIDGET_TYPES))
        self.assertEqual(layout[0]["span"], "2x1")  # model_market_tracker leads wide
        self.assertTrue(all(w["span"] == "1x1" for w in layout[1:]))
        self.assertEqual([w["order"] for w in layout], list(range(len(layout))))
        self.assertTrue(all(w["config"] == {} for w in layout))

    def test_day_one_widget_types_validate(self):
        widgets = [
            {"id": "dash-model_market_tracker", "type": "model_market_tracker", "title": "Frontier Model Intelligence", "span": "2x1", "config": {}, "order": 0},
            {"id": "dash-global_agent_telemetry", "type": "global_agent_telemetry", "title": "The Live Zoo Pulse", "span": "1x1", "config": {}, "order": 1},
        ]
        saved = self.twin.save_dashboard_layout(widgets)
        self.assertEqual([w["type"] for w in saved], ["model_market_tracker", "global_agent_telemetry"])

    def test_save_then_reload_returns_same_layout(self):
        saved = self.twin.save_dashboard_layout(sample_widgets())
        self.assertEqual([w["id"] for w in saved], [w["id"] for w in sample_widgets()])
        self.assertEqual(saved[1]["span"], "2x1")
        path = Path(self.tmp.name) / "dashboard_layout.json"
        self.assertTrue(path.exists())
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.twin.db.close()
        reloaded = Twin(Path(self.tmp.name) / "projects.sqlite3", transport=lambda *a: ("", {}))
        try:
            layout = reloaded.dashboard_layout()
            self.assertEqual([w["id"] for w in layout], [w["id"] for w in sample_widgets()])
            self.assertEqual(layout[1]["config"], {"project_id": "p1"})
        finally:
            reloaded.db.close()
            reloaded.zoo.close()

    def test_corrupt_layout_file_falls_back_to_default(self):
        path = Path(self.tmp.name) / "dashboard_layout.json"
        path.write_text("{not json", encoding="utf-8")
        os.chmod(path, 0o600)
        self.assertEqual(self.twin.dashboard_layout(), default_dashboard_layout())

    def test_empty_saved_layout_is_rejected_so_default_survives(self):
        with self.assertRaises(ValueError):
            self.twin.save_dashboard_layout([])
        self.assertFalse((Path(self.tmp.name) / "dashboard_layout.json").exists())

    def test_validation_rejects_bad_type_duplicate_id_bad_span_and_extra_fields(self):
        cases = [
            [{**sample_widgets()[0], "type": "evidence_board"}],
            [sample_widgets()[0], dict(sample_widgets()[0])],
            [{**sample_widgets()[0], "span": 3}],
            [{**sample_widgets()[0], "secret_rows": [{"text": "private"}]}],
            [{**sample_widgets()[0], "id": ""}],
            [{**sample_widgets()[0], "config": "not-an-object"}],
            "not-a-list",
        ]
        for widgets in cases:
            with self.assertRaises(ValueError, msg=str(widgets)):
                self.twin.save_dashboard_layout(widgets)
        self.assertFalse((Path(self.tmp.name) / "dashboard_layout.json").exists())

    def test_too_many_widgets_rejected(self):
        many = [dict(sample_widgets()[0], id=f"w{i}", order=i) for i in range(13)]
        with self.assertRaises(ValueError):
            self.twin.save_dashboard_layout(many)

    def test_move_edit_delete_round_trip(self):
        widgets = sample_widgets()
        widgets[0], widgets[2] = widgets[2], widgets[0]  # move
        widgets[1]["title"] = "Renamed Pinned"  # edit
        del widgets[2]  # delete
        saved = self.twin.save_dashboard_layout(widgets)
        self.assertEqual(len(saved), 2)
        self.assertEqual(saved[0]["type"], "zoo_odds_watch")
        self.assertEqual(saved[1]["title"], "Renamed Pinned")
        self.assertEqual([w["order"] for w in saved], [0, 1])


class DashboardHttpAndIsolationTests(unittest.TestCase):
    CANARY = "private-vault-canary-9f31"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        port = self.server.server_address[1]
        self.server.origin = "http://127.0.0.1:" + str(port)
        self.server.hosts = {"127.0.0.1:" + str(port)}
        self.server.token = "private-test-session"
        self.server.twin = Twin(Path(self.tmp.name) / "projects.sqlite3", transport=lambda *a: ("", {}))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        # A private project row that must never leak into layout or Zoo payloads.
        project = self.server.twin.act("/api/projects", {"name": "Stealth " + self.CANARY, "goal": "goal " + self.CANARY})
        self.server.twin.act("/api/decision", {"project_id": project["id"], "text": "Decision " + self.CANARY})

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.server.twin.db.close()
        self.server.twin.zoo.close()
        self.tmp.cleanup()

    def request(self, method, path, payload=None, token=True):
        headers = {"X-Twin-Token": self.server.token} if token else {}
        data = json.dumps(payload).encode() if payload is not None else None
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = Request(self.server.origin + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, json.loads(response.read().decode())
        except HTTPError as error:
            return error.code, json.loads(error.read().decode())

    def test_get_requires_private_token(self):
        status, _ = self.request("GET", "/api/dashboard/layout", token=False)
        self.assertEqual(status, 403)
        status, body = self.request("GET", "/api/dashboard/layout")
        self.assertEqual(status, 200)
        self.assertEqual(len(body["widgets"]), len(DASHBOARD_WIDGET_TYPES))
        self.assertEqual([w["type"] for w in body["widgets"]][:4], [t for t, _ in DASHBOARD_DAY_ONE])

    def test_post_move_edit_delete_then_get_reflects(self):
        widgets = sample_widgets()
        status, _ = self.request("POST", "/api/dashboard/layout", {"widgets": widgets})
        self.assertEqual(status, 200)
        widgets[0], widgets[2] = widgets[2], widgets[0]
        widgets[1]["title"] = "Edited Title"
        del widgets[2]
        status, body = self.request("POST", "/api/dashboard/layout", {"widgets": widgets})
        self.assertEqual(status, 200)
        status, body = self.request("GET", "/api/dashboard/layout")
        self.assertEqual(status, 200)
        self.assertEqual([w["type"] for w in body["widgets"]], ["zoo_odds_watch", "project_decisions"])
        self.assertEqual(body["widgets"][1]["title"], "Edited Title")

    def test_layout_never_contains_private_vault_rows(self):
        self.request("POST", "/api/dashboard/layout", {"widgets": sample_widgets()})
        _, body = self.request("GET", "/api/dashboard/layout")
        self.assertNotIn(self.CANARY, json.dumps(body))
        self.assertNotIn('"decisions":', json.dumps(body))
        self.assertNotIn('"documents":', json.dumps(body))

    def test_rejected_layout_keeps_previous_persisted_state(self):
        self.request("POST", "/api/dashboard/layout", {"widgets": sample_widgets()})
        status, _ = self.request("POST", "/api/dashboard/layout", {"widgets": [{"type": "nope", "id": "x"}]})
        self.assertEqual(status, 400)
        _, body = self.request("GET", "/api/dashboard/layout")
        self.assertEqual(len(body["widgets"]), 3)

    def test_zoo_state_never_contains_private_vault_rows(self):
        with self.server.twin.lock:
            zoo_payload = json.dumps(self.server.twin.zoo.state())
        self.assertNotIn(self.CANARY, zoo_payload)
        _, private_payload = self.request("GET", "/api/state")
        self.assertIn(self.CANARY, json.dumps(private_payload))


if __name__ == "__main__":
    unittest.main()
