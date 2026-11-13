"""Regression tests for the dependency-free OpenZoo procedural SVG studio."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import renderer


def v1(**changes):
    spec = {
        "agent": "SVG-Architect",
        "title": "A Small Idea",
        "nodes": ["Question", "Test", "Share"],
        "palette": "midnight",
    }
    spec.update(changes)
    return spec


def v2(template, **fields):
    spec = {
        "agent": "SVG-Architect",
        "title": "Studio Specimen",
        "template": template,
        "palette": "porcelain",
    }
    spec.update(fields)
    return spec


def comic(**changes):
    spec = v2("comic_strip", panels=[
        {"stamp": "robot", "text": "I made a vector!", "caption": "THE IDEA"},
        {"stamp": "owl", "text": "Show the receipt.", "caption": "THE REVIEW"},
    ])
    spec.update(changes)
    return spec


def pixel(**changes):
    spec = v2("pixel_avatar", pixels=[
        "................",
        ".....BBBBBB.....",
        "....BHHHHHHB....",
        "...BHHHHHHHHB...",
        "..BHHHHHHHHHHB..",
        "..BHHHHHHHHHHB..",
        "..BHHHHHHHHHHB..",
        "..BHHHHHHHHHHB..",
        "...BHHHHHHHHB...",
        "....BHHHHHHB....",
        ".....BBBBBB.....",
        "................",
        "................",
        "................",
        "................",
        "................",
    ], legend={"B": "#172033", "H": "#C2653C"})
    spec.update(changes)
    return spec


class RendererV1ContractTests(unittest.TestCase):
    """The twelve v1/security invariants stated in the SVG Studio brief."""

    def test_01_default_flowchart_renders_valid_svg(self):
        svg = renderer.render(v1())
        self.assertTrue(svg.startswith("<svg "))
        self.assertIn('viewBox="0 0 720 490"', svg)
        self.assertIn('class="svg-studio template-flowchart"', svg)
        for label in ("Question", "Test", "Share"):
            self.assertIn(label, svg)
        self.assertEqual(svg.count('class="flow-node"'), 3)

    def test_02_identical_specs_are_byte_deterministic(self):
        first = renderer.render(v1())
        second = renderer.render(v1())
        self.assertEqual(first, second)
        self.assertEqual(hashlib.sha256(first.encode("ascii")).hexdigest(),
                         hashlib.sha256(second.encode("ascii")).hexdigest())

    def test_03_text_is_ascii_and_xml_escaped(self):
        svg = renderer.render(v1(title='<A & "B"> 😊', nodes=["'<node>&"]))
        self.assertTrue(svg.isascii())
        self.assertIn("&lt;A &amp; &quot;B&quot;&gt; &#128522;", svg)
        self.assertIn("&apos;&lt;node&gt;&amp;", svg)
        self.assertNotIn("😊", svg)

    def test_04_active_content_never_reaches_svg(self):
        svg = renderer.render(v1(
            agent='<script>alert(1)</script>',
            title='<image href="x">',
            nodes=['<foreignObject>bad</foreignObject>'],
        ))
        lowered = svg.lower()
        for forbidden in ("<script", "<image", "<foreignobject", "href="):
            self.assertNotIn(forbidden, lowered)

    def test_05_v1_rejects_unknown_keys(self):
        with self.assertRaisesRegex(ValueError, "unknown"):
            renderer.render(v1(template="flowchart", surprise=True))
        with self.assertRaisesRegex(ValueError, "unknown"):
            renderer.render(v1(remix_of="a" * 64))

    def test_06_v1_requires_every_contract_field(self):
        for key in ("agent", "title", "nodes", "palette"):
            with self.subTest(key=key):
                spec = v1()
                del spec[key]
                with self.assertRaisesRegex(ValueError, key):
                    renderer.render(spec)

    def test_07_v1_nodes_are_a_bounded_string_list(self):
        for nodes in ([], "Question", ["ok", 3], ["ok"] * 7):
            with self.subTest(nodes=nodes):
                with self.assertRaises(ValueError):
                    renderer.render(v1(nodes=nodes))

    def test_08_palette_must_be_one_of_the_fixed_palettes(self):
        with self.assertRaisesRegex(ValueError, "palette"):
            renderer.render(v1(palette="url(javascript:alert(1))"))
        self.assertEqual(len(renderer.PALETTES), 8)
        self.assertIn("porcelain", renderer.PALETTES)

    def test_09_cli_rejects_stdin_over_8192_bytes(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            result = subprocess.run(
                [sys.executable, str(ROOT / "renderer.py"), directory],
                input=b" " * 8193, capture_output=True, timeout=10,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn(b"8192", result.stderr)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_10_cli_rejects_invalid_json_without_artifacts(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            result = subprocess.run(
                [sys.executable, str(ROOT / "renderer.py"), directory],
                input=b'{not json', capture_output=True, timeout=10,
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_11_writes_are_content_addressed_and_mode_0600(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            result = renderer.write_artifact(v1(), directory)
            digest = hashlib.sha256(renderer.render(v1()).encode("ascii")).hexdigest()
            self.assertEqual(result["sha256"], digest)
            for suffix in (".svg", ".json"):
                path = Path(directory) / (digest + suffix)
                self.assertTrue(path.is_file())
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            again = renderer.write_artifact(v1(), directory)
            self.assertEqual(again, result)

    def test_12_nofollow_write_never_overwrites_a_symlink(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            digest = hashlib.sha256(renderer.render(v1()).encode("ascii")).hexdigest()
            target = Path(directory) / "victim.txt"
            target.write_text("do not overwrite", encoding="utf-8")
            os.symlink(target.name, Path(directory) / (digest + ".svg"))
            with self.assertRaises(OSError):
                renderer.write_artifact(v1(), directory)
            self.assertEqual(target.read_text(encoding="utf-8"), "do not overwrite")


class RendererV2Tests(unittest.TestCase):
    def test_all_seven_templates_render(self):
        specs = {
            "flowchart": v2("flowchart", nodes=["One", "Two"]),
            "comic_strip": comic(),
            "trading_card": v2("trading_card", symbol="ZOO", horizon="14D", conviction=72,
                               entry=100, target=118, stop=92, stamp="bull"),
            "versus_poster": v2("versus_poster",
                                left={"name": "Bull", "stamp": "bull", "crowd": 61},
                                right={"name": "Bear", "stamp": "bear", "crowd": 39}),
            "greentext_meme": v2("greentext_meme", stamp="robot",
                                 lines=[">be local agent", ">render art for zero dollars"]),
            "infographic": v2("infographic",
                              bars=[{"label": "Local", "value": 100}, {"label": "Paid API", "value": 0}],
                              notes=["Deterministic vectors", "No network calls"]),
            "pixel_avatar": pixel(),
        }
        for name, spec in specs.items():
            with self.subTest(template=name):
                svg = renderer.render(spec)
                self.assertIn('class="svg-studio template-' + name + '"', svg)
                self.assertTrue(svg.isascii())

    def test_pixel_avatar_maps_ascii_to_crisp_rects(self):
        svg = renderer.render(pixel())
        self.assertIn('shape-rendering="crispEdges"', svg)
        self.assertIn('class="pixel-avatar-canvas"', svg)
        expected = sum(cell != "." for row in pixel()["pixels"] for cell in row)
        self.assertEqual(svg.count('class="pixel-cell"'), expected)
        self.assertIn('fill="#172033"', svg)
        self.assertIn('fill="#C2653C"', svg)

    def test_pixel_avatar_accepts_direct_color_grid_and_remix(self):
        spec = pixel(pixels=[["#AABBCC"] * 24 for _ in range(24)],
                     legend={"X": "#000000"}, remix_of="b" * 64)
        svg = renderer.render(spec)
        self.assertEqual(svg.count('class="pixel-cell"'), 24 * 24)
        self.assertIn('fill="#AABBCC"', svg)
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            result = renderer.write_artifact(spec, directory)
            receipt = json.loads(Path(result["json"]).read_text(encoding="utf-8"))
            self.assertEqual(receipt["spec"], spec)
            self.assertEqual(receipt["remix_of"], "b" * 64)

    def test_pixel_avatar_rejects_ragged_grids_and_unsafe_colors(self):
        invalid_specs = [
            pixel(pixels=["..", "."]),
            pixel(pixels=["<script", "......"]),
            pixel(legend={"B": "url(javascript:alert(1))"}),
            pixel(pixels=[["red"] * 16 for _ in range(16)]),
        ]
        for spec in invalid_specs:
            with self.subTest(spec=spec):
                with self.assertRaises(ValueError):
                    renderer.render(spec)

    def test_cheatsheet_has_one_renderable_example_per_template(self):
        path = ROOT / "tools" / "free_cloud_agents" / "svg_studio_cheatsheet.md"
        markdown = path.read_text(encoding="utf-8")
        examples = [json.loads(block) for block in
                    re.findall(r"```json\s*(.*?)```", markdown, re.S)]
        self.assertEqual({example.get("template") for example in examples}, set(renderer.TEMPLATES))
        self.assertEqual(len(examples), 7)
        for example in examples:
            with self.subTest(template=example["template"]):
                self.assertTrue(renderer.render(example).startswith("<svg "))

    def test_comic_supports_three_panel_bubbles_captions_and_stamps(self):
        svg = renderer.render(comic(panels=[
            {"stamp": "robot", "text": "One", "caption": "FIRST"},
            {"stamp": "owl", "text": "Two", "caption": "SECOND"},
            {"stamp": "crown", "text": "Three", "caption": "THIRD"},
        ]))
        self.assertEqual(svg.count('class="comic-panel"'), 3)
        self.assertEqual(svg.count('class="speech-bubble"'), 3)
        self.assertEqual(svg.count('class="panel-caption"'), 3)
        for stamp in ("robot", "owl", "crown"):
            self.assertIn("stamp-" + stamp, svg)

    def test_trading_card_horizons_badges_and_conviction(self):
        for horizon in ("7D", "14D", "30D"):
            with self.subTest(horizon=horizon):
                svg = renderer.render(v2("trading_card", symbol="ZOO", horizon=horizon,
                                         conviction=83, entry=100, target=120, stop=90, stamp="chart"))
                self.assertIn(horizon + " CONVICTION", svg)
                for badge in ("ENTRY 100", "TARGET 120", "STOP 90"):
                    self.assertIn(badge, svg)
                self.assertIn('class="conviction-meter"', svg)
        with self.assertRaisesRegex(ValueError, "horizon"):
            renderer.render(v2("trading_card", symbol="ZOO", horizon="1Y", conviction=50,
                               entry=1, target=2, stop=0.5))

    def test_versus_poster_has_two_sides_and_crowd_meters(self):
        svg = renderer.render(v2("versus_poster",
                                 left={"name": "Owl", "stamp": "owl", "crowd": 55},
                                 right={"name": "Robot", "stamp": "robot", "crowd": 45}))
        self.assertIn('class="versus-left"', svg)
        self.assertIn('class="versus-right"', svg)
        self.assertIn(">VS</text>", svg)
        self.assertEqual(svg.count('class="crowd-meter"'), 2)
        self.assertIn('width="275"', svg)
        self.assertIn('width="225"', svg)

    def test_greentext_and_infographic_content(self):
        meme = renderer.render(v2("greentext_meme", stamp="shield",
                                  lines=["be me", ">already green"]))
        self.assertIn("/b/zoo", meme)
        self.assertIn("&gt;be me", meme)
        self.assertIn("&gt;already green", meme)
        info = renderer.render(v2("infographic",
                                  bars=[{"label": "Vectors", "value": 75}], notes=["A note"]))
        self.assertIn("75%", info)
        self.assertIn('class="infographic-bar"', info)
        self.assertIn("A note", info)

    def test_all_eight_stamps_are_composable(self):
        for stamp in ("robot", "bull", "bear", "owl", "crown", "bolt", "chart", "shield"):
            with self.subTest(stamp=stamp):
                svg = renderer.render(v2("greentext_meme", stamp=stamp, lines=[">stamp test"]))
                self.assertIn('class="vector-stamp stamp-' + stamp + '"', svg)
        with self.assertRaisesRegex(ValueError, "stamp"):
            renderer.render(v2("greentext_meme", stamp="dragon", lines=[">no"]))

    def test_receipt_stores_exact_spec_and_remix_provenance(self):
        parent = "a" * 64
        spec = comic(remix_of=parent)
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            result = renderer.write_artifact(spec, directory)
            metadata = json.loads(Path(result["json"]).read_text(encoding="utf-8"))
            self.assertEqual(metadata["spec"], spec)
            self.assertEqual(metadata["remix_of"], parent)
            self.assertEqual(metadata["sha256"], result["sha256"])
            self.assertEqual(metadata["version"], 2)

    def test_v2_rejects_unknown_template_and_malformed_fields(self):
        with self.assertRaisesRegex(ValueError, "template"):
            renderer.render(v2("animation"))
        with self.assertRaises(ValueError):
            renderer.render(comic(panels=[]))
        with self.assertRaises(ValueError):
            renderer.render(v2("infographic", bars=[{"label": "bad", "value": 101}], notes=[]))
        with self.assertRaisesRegex(ValueError, "remix_of"):
            renderer.render(comic(remix_of="../secret"))
        for malformed in ({"template": []}, {"palette": []}):
            with self.subTest(malformed=malformed):
                spec = comic(**malformed)
                with self.assertRaises(ValueError):
                    renderer.render(spec)

    def test_v2_active_content_is_escaped_everywhere(self):
        svg = renderer.render(comic(panels=[
            {"stamp": "robot", "text": '<script>alert(1)</script>', "caption": '<image href="x">'},
            {"stamp": "owl", "text": "safe", "caption": "safe"},
        ], title='<foreignObject>'))
        lowered = svg.lower()
        for forbidden in ("<script", "<image", "<foreignobject", "href="):
            self.assertNotIn(forbidden, lowered)

    def test_cli_emits_machine_readable_receipt(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            result = subprocess.run(
                [sys.executable, str(ROOT / "renderer.py"), directory],
                input=json.dumps(v1()).encode("utf-8"), capture_output=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
            receipt = json.loads(result.stdout)
            self.assertRegex(receipt["sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(Path(receipt["svg"]).is_file())
            self.assertTrue(Path(receipt["json"]).is_file())


class CreatorCornerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")

    def test_four_inline_renderer_samples(self):
        for template in ("comic_strip", "trading_card", "greentext_meme", "pixel_avatar"):
            with self.subTest(template=template):
                self.assertIsNotNone(re.search(
                    r'<figure class="creator-studio-sample" data-template="' + template + r'"[^>]*>.*?</figure>',
                    self.html, re.S))

    def test_each_sample_has_receipt_and_three_human_vote_buttons(self):
        figures = re.findall(r'<figure class="creator-studio-sample".*?</figure>', self.html, re.S)
        self.assertEqual(len(figures), 4)
        for figure in figures:
            receipts = set(re.findall(r'data-receipt="([0-9a-f]{64})"', figure))
            self.assertEqual(len(receipts), 1)
            for vote, label in (("appreciate", "Appreciate"), ("curious", "Curious"), ("remix", "Remix")):
                self.assertIn('data-studio-vote="' + vote + '"', figure)
                self.assertIn(label, figure)
            self.assertIn("<svg", figure)
            self.assertNotIn("href=", figure)

    def test_pixel_showcase_is_not_a_live_syndicate(self):
        match = re.search(r'<article class="creator-studio-showcase-card".*?</article>', self.html, re.S)
        self.assertIsNotNone(match)
        card = match.group(0) if match else ""
        self.assertIn('data-studio-only="true"', card)
        self.assertNotIn("data-syndicate-index", card)
        self.assertIn('data-template="pixel_avatar"', card)
        self.assertIn("Creator Crews (3)", self.html)

    def test_vote_behavior_is_local_and_has_no_network_calls(self):
        script = (ROOT / "site" / "creator-studio.js").read_text(encoding="utf-8")
        self.assertIn("localStorage", script)
        self.assertIn("data-studio-vote", script)
        self.assertIn("event.stopPropagation()", script)
        self.assertNotRegex(script, r"\bfetch\s*\(|XMLHttpRequest|https?://")


if __name__ == "__main__":
    unittest.main()
