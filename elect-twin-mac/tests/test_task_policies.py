"""Twin-level v2 layout and Task Center policy persistence tests."""
import math
import tempfile
import unittest
from pathlib import Path

from twin import Twin


class TaskPolicyAndTwinLayoutTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.twin = Twin(Path(self.temporary.name) / "projects.sqlite3", transport=lambda *args: ("", {}))

    def tearDown(self):
        self.twin.db.close()
        self.twin.zoo.close()
        self.temporary.cleanup()

    def test_twin_returns_and_saves_v2_layout(self):
        document = self.twin.dashboard_layout_v2()
        self.assertEqual(document["schema_version"], 2)
        self.assertEqual(len(document["tabs"]), 5)
        saved = self.twin.save_dashboard_layout(document)
        self.assertEqual(saved["schema_version"], 2)
        self.assertEqual(self.twin.dashboard_layout_v2(), saved)

    def test_legacy_widget_save_migrates(self):
        widgets = [{"id": "legacy", "type": "morning_postcard", "title": "Mine", "span": "1x1", "config": {}, "order": 0}]
        saved = self.twin.save_dashboard_layout(widgets)
        self.assertEqual(saved[0]["id"], "legacy")
        self.assertEqual(self.twin.dashboard_layout_v2()["schema_version"], 2)
        self.assertEqual(self.twin.dashboard_layout_v2()["tabs"][0]["widgets"][0]["id"], "legacy")

    def test_seed_tasks_have_free_swarm_defaults(self):
        for task in self.twin.tasks():
            self.assertEqual(task["swarm_policy"], "notify_accept")
            self.assertEqual(task["budget_cap_usd"], 0.0)
            self.assertIsInstance(task["is_enabled"], bool)
            self.assertIsInstance(task["triggers"], list)

    def test_task_policy_round_trip(self):
        tasks = self.twin.tasks()
        tasks[0]["swarm_policy"] = "auto_optimize"
        tasks[0]["budget_cap_usd"] = 1.25
        saved = self.twin.save_tasks(tasks)
        self.assertEqual(saved[0]["swarm_policy"], "auto_optimize")
        self.assertEqual(saved[0]["budget_cap_usd"], 1.25)
        self.assertEqual(self.twin.tasks()[0]["budget_cap_usd"], 1.25)

    def test_invalid_task_policy_or_budget_rejected(self):
        for policy, budget in (("bad", 0), ("notify_accept", -1), ("notify_accept", True), ("notify_accept", float("nan")), ("notify_accept", 10001)):
            with self.subTest(policy=policy, budget=budget):
                tasks = self.twin.tasks()
                tasks[0]["swarm_policy"] = policy
                tasks[0]["budget_cap_usd"] = budget
                with self.assertRaises(ValueError):
                    self.twin.save_tasks(tasks)


if __name__ == "__main__":
    unittest.main()
