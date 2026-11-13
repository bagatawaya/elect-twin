"""Regression contracts for user-facing OpenTwin branding and release labels."""
from pathlib import Path
import unittest


MAC = Path(__file__).resolve().parents[1]
WORKSPACE = MAC.parent


class CodeHygieneTests(unittest.TestCase):
    def test_web_surfaces_do_not_use_retired_product_names(self):
        for root in (MAC / "web", WORKSPACE / "elect-twin-windows" / "web"):
            for path in root.iterdir():
                if path.suffix not in {".html", ".css", ".js", ".svg"}:
                    continue
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("Elect Twin", text, str(path))
                self.assertNotIn("The Zoo Network", text, str(path))

    def test_duplicate_participant_margin_rule_is_removed(self):
        shell = (MAC / "web" / "shell.html").read_text(encoding="utf-8")
        self.assertEqual(shell.count(".participant:first-child{margin-left:0}"), 1)

    def test_native_shells_use_opentwin_050_labels(self):
        app_delegate = (MAC / "native" / "AppDelegate.swift").read_text(encoding="utf-8")
        windows = (WORKSPACE / "elect-twin-windows" / "ElectTwinWin" / "Program.cs").read_text(encoding="utf-8")
        for source in (app_delegate, windows):
            self.assertIn("OpenTwin 0.5.0", source)
            self.assertIn("2026111205", source)
            self.assertNotIn("Elect Twin 0.4.0", source)
            self.assertNotIn("About Elect Twin", source)
        self.assertIn('window.title = "OpenTwin"', app_delegate)
        self.assertIn('Text = "OpenTwin - Internal test build', windows)

    def test_packaging_targets_opentwin_050_arm64(self):
        plist = (MAC / "packaging" / "Info.plist").read_text(encoding="utf-8")
        for marker in (
            "<key>CFBundleShortVersionString</key><string>0.5.0</string>",
            "<key>OpenTwinReleaseVersion</key><string>0.5.0</string>",
            "<key>CFBundleVersion</key><string>2026111205</string>",
            "<key>LSMinimumSystemVersion</key><string>14.0</string>",
        ):
            self.assertIn(marker, plist)
        build = (MAC / "packaging" / "build.sh").read_text(encoding="utf-8")
        self.assertIn("arm64-apple-macos14.0", build)
        self.assertIn("OpenTwin-0.5.0-arm64.dmg", build)
        self.assertNotIn("OpenTwin-0.4.1-arm64.dmg", build)

    def test_packaging_bundles_openskills_catalog(self):
        build = (MAC / "packaging" / "build.sh").read_text(encoding="utf-8")
        self.assertIn('--add-data "$ROOT/openskills_v2.json:."', build)

    def test_rooms_web_title_uses_opentwin(self):
        rooms_web = (
            MAC / "rooms-reference" / "Elect Twin Rooms.app" / "Contents" /
            "Resources" / "server" / "_internal" / "web" / "index.html"
        ).read_text(encoding="utf-8")
        self.assertIn("<title>OpenTwin · Rooms</title>", rooms_web)
        self.assertNotIn("<title>Elect Twin", rooms_web)


if __name__ == "__main__":
    unittest.main()
