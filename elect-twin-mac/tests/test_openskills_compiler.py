"""OpenSkills v2 deterministic compiler tests."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.openskills_compiler import GUILDS, compile_catalog, manifest_for


class OpenSkillsCompilerTests(unittest.TestCase):
    def test_branding_source_prompt_and_verification_contract(self):
        row = {
            "id": "one",
            "title": "Electri Decision Brief",
            "description": "Compare plans and negotiate tradeoffs",
            "promptText": "Compare evidence",
            "license": {"name": "MIT", "confidence": "file-verified"},
            "categories": ["strategy"],
        }
        manifest = manifest_for(row)
        self.assertTrue(manifest["header"]["branded_title"].startswith("OpenSkill · "))
        self.assertNotIn("Electri", manifest["header"]["branded_title"])
        self.assertEqual(manifest["content_basis"], "source_prompt")
        self.assertEqual(len(manifest["manifest_sha256"]), 64)
        self.assertIn("Compare evidence", manifest["builder_instructions"])
        self.assertTrue(manifest["verification_contract"]["fact_inference_separation"])
        self.assertEqual(manifest["verification_contract"]["abstention"], "COULDNT_VERIFY")
        self.assertEqual(manifest["verification_contract"]["user_learned_rules"], [])

    def test_metadata_only_does_not_invent_source_procedure(self):
        manifest = manifest_for({"id": "two", "title": "Research", "description": "Read sources", "promptText": None})
        self.assertEqual(manifest["content_basis"], "metadata_only")
        self.assertIn("Source procedure unavailable", manifest["builder_instructions"])
        self.assertIn("COULDNT_VERIFY", manifest["verification_contract"]["abstention"])

    def test_count_deprecated_and_determinism(self):
        rows = [
            {"id": str(index), "title": "Research", "description": "Research sources", "promptText": "Read", "deprecated": index == 1}
            for index in range(3)
        ]
        first = compile_catalog(rows)
        second = compile_catalog(rows)
        self.assertEqual(first, second)
        self.assertEqual(first["source_count"], 3)
        self.assertEqual(first["active_count"], 2)
        self.assertEqual(len(first["manifests"]), 3)

    def test_guild_model_tier_and_parallel_safety(self):
        security = manifest_for({"id": "sec", "title": "Security architecture review", "description": "Red-team SQL forensic review"})
        self.assertEqual(security["header"]["recommended_model_tier"], "deep_reasoning")
        edit = manifest_for({"id": "edit", "title": "Edit shared file", "description": "Write and deploy shared state"})
        self.assertFalse(edit["header"]["parallel_safe"])
        research = manifest_for({"id": "read", "title": "Research independent sources", "description": "Read and compare public evidence"})
        self.assertTrue(research["header"]["parallel_safe"])

    def test_local_catalog_has_real_scale_and_all_guilds(self):
        source = ROOT / "scratch" / "skillspilot-source" / "skills.json"
        rows = json.loads(source.read_text(encoding="utf-8"))
        artifact = compile_catalog(rows)
        self.assertEqual(artifact["source_count"], 1501)
        self.assertEqual(artifact["active_count"], 1462)
        self.assertEqual({m["header"]["guild"] for m in artifact["manifests"]}, set(GUILDS))
        self.assertGreaterEqual(sum(m["content_basis"] == "source_prompt" for m in artifact["manifests"]), 300)
        for manifest in artifact["manifests"]:
            self.assertLessEqual(len(manifest["header"]["summary_140"]), 140)
            self.assertTrue(manifest["manifest_sha256"])


if __name__ == "__main__":
    unittest.main()
