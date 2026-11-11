"""Frontend structure and behavior contracts for the local Zoo experience."""
from pathlib import Path
import json
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def read_source(relative):
    try:
        return (ROOT / relative).read_text()
    except FileNotFoundError:
        return ""


class FrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shell = read_source("web/shell.html")
        cls.projects = read_source("web/index.html")
        cls.zoo_js = read_source("web/zoo.js")
        cls.zoo_css = read_source("web/zoo.css")
        cls.check_js = read_source("tests/check_js.py")

    def test_nine_destinations_separate_collaboration_from_zoo(self):
        match = re.search(r"const pages=\[(.*?)\];", self.shell, re.S)
        self.assertIsNotNone(match, "The shell must declare its page destinations")
        entries = re.findall(r"\['([^']+)','([^']+)','([^']+)'\]", match.group(1)) if match else []
        self.assertEqual([entry[0] for entry in entries], [
            "home", "models", "projects", "twin", "people", "collaboration",
            "challenges", "following", "zoo",
        ])
        labels = {entry[0]: entry[1] for entry in entries}
        self.assertEqual(labels.get("collaboration"), "Collaboration")
        self.assertEqual(labels.get("zoo"), "The Zoo Network")
        self.assertRegex(self.shell, r"function collaboration\(\)")
        views = re.search(r"const views=\{([^}]+)\}", self.shell)
        self.assertIsNotNone(views)
        self.assertIn("collaboration", views.group(1))
        self.assertIn("zoo", views.group(1))

    def test_real_rooms_gateway_remains_in_collaboration(self):
        function = self.shell.split("function collaboration()", 1)[-1].split("function challenges()", 1)[0]
        for marker in ("Shared planning room", "deterministic", "data-room=\"jay\"", "data-room=\"alex\""):
            self.assertIn(marker, function)
        self.assertIn("openRoom", self.shell)

    def test_zoo_source_is_mirrored_inline_for_existing_document_only_routes(self):
        self.assertTrue(self.zoo_js, "web/zoo.js is required")
        self.assertTrue(self.zoo_css, "web/zoo.css is required")
        self.assertIn('<style id="zoo-styles">\n' + self.zoo_css + '\n</style>', self.shell)
        self.assertIn('<script id="zoo-script">\n' + self.zoo_js + '\n</script>', self.shell)
        self.assertIn("if(page==='zoo')await loadZooState()", self.shell)
        self.assertIn("if(page==='zoo')enhanceZooPage()", self.shell)

    def test_feed_exposes_required_order_categories_and_provenance(self):
        for marker in (
            "Top Thread", "Room Zero", "Free for All", "Let’s Collaborate",
            "Human Challenges", "Ideas & Experiments", "What’s the deal with people?",
            "Simulated example", "Stored on this Mac · not published",
        ):
            self.assertIn(marker, self.zoo_js)
        self.assertLess(self.zoo_js.index("zooTopSection"), self.zoo_js.index("zooRoomSection"))
        self.assertLess(self.zoo_js.index("zooRoomSection"), self.zoo_js.index("zooThreadIndex"))
        self.assertIn("is_top", self.zoo_js)
        self.assertIn("category_id", self.zoo_js)

    def test_mutations_use_server_routes_counts_and_refresh(self):
        for route in (
            "/api/zoo/state", "/api/zoo/thread", "/api/zoo/post",
            "/api/zoo/reaction", "/api/zoo/reaction/delete",
            "/api/zoo/follow", "/api/zoo/unfollow",
        ):
            self.assertIn(route, self.zoo_js)
        for reaction in ("appreciate", "curious", "idea"):
            self.assertIn(reaction, self.zoo_js)
        self.assertIn("reaction_counts", self.zoo_js)
        self.assertIn("aria-pressed", self.zoo_js)
        self.assertGreaterEqual(self.zoo_js.count("await refresh()"), 4)
        self.assertNotRegex(self.zoo_js, r"reaction_counts\s*\+\+|reaction_counts[^\n]*\+=\s*1")

    def test_accessible_zoo_actions_and_named_scrollable_profile_dialog(self):
        for action in (
            "data-zoo-agent", "data-zoo-reaction", "data-zoo-follow",
            "data-zoo-category", "data-zoo-thread-form", "data-zoo-post-form",
        ):
            self.assertIn(action, self.zoo_js)
        for function in ("function zoo()", "function zooAgentProfile(id)", "function enhanceZooPage()"):
            self.assertIn(function, self.zoo_js)
        self.assertIn('id="zoo-agent-dialog"', self.shell)
        self.assertIn('aria-labelledby="zoo-agent-title"', self.shell)
        self.assertIn('aria-describedby="zoo-agent-description"', self.shell)
        self.assertRegex(self.zoo_css, r"#zoo-agent-dialog[^}]*overflow\s*:\s*auto")

    def test_profile_contains_boundaries_and_detail_not_feed_statistics(self):
        for field in ("identity_origin", "execution_mode", "connectivity"):
            self.assertIn(field, self.zoo_js)
        for heading in ("Statistics", "Permissions", "Activity", "Budget"):
            self.assertIn(heading, self.zoo_js)
        self.assertIn("External connectivity unavailable/unverified", self.zoo_js)
        self.assertIn("zooAgentProfile", self.zoo_js)

    def test_original_accessible_figurine_portraits_have_variants(self):
        self.assertIn("function zooPortrait", self.zoo_js)
        self.assertIn("<svg", self.zoo_js)
        self.assertIn('role="img"', self.zoo_js)
        self.assertIn("aria-label", self.zoo_js)
        self.assertIn("viewBox=\"0 0 120 140\"", self.zoo_js)
        for shape in ("<path", "<rect", "<circle", "<polygon"):
            self.assertIn(shape, self.zoo_js)
        self.assertGreaterEqual(self.zoo_js.count("zoo-cap-"), 4)
        self.assertNotRegex(self.zoo_js, r"<img|https?://|url\(")

    def test_local_path_routes_and_twin_navigation_are_enhanced(self):
        for route in ("/zoo/rooms/", "/zoo/categories/", "/zoo/threads/", "/zoo/agents/"):
            self.assertIn(route, self.zoo_js)
        self.assertIn("location.pathname", self.shell)
        self.assertIn("data-page=\"twin\"", self.zoo_js)
        self.assertIn("popstate", self.zoo_js)

    def test_project_workspace_has_working_zoo_navigation(self):
        self.assertIn('id="open-zoo"', self.projects)
        self.assertIn("The Zoo Network", self.projects)
        self.assertRegex(self.projects, r"open-zoo['\"]\)\.onclick=.*?/zoo#token=")

    def test_responsive_flat_accessible_styles(self):
        for pattern in (
            r":focus-visible", r"prefers-reduced-motion\s*:\s*reduce",
            r"@media\s*\(max-width\s*:\s*760px\)", r"overflow-wrap\s*:\s*anywhere",
            r"minmax\(0\s*,\s*1fr\)", r"flex-wrap\s*:\s*wrap",
        ):
            self.assertRegex(self.zoo_css, pattern)
        self.assertNotRegex(self.zoo_css, r"gradient\(|box-shadow|@import|https?://")

    def test_no_unsupported_public_live_or_federated_claims(self):
        combined = self.zoo_js + "\n" + self.zoo_css
        for pattern in (
            r"\bpublic\s+(?:feed|network|publishing)\b",
            r"\blive\s+(?:agents?|feed|activity)\b",
            r"\bfederated\s+(?:network|feed|agents?)\b",
            r"\btrending\b", r"\bautonomous\s+agents?\b",
            r"\bpeer-to-peer\s+resilience\b", r"\bagent-led\s+governance\b",
        ):
            self.assertNotRegex(combined, pattern)

    def test_javascript_checker_covers_standalone_zoo_source(self):
        self.assertIn('ROOT / "web" / "zoo.js"', self.check_js)
        self.assertRegex(self.check_js, r"suffix\s*==\s*['\"]\.js['\"]")

    def test_rendered_feed_uses_server_order_counts_and_pressed_states(self):
        if not self.zoo_js:
            self.fail("web/zoo.js is required")
        fixture = {
            "categories": [
                {"id": "free-for-all", "title": "Free for All"},
                {"id": "lets-collaborate", "title": "Let’s Collaborate"},
                {"id": "human-challenges", "title": "Human Challenges"},
                {"id": "ideas-experiments", "title": "Ideas & Experiments"},
            ],
            "rooms": [{"id": "room-zero", "title": "Room Zero"}],
            "agents": [
                {"id": "jay", "name": "Jay (Simulated)", "kind": "human", "simulated": True,
                 "identity_origin": "simulated", "execution_mode": "simulated", "connectivity": "local_only"},
                {"id": "you", "name": "You", "kind": "human", "simulated": False},
            ],
            "threads": [
                {"id": "thread-people", "room_id": "room-zero", "category_id": "free-for-all",
                 "title": "What’s the deal with people?", "author_id": "jay", "created_at": 1,
                 "simulated": True, "is_top": True,
                 "reaction_counts": {"appreciate": 0, "curious": 0, "idea": 0}},
                {"id": "local-thread", "room_id": "room-zero", "category_id": "ideas-experiments",
                 "title": "A local experiment", "author_id": "you", "created_at": 2,
                 "simulated": False, "is_top": False,
                 "reaction_counts": {"appreciate": 7, "curious": 2, "idea": 3}},
            ],
            "posts": [],
            "reactions": [{"id": "reaction-local", "target_id": "local-thread", "reaction": "appreciate", "author_id": "you"}],
            "follows": [],
        }
        program = self.zoo_js + r"""
zooState = FIXTURE;
const rendered = zoo();
if (rendered.indexOf('Top Thread') > rendered.indexOf('Room Zero')) throw new Error('Top Thread is not first');
if (rendered.indexOf('Room Zero') > rendered.indexOf('Thread index')) throw new Error('Room Zero is not second');
if (!rendered.includes('Appreciate · 7')) throw new Error('Server reaction count missing');
if (!/data-zoo-reaction="local-thread"[^>]*data-zoo-kind="appreciate"[^>]*aria-pressed="true"/.test(rendered)) throw new Error('Existing reaction is not pressed');
if (!/data-zoo-reaction="thread-people"[^>]*data-zoo-kind="appreciate"[^>]*aria-pressed="false"/.test(rendered)) throw new Error('Unselected reaction is pressed');
if (!rendered.includes('[Simulated example]')) throw new Error('Example provenance missing');
if (!rendered.includes('Stored on this Mac · not published')) throw new Error('Local provenance missing');
"""
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
            script = Path(directory) / "zoo-contract.js"
            script.write_text(
                "const FIXTURE = " + json.dumps(fixture, ensure_ascii=False) + ";\n"
                "const esc = value => String(value ?? '').replace(/[&<>\"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[c]));\n"
                + program
            )
            result = subprocess.run(["node", str(script)], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


    def run_interaction(self, scenario):
        harness = r"""
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let page = 'zoo';
let state = {profile: {human_name: 'You'}};
class FakeClassList {
  constructor() { this.values = new Set(); }
  toggle(name, force) { if (force) this.values.add(name); else this.values.delete(name); }
  add(name) { this.values.add(name); }
  contains(name) { return this.values.has(name); }
}
class FakeElement {
  constructor(id = '', dataset = {}) {
    this.id = id;
    this.dataset = {...dataset};
    this.attributes = {};
    this.listeners = {};
    this.classList = new FakeClassList();
    this.isConnected = true;
    this.disabled = false;
    this.open = false;
    this.focusCount = 0;
    this.textContent = '';
    this.innerHTML = '';
    this.parentElement = null;
    this.tagName = 'DIV';
  }
  addEventListener(type, callback) { (this.listeners[type] ||= []).push(callback); }
  async dispatch(type, event) { for (const callback of this.listeners[type] || []) await callback(event); }
  closest(selector) {
    if (selector === 'details' || selector === 'details.zoo-conversation') {
      let ancestor = this.parentElement;
      while (ancestor) {
        if (ancestor.tagName === 'DETAILS') return ancestor;
        ancestor = ancestor.parentElement;
      }
      return null;
    }
    return this;
  }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name]; }
  hasAttribute(name) { return Object.hasOwn(this.attributes, name); }
  querySelector(selector) {
    if (selector === 'details') return this.details ||= new FakeElement();
    if (selector === 'summary') return this.summary || null;
    if (selector === '[type="submit"]') return this.submit ||= new FakeElement();
    if (selector === '[data-zoo-follow]') return this.followControl || null;
    return null;
  }
  focus() { document.activeElement = this; this.focusCount += 1; }
  showModal() { this.open = true; }
  close() { this.open = false; return this.dispatch('close', {}); }
}
const registry = {};
function register(id, element = new FakeElement(id)) { registry[id] = element; return element; }
const document = {
  activeElement: null,
  rows: [],
  categoryButtons: [],
  controls: [],
  getElementById(id) { return registry[id] || null; },
  querySelectorAll(selector) {
    if (selector === '#zoo-thread-list [data-zoo-thread-row]') return this.rows;
    if (selector === '[data-zoo-category]') return this.categoryButtons;
    if (selector.includes('data-zoo-agent') || selector.includes('data-zoo-reaction') || selector.includes('data-zoo-follow')) return this.controls;
    return [];
  },
};
const pageElement = register('page');
const dialog = register('zoo-agent-dialog');
for (const id of ['zoo-agent-close', 'zoo-agent-title', 'zoo-agent-description', 'zoo-agent-portrait', 'zoo-agent-details', 'zoo-filter-empty', 'zoo-filter-status']) register(id);
const window = {listeners: {}, addEventListener(type, callback) { (this.listeners[type] ||= []).push(callback); }};
const location = {pathname: '/zoo'};
const history = {
  pushState(_state, _title, url) { location.pathname = url; },
  replaceState(_state, _title, url) { location.pathname = url; },
};
function $(id) { return document.getElementById(id); }
function note() {}
let render = () => {};
let refresh = async () => { render(); };
let api = async () => ({});
function control(dataset) {
  const element = new FakeElement('', dataset);
  document.controls.push(element);
  return element;
}
function conversation(id, open = false) {
  const element = register(id, new FakeElement(id));
  element.tagName = 'DETAILS';
  element.open = open;
  element.summary = new FakeElement();
  element.summary.tagName = 'SUMMARY';
  element.summary.parentElement = element;
  return element;
}
function categoryButton(category) {
  const element = new FakeElement('', {zooCategory: category});
  document.categoryButtons.push(element);
  return element;
}
function row(id, category) {
  const element = new FakeElement(id, {category});
  document.rows.push(element);
  return element;
}
function makeFixture() {
  return {
    categories: [
      {id: 'free-for-all', title: 'Free for All'},
      {id: 'ideas-experiments', title: 'Ideas & Experiments'},
    ],
    rooms: [{id: 'room-zero', title: 'Room Zero'}],
    agents: [{id: 'jay', name: 'Jay (Simulated)', kind: 'human', simulated: true, identity_origin: 'simulated', execution_mode: 'simulated', connectivity: 'local_only'}],
    threads: [
      {id: 'free-thread', category_id: 'free-for-all', title: 'Free thread', author_id: 'jay', simulated: false, is_top: false, reaction_counts: {appreciate: 0, curious: 0, idea: 0}},
      {id: 'local-thread', category_id: 'ideas-experiments', title: 'Idea thread', author_id: 'jay', simulated: false, is_top: false, reaction_counts: {appreciate: 0, curious: 0, idea: 0}},
    ],
    posts: [],
    reactions: [],
    follows: [],
  };
}
function assert(condition, message) { if (!condition) throw new Error(message); }
"""
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
            script = Path(directory) / "zoo-interaction.js"
            script.write_text(harness + "\n" + self.zoo_js + "\n" + scenario)
            result = subprocess.run(["node", str(script)], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_back_to_zoo_route_resets_category_behavior(self):
        self.run_interaction(r"""
zooState = makeFixture();
document.rows = [];
document.categoryButtons = [];
row('free-row', 'free-for-all');
row('idea-row', 'ideas-experiments');
for (const category of ['all', 'free-for-all', 'ideas-experiments']) categoryButton(category);
location.pathname = '/zoo/categories/free-for-all';
enhanceZooPage();
assert(zooCategory === 'free-for-all', 'Category route did not apply its filter');
assert(document.rows[1].classList.contains('hidden'), 'Category route did not hide other categories');
location.pathname = '/zoo';
enhanceZooPage();
assert(zooCategory === 'all', 'Back to /zoo retained a stale category');
assert(document.rows.every(row => !row.classList.contains('hidden')), 'Back to /zoo did not reveal all rows');
assert(document.categoryButtons[0].getAttribute('aria-pressed') === 'true', 'All threads is not pressed after Back');
""")

    def test_thread_creation_route_reveals_target_behavior(self):
        self.run_interaction(r"""
(async () => {
  zooState = makeFixture();
  zooCategory = 'free-for-all';
  location.pathname = '/zoo/categories/free-for-all';
  const form = new FakeElement();
  form.setAttribute('data-zoo-thread-form', '');
  form.elements = {title: {value: 'Created idea'}, category_id: {value: 'ideas-experiments'}};
  let targetRow;
  api = async (route, data) => {
    assert(route === '/api/zoo/thread', 'Unexpected thread creation route');
    const created = {id: 'created-thread', category_id: data.category_id, title: data.title, author_id: 'you', simulated: false, is_top: false, reaction_counts: {appreciate: 0, curious: 0, idea: 0}};
    zooState.threads.push(created);
    return created;
  };
  render = () => {
    document.rows = [];
    targetRow = row('zoo-thread-created-thread', 'ideas-experiments');
    registry['zoo-thread-created-thread'] = targetRow;
    enhanceZooPage();
  };
  let prevented = false;
  await pageElement.dispatch('submit', {target: form, preventDefault() { prevented = true; }});
  assert(prevented, 'Thread submission was not handled');
  assert(location.pathname === '/zoo/threads/created-thread', 'Thread route was not applied');
  assert(!targetRow.classList.contains('hidden'), 'Created target is hidden by the stale filter');
  assert(zooCategory === 'ideas-experiments', 'Thread route did not derive the target category');
})().catch(error => { console.error(error); process.exit(1); });
""")

    def test_profile_follow_updates_open_dialog_behavior(self):
        self.run_interaction(r"""
(async () => {
  zooState = makeFixture();
  zooAgentProfile('jay');
  const follow = control({zooFollow: 'agent', zooTarget: 'jay'});
  follow.textContent = 'Follow';
  follow.setAttribute('aria-pressed', 'false');
  $('zoo-agent-details').followControl = follow;
  api = async (route, data) => {
    assert(route === '/api/zoo/follow', 'First profile action should follow');
    zooState.follows.push({id: 'follow-jay', kind: 'agent', target: 'jay'});
    return zooState.follows[0];
  };
  await dialog.dispatch('click', {target: follow});
  assert(dialog.open, 'Profile follow closed the dialog');
  assert(follow.textContent === 'Following', 'Open dialog still says Follow after refreshed state');
  assert(follow.getAttribute('aria-pressed') === 'true', 'Open dialog aria-pressed is stale');
})().catch(error => { console.error(error); process.exit(1); });
""")

    def test_reaction_and_feed_follow_restore_equivalent_focus_behavior(self):
        self.run_interaction(r"""
(async () => {
  zooState = makeFixture();
  const oldReaction = control({zooReaction: 'local-thread', zooKind: 'appreciate'});
  let newReaction;
  api = async (route, data) => {
    zooState.reactions.push({id: 'reaction-new', target_id: data.target_id, reaction: data.reaction, author_id: 'you'});
    return {};
  };
  render = () => {
    oldReaction.isConnected = false;
    newReaction = control({zooReaction: 'local-thread', zooKind: 'appreciate'});
  };
  document.activeElement = oldReaction;
  await pageElement.dispatch('click', {target: oldReaction});
  assert(document.activeElement === newReaction, 'Reaction refresh did not focus the equivalent new control');

  zooState = makeFixture();
  const oldFollow = control({zooFollow: 'thread', zooTarget: 'local-thread'});
  let newFollow;
  api = async (route, data) => {
    zooState.follows.push({id: 'follow-thread', kind: data.kind, target: data.target});
    return {};
  };
  render = () => {
    oldFollow.isConnected = false;
    newFollow = control({zooFollow: 'thread', zooTarget: 'local-thread'});
  };
  document.activeElement = oldFollow;
  await pageElement.dispatch('click', {target: oldFollow});
  assert(document.activeElement === newFollow, 'Feed follow refresh did not focus the equivalent new control');
})().catch(error => { console.error(error); process.exit(1); });
""")

    def test_dialog_close_restores_equivalent_launcher_behavior(self):
        self.run_interaction(r"""
(async () => {
  zooState = makeFixture();
  const oldLauncher = control({zooAgent: 'jay'});
  document.activeElement = oldLauncher;
  zooAgentProfile('jay');
  oldLauncher.isConnected = false;
  const newLauncher = control({zooAgent: 'jay'});
  await dialog.close();
  assert(document.activeElement === newLauncher, 'Dialog close did not find the replacement launcher');
  assert(newLauncher.focusCount === 1, 'Replacement launcher did not receive focus exactly once');
})().catch(error => { console.error(error); process.exit(1); });
""")

    def test_post_reaction_reopens_active_conversation_for_focus_behavior(self):
        self.run_interaction(r"""
(async () => {
  zooState = makeFixture();
  zooState.posts.push({id: 'post-alex', thread_id: 'thread-people', author_id: 'alex', content: 'Example', reaction_counts: {appreciate: 0, curious: 0, idea: 0}});
  const oldConversation = conversation('zoo-conversation-thread-people', true);
  const oldReaction = control({zooReaction: 'post-alex', zooKind: 'idea'});
  oldReaction.parentElement = oldConversation;
  let newConversation;
  let newReaction;
  api = async (route, data) => {
    zooState.reactions.push({id: 'reaction-post', target_id: data.target_id, reaction: data.reaction, author_id: 'you'});
    return {};
  };
  render = () => {
    oldReaction.isConnected = false;
    oldConversation.isConnected = false;
    newConversation = conversation('zoo-conversation-thread-people', false);
    newReaction = control({zooReaction: 'post-alex', zooKind: 'idea'});
    newReaction.parentElement = newConversation;
  };
  document.activeElement = oldReaction;
  await pageElement.dispatch('click', {target: oldReaction});
  assert(newConversation.open, 'Post reaction refresh left its replacement inside a closed conversation');
  assert(document.activeElement === newReaction, 'Post reaction did not focus the equivalent visible control');
})().catch(error => { console.error(error); process.exit(1); });
""")

    def test_profile_close_skips_closed_author_and_uses_directory_or_summary_behavior(self):
        self.run_interaction(r"""
(async () => {
  zooState = makeFixture();
  zooState.agents.push({id: 'alex', name: 'Alex (Simulated)', kind: 'human', simulated: true, identity_origin: 'simulated', execution_mode: 'simulated', connectivity: 'local_only'});
  const oldDirectory = control({zooAgent: 'alex'});
  document.activeElement = oldDirectory;
  zooAgentProfile('alex');
  oldDirectory.isConnected = false;
  const closedTop = conversation('zoo-conversation-thread-people', false);
  const hiddenAuthor = control({zooAgent: 'alex'});
  hiddenAuthor.parentElement = closedTop;
  const visibleDirectory = control({zooAgent: 'alex'});
  await dialog.close();
  assert(document.activeElement === visibleDirectory, 'Dialog close chose a post author hidden by closed Top Thread details');

  const oldPostConversation = conversation('zoo-conversation-thread-people', true);
  const oldPostLauncher = control({zooAgent: 'alex'});
  oldPostLauncher.parentElement = oldPostConversation;
  document.activeElement = oldPostLauncher;
  zooAgentProfile('alex');
  oldPostLauncher.isConnected = false;
  visibleDirectory.isConnected = false;
  const newClosedConversation = conversation('zoo-conversation-thread-people', false);
  const fallbackAuthor = control({zooAgent: 'alex'});
  fallbackAuthor.parentElement = newClosedConversation;
  await dialog.close();
  assert(document.activeElement === newClosedConversation.summary, 'Dialog close did not use the conversation summary as a safe fallback');
})().catch(error => { console.error(error); process.exit(1); });
""")

    def test_project_header_flexes_without_fixed_height_overlap(self):
        header = re.search(r"(?:^|})header\{([^}]+)\}", self.projects)
        self.assertIsNotNone(header)
        self.assertIn("min-height:70px", header.group(1))
        self.assertNotRegex(header.group(1), r"(?:^|;)height:")
        self.assertIn("flex-wrap:wrap", header.group(1))
        mobile = re.search(r"@media\(max-width:620px\)\{header\{([^}]+)\}", self.projects)
        self.assertIsNotNone(mobile)
        self.assertIn("min-height:62px", mobile.group(1))
        self.assertNotRegex(mobile.group(1), r"(?:^|;)height:")


class OnboardingFrontendContractTests(unittest.TestCase):
    CONSENT = "Local preview only — nothing was sent, no account was created, no membership changed, and no access was granted."

    @classmethod
    def setUpClass(cls):
        cls.shell = read_source("web/shell.html")
        cls.onboarding = read_source("web/onboarding.js")
        cls.zoo_css = read_source("web/zoo.css")
        cls.check_js = read_source("tests/check_js.py")

    def test_onboarding_source_dialogs_and_page_integration_are_synchronized(self):
        self.assertTrue(self.onboarding, "web/onboarding.js is required")
        self.assertIn('<script id="onboarding-script">\n' + self.onboarding + '\n</script>', self.shell)
        self.assertIn('ROOT / "web" / "onboarding.js"', self.check_js)
        for function in ("maybeShowSetup()", "enhanceLocalPages()", "showInvitationPreview(id)"):
            self.assertIn("function " + function, self.onboarding)
        self.assertIn("enhanceLocalPages()", self.shell)
        self.assertIn("maybeShowSetup()", self.shell)
        for dialog in ("setup", "invitation"):
            self.assertIn(f'id="{dialog}-dialog" aria-labelledby="{dialog}-title" aria-describedby="{dialog}-description"', self.shell)
            self.assertIn(f'id="{dialog}-title" tabindex="-1"', self.shell)
            self.assertIn(f'id="{dialog}-status" class="status" role="status" aria-live="polite"', self.shell)

    def test_wizard_steps_api_keys_and_honest_provider_boundaries(self):
        for marker in (
            "Welcome / privacy", "Providers", "Collaborators", "Skip setup", "Not now",
            "Ordinary web subscriptions do not automatically include API access.",
            "Charges depend on the provider account.",
            "Output limits are not a spending cap.",
            "session-only", "unverified", "never makes a provider request",
            "local plaintext", "private by default", "browse without a provider",
        ):
            self.assertIn(marker, self.onboarding)
        for provider, name in (
            ("openai", "OpenAI"), ("anthropic", "Anthropic"),
            ("gemini", "Gemini"), ("mistral", "Mistral"), ("groq", "Groq"),
        ):
            self.assertIn(f'setup-key-{provider}', self.onboarding)
            self.assertIn(f'{name} API key', self.onboarding)
        self.assertIn('type="password"', self.onboarding)
        self.assertIn("/api/connect", self.onboarding)
        self.assertIn("/api/disconnect", self.onboarding)
        self.assertIn("/api/onboarding", self.onboarding)
        self.assertNotRegex(self.onboarding, r"OAuth|subscription sign.in|/api/(?:chat|run|request|generate)")

    def test_models_and_people_offer_persistent_return_paths(self):
        self.assertIn('data-open-setup="providers"', self.shell)
        self.assertIn('data-open-setup="collaborators"', self.shell)
        self.assertIn('data-new-invitation', self.shell)
        self.assertIn("invitationPreviewList()", self.shell)
        self.assertNotIn("setTimeout(()=>{if(!$('provider-dialog').open)showConnect()", self.shell)
        for status in ("skipped", "completed"):
            self.assertIn(f"status: '{status}'", self.onboarding)

    def test_invitation_preview_consent_statuses_and_no_delivery_contract(self):
        self.assertIn(self.CONSENT, self.onboarding)
        self.assertIn(
            "Accepting, declining, or cancelling changes only this preview record: nothing is sent, no account, membership, or access changes, and no private project content is shared.",
            self.onboarding,
        )
        for marker in (
            "Inviter preview", "Invitee preview", "accepted_preview",
            "declined_preview", "cancelled_preview", "/api/invitation-preview",
            "/api/invitation-preview/status", "/api/invitation-preview/delete",
            "sharing_goal", "sharing_documents", "sharing_history", "checked",
        ):
            self.assertIn(marker, self.onboarding)
        self.assertNotIn("Send invitation", self.shell + self.onboarding)
        self.assertNotRegex(self.onboarding, r"https?://|acceptance\s+url|bearer\s+link|location\.href|sessionStorage")

    def test_invitation_install_copy_fallback_and_responsive_accessible_styles(self):
        for marker in (
            "Install and open Elect Twin", "Join steps", "internal build",
            "Developer ID", "notarized", "Gatekeeper", "clipboard.writeText",
            "invitation-copy-fallback", "select()", "readOnly",
        ):
            self.assertIn(marker, self.onboarding + self.shell)
        for selector in ("#setup-dialog", "#invitation-dialog", ".setup-provider", ".invitation-fields"):
            self.assertIn(selector, self.zoo_css)
        self.assertNotRegex(self.zoo_css, r"gradient\(|box-shadow|@import|https?://")
        self.assertRegex(self.zoo_css, r"@media\s*\(max-width\s*:\s*760px\)")
        self.assertRegex(self.zoo_css, r"prefers-reduced-motion\s*:\s*reduce")
        self.assertRegex(self.zoo_css, r"overflow-wrap\s*:\s*anywhere")

    def run_onboarding(self, scenario):
        harness = r"""
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let page = 'models';
let setupShown = false;
let state = {
  profile: {human_name: 'You', onboarding: {status: 'not_started', updated_at: null}},
  providers: [
    {id: 'openai', configured: false}, {id: 'anthropic', configured: false},
    {id: 'gemini', configured: false}, {id: 'mistral', configured: false},
    {id: 'groq', configured: false},
  ],
  projects: [{id: 'project-local', name: 'Local project'}],
  invitation_previews: [],
};
class FakeClassList {
  constructor() { this.values = new Set(); }
  add(name) { this.values.add(name); }
  remove(name) { this.values.delete(name); }
  toggle(name, force) {
    if (force === undefined) force = !this.values.has(name);
    if (force) this.values.add(name); else this.values.delete(name);
  }
  contains(name) { return this.values.has(name); }
}
class FakeElement {
  constructor(id = '', dataset = {}) {
    this.id = id;
    this.dataset = {...dataset};
    this.attributes = {};
    this.listeners = {};
    this.classList = new FakeClassList();
    this.isConnected = true;
    this.disabled = false;
    this.open = false;
    this.focusCount = 0;
    this.textContent = '';
    this.innerHTML = '';
    this.value = '';
    this.readOnly = false;
    this.selected = false;
    this.elements = {};
  }
  addEventListener(type, callback) { (this.listeners[type] ||= []).push(callback); }
  async dispatch(type, event) { for (const callback of this.listeners[type] || []) await callback(event); }
  closest() { return this; }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name]; }
  hasAttribute(name) { return Object.hasOwn(this.attributes, name); }
  focus() { document.activeElement = this; this.focusCount += 1; }
  showModal() { this.open = true; }
  close() { this.open = false; return this.dispatch('close', {}); }
  select() { this.selected = true; }
}
const registry = {};
function register(id, element = new FakeElement(id)) { registry[id] = element; return element; }
for (const id of [
  'page', 'status', 'setup-dialog', 'setup-title', 'setup-description',
  'setup-status', 'setup-content', 'invitation-dialog', 'invitation-title',
  'invitation-description', 'invitation-status', 'invitation-content',
  'invitation-copy-fallback', 'invitation-copy-text',
]) register(id);
for (const id of ['openai', 'anthropic', 'gemini', 'mistral', 'groq']) {
  register('setup-provider-state-' + id);
  register('setup-disconnect-' + id);
}
const document = {
  activeElement: null,
  setupLaunchers: [],
  invitationLaunchers: [],
  newInvitationLaunchers: [],
  getElementById(id) { return registry[id] || null; },
  querySelectorAll(selector) {
    if (selector === '[data-open-setup]') return this.setupLaunchers;
    if (selector === '[data-invitation-id]') return this.invitationLaunchers;
    if (selector === '[data-new-invitation]') return this.newInvitationLaunchers;
    return [];
  },
};
let navigator = {clipboard: {writeText: async () => {}}};
function $(id) { return document.getElementById(id); }
function note() {}
let api = async () => ({});
let refresh = async () => {};
function assert(condition, message) { if (!condition) throw new Error(message); }
function click(target) { return {target, preventDefault() {}}; }
function submit(target) { return {target, prevented: false, preventDefault() { this.prevented = true; }}; }
function setupLauncher(step) {
  const launcher = new FakeElement('', {openSetup: step});
  document.setupLaunchers.push(launcher);
  return launcher;
}
function invitationLauncher(id) {
  const launcher = new FakeElement('', {invitationId: id});
  document.invitationLaunchers.push(launcher);
  return launcher;
}
function providerForm(provider, key) {
  const form = new FakeElement('', {setupProviderForm: provider});
  form.elements = {key: {value: key}};
  return form;
}
function invitationForm() {
  const form = new FakeElement('', {invitationCreate: ''});
  form.elements = {
    recipient_name: {value: 'Ada'}, contact: {value: 'ada@example.test'},
    project_id: {value: 'project-local'}, role: {value: 'Reviewer'},
    sharing_goal: {checked: false}, sharing_documents: {checked: false},
    sharing_history: {checked: false},
  };
  return form;
}
function localInvitation() {
  return {
    id: 'invitation-local', recipient_name: 'Ada', contact: 'ada@example.test',
    project_id: 'project-local', project_name: 'Local project', role: 'Reviewer',
    sharing: {goal: false, documents: false, history: false}, status: 'draft',
    simulated: true, delivery: 'not_sent', membership_changed: false,
    created_at: 1, updated_at: 1,
  };
}
"""
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
            script = Path(directory) / "onboarding-interaction.js"
            script.write_text(harness + "\n" + self.onboarding + "\n" + scenario)
            result = subprocess.run(["node", str(script)], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_wizard_steps_focus_and_reopen_preserve_state_behavior(self):
        self.run_onboarding(r"""
(async () => {
  const launcher = setupLauncher('providers');
  document.activeElement = launcher;
  let calls = [];
  api = async (route, data) => { calls.push({route, data}); return {}; };
  maybeShowSetup();
  assert($('setup-dialog').open, 'First run did not open optional setup');
  assert($('setup-title').textContent === 'Welcome / privacy', 'Welcome step missing');
  assert(document.activeElement === $('setup-title'), 'Welcome heading did not receive focus');
  await $('setup-dialog').dispatch('click', click(new FakeElement('', {setupStep: 'providers'})));
  assert($('setup-title').textContent === 'Providers', 'Providers step missing');
  assert($('setup-title').focusCount === 2, 'Providers heading did not receive focus');
  await $('setup-dialog').dispatch('click', click(new FakeElement('', {setupStep: 'collaborators'})));
  assert($('setup-title').textContent === 'Collaborators', 'Collaborators step missing');
  assert($('setup-title').focusCount === 3, 'Collaborators heading did not receive focus');
  await $('setup-dialog').close();
  state.profile.onboarding = {status: 'completed', updated_at: 10};
  state.providers[0].configured = true;
  maybeShowSetup();
  assert(!$('setup-dialog').open, 'Completed setup reopened automatically');
  await $('page').dispatch('click', click(launcher));
  assert($('setup-dialog').open, 'My Models return path did not reopen setup');
  assert($('setup-title').textContent === 'Providers', 'Return path reset the requested step');
  assert(state.profile.onboarding.status === 'completed', 'Reopening reset onboarding state');
  assert(state.providers[0].configured, 'Reopening reset provider state');
  assert(calls.length === 0, 'Step navigation or reopening made an unexpected request');
})().catch(error => { console.error(error); process.exit(1); });
""")

    def test_skip_and_not_now_persist_and_restore_replacement_launcher_behavior(self):
        self.run_onboarding(r"""
(async () => {
  const oldLauncher = setupLauncher('welcome');
  document.activeElement = oldLauncher;
  const calls = [];
  api = async (route, data) => {
    calls.push({route, data});
    state.profile.onboarding = {status: data.status, updated_at: 2};
    return {};
  };
  const replacement = new FakeElement('', {openSetup: 'welcome'});
  refresh = async () => {
    oldLauncher.isConnected = false;
    document.setupLaunchers = [replacement];
  };
  maybeShowSetup();
  await $('setup-dialog').dispatch('click', click(new FakeElement('', {setupSkip: ''})));
  assert(calls.length === 1 && calls[0].route === '/api/onboarding' && calls[0].data.status === 'skipped', 'Skip setup was not persisted');
  assert(!$('setup-dialog').open, 'Skip setup did not close the wizard');
  assert(document.activeElement === replacement, 'Skip did not focus the replacement launcher');
  await $('page').dispatch('click', click(replacement));
  await $('setup-dialog').dispatch('click', click(new FakeElement('', {setupNotNow: ''})));
  assert(calls.length === 2 && calls[1].data.status === 'skipped', 'Not now was not persisted as skipped');
  assert(!$('setup-dialog').open, 'Not now did not close the wizard');
  assert($('setup-status').getAttribute('role') === 'status', 'Successful status was not announced politely');
})().catch(error => { console.error(error); process.exit(1); });
""")

    def test_sequential_provider_configuration_preserves_others_and_clears_keys_behavior(self):
        self.run_onboarding(r"""
(async () => {
  const launcher = setupLauncher('providers');
  await $('page').dispatch('click', click(launcher));
  const openai = providerForm('openai', 'fixture-openai-key');
  const anthropic = providerForm('anthropic', 'fixture-anthropic-key');
  const calls = [];
  api = async (route, data) => {
    calls.push({route, data});
    if (route === '/api/connect') state.providers.find(item => item.id === data.provider).configured = true;
    if (route === '/api/disconnect') state.providers.find(item => item.id === data.provider).configured = false;
    return {};
  };
  await $('setup-dialog').dispatch('submit', submit(openai));
  assert(openai.elements.key.value === '', 'Submitted OpenAI key was not cleared');
  assert(anthropic.elements.key.value === 'fixture-anthropic-key', 'Another provider field was changed');
  assert($('setup-dialog').open, 'Wizard closed after the first provider');
  await $('setup-dialog').dispatch('submit', submit(anthropic));
  assert(anthropic.elements.key.value === '', 'Submitted Anthropic key was not cleared');
  assert(state.providers[0].configured && state.providers[1].configured, 'Providers were not configured independently');
  await $('setup-dialog').dispatch('click', click(new FakeElement('', {setupDisconnect: 'openai'})));
  assert(!state.providers[0].configured && state.providers[1].configured, 'Disconnect changed another provider');
  assert($('setup-dialog').open, 'Wizard closed after disconnect');
  assert(calls.map(call => call.route).join(',') === '/api/connect,/api/connect,/api/disconnect', 'Unexpected provider or model route');
  assert($('setup-status').textContent.includes('unverified'), 'Provider status did not explain verification');
})().catch(error => { console.error(error); process.exit(1); });
""")

    def test_failed_provider_attempt_clears_key_and_announces_without_closing_behavior(self):
        self.run_onboarding(r"""
(async () => {
  await $('page').dispatch('click', click(setupLauncher('providers')));
  const form = providerForm('gemini', 'fixture-rejected-key');
  api = async route => { assert(route === '/api/connect', 'Failure path called a model route'); throw new Error('Fixture connection rejected'); };
  const event = submit(form);
  await $('setup-dialog').dispatch('submit', event);
  assert(event.prevented, 'Provider form performed native submission');
  assert(form.elements.key.value === '', 'Failed attempt retained its key field');
  assert($('setup-dialog').open, 'Failed attempt closed the wizard');
  assert($('setup-status').getAttribute('role') === 'alert', 'Provider error was not announced');
  assert($('setup-status').textContent.includes('Fixture connection rejected'), 'Provider error was not visible');
})().catch(error => { console.error(error); process.exit(1); });
""")

    def test_invitation_create_unchecked_status_and_delete_behavior(self):
        self.run_onboarding(r"""
(async () => {
  const createLauncher = new FakeElement('', {newInvitation: ''});
  document.newInvitationLaunchers.push(createLauncher);
  await $('page').dispatch('click', click(createLauncher));
  assert(document.activeElement === $('invitation-title'), 'Create heading did not receive focus');
  const form = invitationForm();
  const calls = [];
  api = async (route, data) => {
    calls.push({route, data});
    if (route === '/api/invitation-preview') {
      assert(Object.keys(data).sort().join(',') === 'contact,project_id,recipient_name,role,sharing', 'Create sent fields outside the allowed schema');
      assert(Object.values(data.sharing).every(value => value === false), 'Sharing did not default unchecked');
      const created = {...localInvitation(), ...data, id: 'invitation-local'};
      state.invitation_previews.push(created);
      return created;
    }
    if (route === '/api/invitation-preview/status') {
      const item = state.invitation_previews[0];
      item.status = data.status;
      item.updated_at = 2;
      return item;
    }
    if (route === '/api/invitation-preview/delete') {
      state.invitation_previews = [];
      return {deleted: data.id};
    }
    throw new Error('Unexpected route ' + route);
  };
  await $('invitation-dialog').dispatch('submit', submit(form));
  assert(state.invitation_previews.length === 1, 'Local preview was not created');
  assert($('invitation-title').textContent === 'Inviter preview', 'Create did not return to inviter view');
  await $('invitation-dialog').dispatch('click', click(new FakeElement('', {invitationStatus: 'invitation-local', status: 'accepted_preview'})));
  assert(state.invitation_previews[0].status === 'accepted_preview', 'Accept did not update only the preview record');
  assert(state.invitation_previews[0].delivery === 'not_sent' && !state.invitation_previews[0].membership_changed, 'Preview changed delivery or membership');
  assert($('invitation-status').textContent.includes('only this preview record'), 'Preview-only status change was not announced');
  await $('invitation-dialog').dispatch('click', click(new FakeElement('', {invitationDelete: 'invitation-local'})));
  assert(state.invitation_previews.length === 0, 'Delete did not remove the preview');
  assert(!$('invitation-dialog').open, 'Delete did not close the preview dialog');
  assert(calls.map(call => call.route).join(',') === '/api/invitation-preview,/api/invitation-preview/status,/api/invitation-preview/delete', 'Unexpected invitation route');
})().catch(error => { console.error(error); process.exit(1); });
""")

    def test_copy_failure_exposes_safe_selectable_fallback_behavior(self):
        self.run_onboarding(r"""
(async () => {
  const item = {...localInvitation(), private_note: 'private-canary', bearer_link: 'bearer-canary'};
  state.invitation_previews = [item];
  const launcher = invitationLauncher(item.id);
  await $('page').dispatch('click', click(launcher));
  let copied = '';
  navigator.clipboard.writeText = async text => { copied = text; throw new Error('Clipboard unavailable'); };
  await $('invitation-dialog').dispatch('click', click(new FakeElement('', {invitationCopy: item.id})));
  assert(copied.includes('Local preview only — nothing was sent'), 'Copy omitted local-only consent');
  assert(copied.includes('Join steps') && copied.includes('Developer ID'), 'Copy omitted join/signing limitations');
  for (const forbidden of ['private-canary', 'bearer-canary', 'http://', 'https://', '#token=']) {
    assert(!copied.includes(forbidden), 'Copy included forbidden content: ' + forbidden);
    assert(!$('invitation-content').innerHTML.includes(forbidden), 'Preview displayed forbidden content: ' + forbidden);
  }
  assert(!$('invitation-copy-fallback').classList.contains('hidden'), 'Copy failure did not reveal fallback');
  assert($('invitation-copy-text').value === copied, 'Fallback omitted the explanatory preview');
  assert($('invitation-copy-text').selected, 'Fallback text was not selected');
  assert(document.activeElement === $('invitation-copy-text'), 'Fallback did not receive focus');
  assert($('invitation-status').getAttribute('role') === 'status', 'Copy fallback was not announced');
})().catch(error => { console.error(error); process.exit(1); });
""")

    def test_invitation_close_restores_replacement_launcher_behavior(self):
        self.run_onboarding(r"""
(async () => {
  state.invitation_previews = [localInvitation()];
  const oldLauncher = invitationLauncher('invitation-local');
  document.activeElement = oldLauncher;
  await $('page').dispatch('click', click(oldLauncher));
  assert($('invitation-dialog').open, 'Inviter preview did not open');
  oldLauncher.isConnected = false;
  const replacement = new FakeElement('', {invitationId: 'invitation-local'});
  document.invitationLaunchers = [replacement];
  await $('invitation-dialog').close();
  assert(document.activeElement === replacement, 'Invitation close did not focus replacement launcher');
  assert(replacement.focusCount === 1, 'Replacement invitation launcher focused more than once');
})().catch(error => { console.error(error); process.exit(1); });
""")

    def test_invitee_close_restores_the_equivalent_view_launcher_behavior(self):
        self.run_onboarding(r"""
(async () => {
  state.invitation_previews = [localInvitation()];
  const oldLauncher = invitationLauncher('invitation-local');
  oldLauncher.dataset.invitationInvitee = '';
  document.activeElement = oldLauncher;
  await $('page').dispatch('click', click(oldLauncher));
  assert($('invitation-title').textContent === 'Invitee preview', 'Invitee launcher opened the wrong view');
  oldLauncher.isConnected = false;
  const inviter = new FakeElement('', {invitationId: 'invitation-local', invitationView: 'inviter'});
  const invitee = new FakeElement('', {invitationId: 'invitation-local', invitationInvitee: ''});
  document.invitationLaunchers = [inviter, invitee];
  await $('invitation-dialog').close();
  assert(document.activeElement === invitee, 'Invitee close focused a different action on the same record');
})().catch(error => { console.error(error); process.exit(1); });
""")

    def test_nested_create_close_restores_setup_launcher_after_rerender_behavior(self):
        self.run_onboarding(r"""
(async () => {
  const setup = setupLauncher('collaborators');
  await $('page').dispatch('click', click(setup));
  const pageCreate = new FakeElement('', {newInvitation: ''});
  const setupCreate = new FakeElement('', {newInvitation: '', setupInvitation: ''});
  document.newInvitationLaunchers = [pageCreate, setupCreate];
  document.activeElement = setupCreate;
  await $('setup-dialog').dispatch('click', click(setupCreate));
  assert($('invitation-dialog').open, 'Nested create preview did not open');
  pageCreate.isConnected = false;
  setupCreate.isConnected = false;
  const pageReplacement = new FakeElement('', {newInvitation: ''});
  const setupReplacement = new FakeElement('', {newInvitation: '', setupInvitation: ''});
  document.newInvitationLaunchers = [pageReplacement, setupReplacement];
  await $('invitation-dialog').close();
  assert(document.activeElement === setupReplacement, 'Nested preview close focused the underlying page instead of its setup launcher');
})().catch(error => { console.error(error); process.exit(1); });
""")


if __name__ == "__main__":
    unittest.main()
