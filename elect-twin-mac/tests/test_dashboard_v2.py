"""Five-tab dashboard schema, migration, and persistence tests."""
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from dashboard_v2 import DashboardStore, default_layout, migrate_layout, validate_layout


class DashboardV2Tests(unittest.TestCase):
    def test_default_has_five_prepopulated_tabs(self):
        document = default_layout()
        self.assertEqual(document["schema_version"], 2)
        self.assertEqual(document["active_tab"], "command")
        self.assertEqual([tab["id"] for tab in document["tabs"]], ["command", "news", "ai-code", "markets", "zoo-studio"])
        command = document["tabs"][0]
        self.assertEqual(
            [widget["type"] for widget in command["widgets"]],
            ["my_models_hub", "openskills_library", "morning_postcard", "project_decisions", "task_center_live_feed", "airlock_privacy_diff"],
        )
        self.assertEqual(command["widgets"][0]["span"], "2x1")
        self.assertEqual(command["widgets"][1]["span"], "1x1")
        self.assertEqual(command["widgets"][2]["span"], "2x1")
        self.assertEqual(document["tabs"][1]["widgets"][0]["type"], "open_news_engine")
        self.assertEqual(document["tabs"][2]["widgets"][0]["span"], "2x2")
        self.assertEqual(document["tabs"][3]["widgets"][1]["type"], "macro_alpha_delta")
        self.assertEqual(document["tabs"][4]["widgets"][2]["type"], "imageboard_media_remix")

    def test_v1_list_migration_preserves_widget_identity_and_config(self):
        old = [{"id": "mine", "type": "morning_postcard", "title": "My card", "span": "2x1", "config": {"room_id": "x"}, "order": 0}]
        document = migrate_layout(old)
        widget = document["tabs"][0]["widgets"][0]
        self.assertEqual(widget["id"], "mine")
        self.assertEqual(widget["title"], "My card")
        self.assertEqual(widget["config"], {"room_id": "x"})
        self.assertEqual(len(document["tabs"]), 5)

    def test_v1_envelope_migration(self):
        old = {"widgets": [{"id": "mine", "type": "project_decisions", "title": "Pinned", "span": 2, "config": {}, "order": 0}]}
        document = migrate_layout(old)
        self.assertEqual(document["tabs"][0]["widgets"][0]["span"], "2x1")

    def test_custom_tab_and_lens_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dashboard_layout.json"
            store = DashboardStore(path)
            document = store.load()
            document["active_tab"] = "custom-1"
            document["lens"] = ["open-source-ai", "macro-markets"]
            document["tabs"].append({"id": "custom-1", "title": "Research", "kind": "custom", "widgets": []})
            store.save(document)
            loaded = store.load()
            self.assertEqual(len(loaded["tabs"]), 6)
            self.assertEqual(loaded["active_tab"], "custom-1")
            self.assertEqual(loaded["lens"], ["open-source-ai", "macro-markets"])
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_rejected_save_keeps_last_valid_document(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dashboard_layout.json"
            store = DashboardStore(path)
            original = store.load()
            store.save(original)
            before = path.read_text(encoding="utf-8")
            with self.assertRaises(ValueError):
                store.save({**original, "schema_version": 1})
            self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_fixed_tab_cannot_be_deleted(self):
        document = default_layout()
        document["tabs"] = document["tabs"][1:]
        with self.assertRaises(ValueError):
            validate_layout(document)

    def test_widget_validation(self):
        document = default_layout()
        bad_widgets = [
            {"id": "", "type": "morning_postcard", "title": "Bad", "span": "1x1", "config": {}},
            {"id": "x", "type": "unknown", "title": "Bad", "span": "1x1", "config": {}},
            {"id": "x", "type": "morning_postcard", "title": "Bad", "span": "3x3", "config": {}},
            {"id": "x", "type": "morning_postcard", "title": "Bad", "span": "1x1", "config": "private"},
        ]
        for widget in bad_widgets:
            with self.subTest(widget=widget):
                candidate = json.loads(json.dumps(document))
                candidate["tabs"][0]["widgets"] = [widget]
                with self.assertRaises(ValueError):
                    validate_layout(candidate)

    def test_corrupt_file_falls_back_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dashboard_layout.json"
            path.write_text("not json", encoding="utf-8")
            os.chmod(path, 0o600)
            store = DashboardStore(path)
            self.assertEqual(store.load(), default_layout())
            self.assertEqual(path.read_text(encoding="utf-8"), "not json")


if __name__ == "__main__":
    unittest.main()
