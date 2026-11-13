"""Deterministic parallel fan-out governance and collision tests."""
import unittest

from swarm_governance import evaluate_swarm


class SwarmGovernanceTests(unittest.TestCase):
    def test_independent_research_notifies(self):
        result = evaluate_swarm({
            "prompt": "Research these tickers independently",
            "targets": ["$NVDA", "$BTC", "$AAPL"],
            "swarm_policy": "notify_accept",
            "tier": "free",
        })
        self.assertTrue(result["recommend"])
        self.assertTrue(result["requires_acceptance"])
        self.assertFalse(result["auto_activate"])
        self.assertEqual(result["worker_count"], 3)
        self.assertEqual(result["worst_case_cost_usd"], 0.0)
        self.assertGreater(result["estimated_speedup"], 1.0)

    def test_targets_are_extracted_from_prompt(self):
        result = evaluate_swarm({
            "prompt": "Compare https://a.example and https://b.example independently",
            "tier": "free",
        })
        self.assertTrue(result["recommend"])
        self.assertEqual(result["worker_count"], 2)

    def test_shared_file_collision_suppresses_swarm(self):
        result = evaluate_swarm({
            "prompt": "Edit these files sequentially",
            "targets": ["a.py", "b.py"],
            "shared_paths": ["a.py"],
            "swarm_policy": "auto_optimize",
        })
        self.assertFalse(result["recommend"])
        self.assertFalse(result["auto_activate"])
        self.assertIn("shared_path:a.py", result["collisions"])
        self.assertIn("sequential_or_write_intent", result["collisions"])

    def test_shared_state_suppresses_swarm(self):
        result = evaluate_swarm({
            "prompt": "Research two independent URLs",
            "targets": ["https://a.example", "https://b.example"],
            "shared_state": True,
        })
        self.assertFalse(result["recommend"])
        self.assertIn("shared_state", result["collisions"])

    def test_auto_optimize_activates_only_within_budget(self):
        payload = {
            "prompt": "Compare two URLs independently",
            "targets": ["https://a.example", "https://b.example"],
            "swarm_policy": "auto_optimize",
            "budget_cap_usd": 1,
            "cost_per_worker_usd": 0.25,
            "tier": "paid",
            "external_write": True,
        }
        result = evaluate_swarm(payload)
        self.assertTrue(result["auto_activate"])
        self.assertTrue(result["external_write_requires_approval"])
        self.assertEqual(result["worst_case_cost_usd"], 0.5)
        result = evaluate_swarm({**payload, "budget_cap_usd": 0.25})
        self.assertFalse(result["auto_activate"])
        self.assertFalse(result["recommend"])
        self.assertIn("budget_exceeded", result["reasons"])

    def test_sequential_single_file_edit_stays_single_agent(self):
        result = evaluate_swarm({
            "prompt": "Edit app.js and then run its tests",
            "targets": ["app.js"],
            "swarm_policy": "auto_optimize",
        })
        self.assertFalse(result["recommend"])
        self.assertEqual(result["worker_count"], 1)

    def test_validation(self):
        bad_payloads = [
            {"prompt": ""},
            {"prompt": "x" * 20001},
            {"prompt": "x", "swarm_policy": "bad"},
            {"prompt": "x", "targets": ["a"] * 33},
            {"prompt": "x", "targets": "not-a-list"},
            {"prompt": "x", "shared_paths": [1]},
            {"prompt": "x", "budget_cap_usd": True},
            {"prompt": "x", "cost_per_worker_usd": float("nan")},
            {"prompt": "x", "budget_cap_usd": -1},
        ]
        for payload in bad_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    evaluate_swarm(payload)


if __name__ == "__main__":
    unittest.main()
