"""Offline, source-honest Open News analysis and legacy API compatibility."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from open_news import analyze_news
from twin import Twin


class OpenNewsTests(unittest.TestCase):
    def test_headline_is_heuristic_not_verified(self):
        result = analyze_news({"url_or_headline": "Workers union regulation report"})
        self.assertEqual(sum(result["coverage_split"][key] for key in ("left", "center", "right")), 100)
        self.assertEqual(len(result["frames"]), 3)
        self.assertFalse(result["verified_core"]["verified"])
        self.assertIn("COULDNT_VERIFY", result["verified_core"]["text"])
        self.assertTrue(result["inferences"])
        self.assertTrue(result["unverified"])

    def test_url_is_not_fetched(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")):
            result = analyze_news({"url_or_headline": "https://example.com/story"})
        self.assertFalse(result["source_text_available"])
        self.assertEqual(result["submitted_source"], "example.com")
        self.assertFalse(result["audio_brief"]["available"])
        self.assertIn("not fetched", result["method"])
        self.assertIn("anchor", result["audio_brief"]["script"])
        self.assertIn("skeptic", result["audio_brief"]["script"])

    def test_supplied_primary_text_supports_only_extractive_core(self):
        text = "The council approved the grant on Tuesday. Advocates welcomed the decision."
        result = analyze_news({
            "url_or_headline": "Council grant decision",
            "source_text": text,
            "source_kind": "primary",
        })
        self.assertTrue(result["source_text_available"])
        self.assertTrue(result["verified_core"]["verified"])
        self.assertEqual(result["verified_core"]["text"], "The council approved the grant on Tuesday.")
        self.assertIn("The council approved the grant on Tuesday.", result["facts"])
        secondary = analyze_news({"url_or_headline": "Council grant", "source_text": text})
        self.assertFalse(secondary["verified_core"]["verified"])
        self.assertTrue(secondary["facts"])

    def test_verdict_and_legacy_fields(self):
        result = analyze_news({"url_or_headline": "A reported survey"})
        self.assertIn("FACT", result["verdict_card"])
        self.assertIn("INFERENCE", result["verdict_card"])
        self.assertIn("COULDNT_VERIFY", result["verdict_card"])
        self.assertIn("coverage_split", result)

    def test_validation(self):
        for payload in ({}, {"url_or_headline": 42}, {"url_or_headline": "x" * 501},
                        {"url_or_headline": "story", "source_text": 42},
                        {"url_or_headline": "story", "source_text": "x" * 100001},
                        {"url_or_headline": "story", "source_kind": "unknown"}):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    analyze_news(payload)


class OpenNewsTwinTests(unittest.TestCase):
    def test_new_and_legacy_routes_share_analysis(self):
        with tempfile.TemporaryDirectory() as directory:
            twin = Twin(Path(directory) / "projects.sqlite3", transport=lambda *args: ("", {}))
            try:
                payload = {"url_or_headline": "Workers union regulation report"}
                current = twin.act("/api/dashboard/open-news", payload)
                legacy = twin.act("/api/dashboard/analyze-story", payload)
                self.assertEqual(current["coverage_split"], legacy["coverage_split"])
                self.assertIn("comparative_headlines", legacy)
                self.assertIn("de_spinned_receipt", legacy)
                self.assertIn("audio_brief", legacy)
            finally:
                twin.close()


if __name__ == "__main__":
    unittest.main()
