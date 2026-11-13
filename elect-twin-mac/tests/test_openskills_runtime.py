"""FTS5 OpenSkills discovery, prompt bundles, learning, and store isolation."""
import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from openskills import OpenSkillsStore
from twin import Twin


def manifest(skill_id, title, summary, *, deprecated=False, guild="⚡ Code & Architecture"):
    return {
        "header": {
            "skill_id": "openskill:" + skill_id,
            "branded_title": "OpenSkill · " + title,
            "guild": guild,
            "summary_140": summary,
            "trigger_keywords": summary.lower().split(),
            "recommended_model_tier": "deep_reasoning",
            "parallel_safe": True,
        },
        "builder_instructions": "Builder for " + title,
        "challenger_rubric": {"role": "Model Slot B (Challenger)", "checks": ["Challenge " + title]},
        "verification_contract": {"fact_inference_separation": True, "abstention": "COULDNT_VERIFY", "banned_phrases": ["delve"], "user_learned_rules": []},
        "content_basis": "source_prompt",
        "deprecated": deprecated,
        "provenance": {"runtime_verified": False},
        "manifest_sha256": "a" * 64,
    }


class OpenSkillsRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(self.temporary.name)
        artifact = {
            "schema": "openskill-v2",
            "source_count": 3,
            "active_count": 2,
            "manifests": [
                manifest("security", "Security Architecture", "security architecture audit"),
                manifest("research", "Source Research", "research public evidence", guild="📰 Research & De-Spin"),
                manifest("old", "Deprecated Skill", "security old", deprecated=True),
            ],
        }
        self.catalog = root / "catalog.json"
        self.catalog.write_text(json.dumps(artifact), encoding="utf-8")
        self.projects = sqlite3.connect(root / "projects.sqlite3")
        self.store = OpenSkillsStore(root / "openskills.sqlite3", self.projects, self.catalog)

    def tearDown(self):
        self.store.close()
        self.projects.close()
        self.temporary.cleanup()

    def test_search_returns_discovery_only_and_hides_deprecated(self):
        rows = self.store.search("security architecture", limit=5)
        self.assertEqual([row["skill_id"] for row in rows], ["openskill:security"])
        self.assertNotIn("builder_instructions", rows[0])
        self.assertEqual(rows[0]["id"], "openskill:security")
        self.assertEqual(rows[0]["name"], "OpenSkill · Security Architecture")
        self.assertNotIn("openskill:old", json.dumps(self.store.search("security")))

    def test_empty_query_browses_and_filters_guild(self):
        rows = self.store.search("", guild="📰 Research & De-Spin")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["skill_id"], "openskill:research")

    def test_optimize_returns_only_selected_playbooks(self):
        matches = self.store.search("security architecture")
        bundle = self.store.optimize("security architecture", [matches[0]["skill_id"]])
        self.assertEqual(len(bundle["selected"]), 1)
        self.assertIn("builder_instructions", bundle["selected"][0])
        self.assertIn("Builder for Security Architecture", bundle["static_system_prefix"])
        self.assertIn("Challenge Security Architecture", bundle["challenger_prefix"])

    def test_learned_rules_are_bounded_and_private(self):
        result = self.store.learn("Always separate observed facts from inference.")
        self.assertEqual(result["rule_count"], 1)
        rows = self.store.search("security")
        self.assertNotIn("Always separate", json.dumps(rows))
        bundle = self.store.optimize("security", ["openskill:security"])
        self.assertEqual(bundle["learned_rules"], ["Always separate observed facts from inference."])
        self.assertEqual(bundle["selected"][0]["verification_contract"]["user_learned_rules"], bundle["learned_rules"])
        with self.assertRaises(ValueError):
            self.store.learn("Always separate observed facts from inference.")
        for invalid in ("", "x" * 501, 42):
            with self.assertRaises(ValueError):
                self.store.learn(invalid)

    def test_repeat_local_search_is_fast(self):
        self.store.search("security")
        started = time.perf_counter()
        for _ in range(20):
            self.store.search("security")
        elapsed_ms = (time.perf_counter() - started) * 1000 / 20
        self.assertLess(elapsed_ms, 50)

    def test_invalid_queries_and_ids(self):
        for query, guild, limit in ((42, "", 10), ("x", "", 0), ("x", "", 21), ("x", 42, 10)):
            with self.assertRaises(ValueError):
                self.store.search(query, guild=guild, limit=limit)
        with self.assertRaises(ValueError):
            self.store.optimize("x", "not-a-list")
        with self.assertRaises(ValueError):
            self.store.optimize("x", ["openskill:missing"])


class OpenSkillsTwinIntegrationTests(unittest.TestCase):
    def test_twin_search_and_preview_resolve_openskill(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            twin = Twin(Path(directory) / "projects.sqlite3", transport=lambda *args: ("", {}))
            try:
                result = twin.act("/api/skills/search", {"query": "security architecture"})
                self.assertTrue(result["skills"])
                skill = result["skills"][0]
                self.assertNotIn("builder_instructions", skill)
                project = twin.act("/api/projects", {"name": "Local", "goal": "Test"})
                preview = twin.act("/api/preview", {
                    "project_id": project["id"], "kind": "text", "provider": "openai", "model": "fixture",
                    "prompt": "Review architecture", "skill_ids": [skill["id"]],
                })
                self.assertIn("SOURCE PLAYBOOK", preview["context"])
            finally:
                twin.close()


if __name__ == "__main__":
    unittest.main()
