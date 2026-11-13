"""Offline model-version complexity routing tests."""
import unittest

from model_router import FAMILY_MODELS, route_model


class ModelRouterTests(unittest.TestCase):
    def setUp(self):
        self.kimi = {
            "family": "kimi",
            "connected_models": ["kimi-k2.8", "kimi-k3.1-pro"],
        }

    def test_kimi_routes_copy_to_economy(self):
        result = route_model({**self.kimi, "prompt": "Polish this UI copy"})
        self.assertEqual(result["selected_model"], "kimi-k2.8")
        self.assertEqual(result["tier"], "fast_economical")
        self.assertIn("50%", result["savings_label"])

    def test_kimi_routes_architecture_to_deep_reasoning(self):
        result = route_model({
            **self.kimi,
            "prompt": "Refactor multi-file architecture and audit security",
        })
        self.assertEqual(result["selected_model"], "kimi-k3.1-pro")
        self.assertEqual(result["tier"], "deep_reasoning")

    def test_skill_and_challenger_signals(self):
        result = route_model({
            **self.kimi,
            "prompt": "Review this",
            "recommended_model_tier": "deep_reasoning",
            "room_role": "Challenger",
        })
        self.assertEqual(result["tier"], "deep_reasoning")
        self.assertIn("matched_to_skill_tier", result["reasons"])

    def test_file_depth_selects_deep_reasoning(self):
        result = route_model({**self.kimi, "prompt": "Update the code", "file_count": 4})
        self.assertEqual(result["selected_model"], "kimi-k3.1-pro")

    def test_modes_override_complexity(self):
        prompt = {**self.kimi, "prompt": "Simple summary"}
        self.assertEqual(route_model({**prompt, "mode": "frontier_max"})["selected_model"], "kimi-k3.1-pro")
        self.assertEqual(route_model({**prompt, "mode": "economy_lock"})["selected_model"], "kimi-k2.8")

    def test_disconnected_family_is_honest(self):
        result = route_model({"family": "kimi", "connected_models": [], "prompt": "Summary"})
        self.assertFalse(result["available"])
        self.assertIsNone(result["selected_model"])

    def test_requested_families_have_two_tiers(self):
        self.assertEqual(set(FAMILY_MODELS), {"kimi", "gemini", "claude", "openrouter", "groq", "ollama"})
        for family, tiers in FAMILY_MODELS.items():
            with self.subTest(family=family):
                self.assertEqual(set(tiers), {"fast_economical", "deep_reasoning"})
                self.assertTrue(tiers["fast_economical"])
                self.assertTrue(tiers["deep_reasoning"])

    def test_gemini_selects_connected_version(self):
        result = route_model({
            "family": "gemini",
            "connected_models": ["gemini-2.5-flash", "gemini-2.5-pro"],
            "prompt": "Prove this math identity",
        })
        self.assertEqual(result["selected_model"], "gemini-2.5-pro")

    def test_validation(self):
        for payload in (
            {"prompt": 4},
            {"prompt": "x", "family": "unknown"},
            {"prompt": "x", "mode": "unknown"},
            {"prompt": "x", "connected_models": "kimi"},
            {"prompt": "x", "file_count": True},
            {"prompt": "x", "recommended_model_tier": "unknown"},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    route_model(payload)


if __name__ == "__main__":
    unittest.main()
