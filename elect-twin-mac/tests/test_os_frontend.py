"""Five-tab OS web-module contracts and executable pure-state behavior."""
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class OSFrontendSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = (WEB / "styles.css").read_text(encoding="utf-8")
        cls.js = (WEB / "app.js").read_text(encoding="utf-8")

    def test_porcelain_accessibility_and_responsive_contracts(self):
        for color in ("#F9F9FB", "#FFFFFF", "#0F172A", "#0F766E"):
            self.assertIn(color, self.css)
        self.assertIn(":focus-visible", self.css)
        self.assertIn("prefers-reduced-motion", self.css)
        self.assertIn("grid-template-columns:1fr", self.css)
        for mode in ("os-scan", "os-split", "os-audio"):
            self.assertIn(mode, self.css)
        self.assertNotIn("@import", self.css)
        self.assertNotIn("fonts.googleapis", self.css)

    def test_application_contracts_and_honest_empty_states(self):
        for tab in ("command", "news", "ai-code", "markets", "zoo-studio"):
            self.assertIn(tab, self.js)
        for widget in ("my_models_hub", "openskills_library", "task_center_live_feed", "open_news_engine",
                       "multimodal_model_tracker", "personal_blind_scorecard", "builder_signal_radar",
                       "macro_alpha_delta", "room_zero_lockbox", "imageboard_media_remix"):
            self.assertIn(widget, self.js)
        for mode in ("auto_optimize", "economy_lock", "frontier_max", "notify_accept"):
            self.assertIn(mode, self.js)
        self.assertIn("osSelectedSkills", self.js)
        self.assertIn("osRouterMode", self.js)
        self.assertIn("osSwarmPolicy", self.js)
        self.assertIn("exact-preview", self.js)
        self.assertIn("INPUT", self.js)
        self.assertIn("TEXTAREA", self.js)
        self.assertIn("SELECT", self.js)
        self.assertIn("enhanceOpenTwinOS", self.js)
        self.assertIn("osEscape", self.js)
        self.assertNotIn("/api/send", self.js)
        self.assertNotIn("SESSION_KEYS", self.js)

    def test_os_enhancer_creates_missing_home_container(self):
        function = self.js.split("async function enhanceOpenTwinOS()", 1)[1].split("function osDashboardClick", 1)[0]
        self.assertIn("document.createElement('section')", function)
        self.assertIn("section.id = 'studio-dashboard'", function)
        self.assertIn("pageEl.appendChild(section)", function)

    def test_injection_preserves_existing_shell_boundaries(self):
        for name in ("shell.html", "index.html"):
            source = (WEB / name).read_text(encoding="utf-8")
            self.assertEqual(source.count('<style id="opentwin-os-styles">'), 1)
            self.assertEqual(source.count('<script id="opentwin-os-script">'), 1)
            self.assertNotIn("/* OPENTWIN_OS_STYLES */", source)
            self.assertNotIn("/* OPENTWIN_OS_SCRIPT */", source)


class OSFrontendStateTests(unittest.TestCase):
    def test_pure_layout_governance_and_empty_state_helpers(self):
        script = r"""
const assert = require('assert');
const os = require(process.argv[1]);
const fixed = [
 {id:'command',title:'Command',kind:'system',widgets:[{id:'a',type:'my_models_hub',title:'A',span:'1x1',config:{},order:0},{id:'b',type:'morning_postcard',title:'B',span:'2x1',config:{},order:1}]},
 {id:'news',title:'News',kind:'system',widgets:[]}
];
let layout = {schema_version:2,active_tab:'command',lens:[],tabs:fixed};
assert.equal(os.osActiveTab(layout).id, 'command');
layout = os.osSelectTab(layout, 'news');
assert.equal(layout.active_tab, 'news');
layout = os.osAddCustomTab(layout, 'Research', 'custom-1');
assert.equal(layout.tabs.length, 3);
layout = os.osRenameCustomTab(layout, 'custom-1', 'Evidence');
assert.equal(layout.tabs[2].title, 'Evidence');
layout = os.osResizeWidget(layout, 'command', 'a');
assert.equal(layout.tabs[0].widgets[0].span, '2x1');
layout = os.osMoveWidget(layout, 'command', 'a', 1);
assert.equal(layout.tabs[0].widgets[1].id, 'a');
let deletion = os.osDeleteWidget(layout, 'command', 'b');
layout = deletion.layout;
assert.equal(layout.tabs[0].widgets.length, 1);
layout = os.osUndoDelete(layout, 'command', deletion.removed);
assert.equal(layout.tabs[0].widgets.length, 2);
let selected = new Set();
selected = os.osToggleSkill(selected, 'openskill:test', true);
assert(selected.has('openskill:test'));
selected = os.osToggleSkill(selected, 'openskill:test', false);
assert(!selected.has('openskill:test'));
assert.equal(os.osRouterLabel({available:true,selected_model:'kimi-k2.8',tier:'fast_economical'}), 'kimi-k2.8 · fast_economical');
assert.equal(os.osRouterLabel({available:false}), 'No connected model for this tier');
assert.equal(os.osSwarmAcceptance({auto_activate:true,external_write_requires_approval:true}, true, false).activated, false);
assert.equal(os.osSwarmAcceptance({requires_acceptance:true,external_write_requires_approval:false}, true, false).activated, true);
assert.equal(os.osNewsMode('split').mode, 'split');
assert.equal(os.osNewsMode('audio').available, false);
assert.deepEqual(os.osModelMetrics({}), {ttft:'—',tokensPerSecond:'—',winRate:'—',savings:'—'});
const escaped = os.osEscape('<img src=x onerror=alert(1)>');
assert(!escaped.includes('<img'));
layout = os.osDeleteCustomTab(layout, 'custom-1').layout;
assert.equal(layout.tabs.length, 2);
console.log(JSON.stringify({ok:true}));
"""
        result = subprocess.run(["node", "-e", script, str(WEB / "app.js")], check=True, capture_output=True, text=True)
        self.assertTrue(json.loads(result.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()
