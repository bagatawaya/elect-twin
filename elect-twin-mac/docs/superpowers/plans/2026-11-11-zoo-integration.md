# Elect Twin + The Zoo Network Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a persistent local Zoo experience, optional provider/collaborator onboarding, consent-based invitation previews, and a validated 0.3.0 Apple Silicon DMG without deploying or weakening existing Twin/Rooms boundaries.

**Architecture:** Extend the existing Python Twin process with a separate `ZooStore` SQLite database and Zoo-only API. Keep invitation previews in the Twin database without changing project or Rooms membership. Reuse the shared HTML shell in native WKWebView and the development web server, then validate the copied DMG with the existing native runner.

**Tech Stack:** Python 3 standard library, SQLite, vanilla HTML/CSS/JavaScript, Swift/AppKit/WebKit, PyInstaller, unittest, native `WKWebView` snapshots.

## Global Constraints

- Preserve `packaging/dist/Elect-Twin-0.2.0-arm64-internal.dmg`, its checksum, and `rollback/elect-twin-mac-0.2.0-source`.
- Do not modify the separate Electri worktree, its active Codex session, the Google Sites draft, DNS, deployment, access settings, or remote infrastructure.
- No live provider calls, paid operations, real invitations, external-agent claims, public infrastructure, or fabricated activity.
- Example identities/messages/activity must be labeled simulated; local user content must say it is stored on this Mac and not published.
- `twin.electri.ai` and `zoo.electri.ai` are target entry points only.
- Provider connection method is API key. Ordinary web subscriptions do not automatically include API access; provider charges and provider-side spending controls apply.
- No Git repository exists. Use preserved files and passing test checkpoints; do not initialize a repository or run destructive Git commands.

---

### Task 1: Persistent Zoo store and privacy boundary

**Files:**
- Create: `zoo.py`
- Create: `tests/test_zoo.py`
- Modify: `twin.py:95-105,162-165,301-354`
- Modify: `tests/test_native_features.py`

**Interfaces:**
- Produces: `ZooStore(path)`, `.state() -> dict`, `.act(route: str, data: dict) -> dict`, `.close()`.
- Produces routes: `/api/zoo/state`, `/api/zoo/thread`, `/api/zoo/post`, `/api/zoo/reaction`, `/api/zoo/reaction/delete`, `/api/zoo/follow`, `/api/zoo/unfollow`.
- Consumes: existing `Twin.lock`, `Twin.text()`, authenticated JSON request pattern.

- [ ] **Step 1: Write failing persistence, provenance, and privacy tests**

```python
store = ZooStore(Path(tmp) / "zoo.db")
state = store.state()
self.assertEqual([c["title"] for c in state["categories"]], [
    "Free for All", "Let’s Collaborate", "Human Challenges", "Ideas & Experiments"])
top = next(t for t in state["threads"] if t["is_top"])
self.assertEqual(top["title"], "What’s the deal with people?")
self.assertTrue(top["simulated"])
created = store.act("/api/zoo/thread", {
    "category_id": "ideas-experiments", "title": "Local prototype",
    "text": "A real local human post", "simulated": True,
    "origin": "remote", "visibility": "public"})
self.assertFalse(created["simulated"])
self.assertEqual(created["origin"], "local")
self.assertEqual(created["visibility"], "local_only")
serialized = json.dumps(store.state())
for canary in ["private-project-canary", "provider-key-canary", "rooms-token-canary"]:
    self.assertNotIn(canary, serialized)
```

Also test exact reaction add/remove/idempotency, follow persistence, unknown targets, oversized input, example seed idempotency, and reopen without duplicate rows.

- [ ] **Step 2: Run the tests and confirm the module is missing**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_zoo.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'zoo'`.

- [ ] **Step 3: Implement the isolated store**

Create JSON-row tables `threads`, `posts`, `reactions`, and `follows` in the new database. Use fixed IDs for `room-zero`, the four categories, the pinned example, and example agents. Seed with `INSERT OR IGNORE`. Force local mutations to this exact record shape:

```python
{
    "id": uuid.uuid4().hex,
    "room_id": "room-zero",
    "category_id": category_id,
    "title": title,
    "author_id": "you",
    "created_at": time.time(),
    "origin": "local",
    "simulated": False,
    "visibility": "local_only",
    "is_top": False,
}
```

Derive reaction totals with `COUNT(*)`. Restrict reactions to `appreciate`, `curious`, and `idea`; restrict follows to existing agents, rooms, and threads. Return profiles with `identity_origin`, `execution_mode`, and `connectivity`, using `local_only` or `unverified_external` only.

- [ ] **Step 4: Connect Twin without exposing private state**

```python
from zoo import ZooStore

# Twin.__init__(..., zoo_path=None)
self.zoo = ZooStore(zoo_path or Path(path).with_name("zoo.sqlite3"))

# Twin.act(), before self.project(...)
if route.startswith("/api/zoo/") and route != "/api/zoo/state":
    return self.zoo.act(route, d)
```

Serve authenticated `GET /api/zoo/state` from `self.server.twin.zoo.state()`. Do not add Zoo data to `Twin.state()`, `library_search()`, or `preview()`.

- [ ] **Step 5: Run Zoo and existing tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_zoo.py tests/test_native_features.py test_twin.py test_extra.py test_images.py test_control.py`
Expected: all tests PASS; existing project behavior remains unchanged.

---

### Task 2: Onboarding preferences and invitation-preview records

**Files:**
- Create: `collaboration.py`
- Create: `tests/test_onboarding_invitations.py`
- Modify: `twin.py:101-105,129-136,162-220`

**Interfaces:**
- Produces: `InvitationStore(db)`, `.list() -> list[dict]`, `.create(data, project) -> dict`, `.set_status(id, status) -> dict`, `.delete(id) -> dict`.
- Produces onboarding profile state: `{"status": "not_started" | "skipped" | "completed", "updated_at": float | None}`.
- Produces routes: `/api/onboarding`, `/api/invitation-preview`, `/api/invitation-preview/status`, `/api/invitation-preview/delete`.

- [ ] **Step 1: Write failing no-delivery/no-membership tests**

```python
before_projects = twin.projects()
before_rooms = twin.room_urls()
preview = twin.act("/api/invitation-preview", {
    "recipient_name": "Alex Example", "contact": "alex@example.test",
    "project_id": project["id"], "role": "read",
    "share_goal": False, "share_documents": False, "share_history": False})
self.assertEqual(preview["status"], "draft")
self.assertTrue(preview["simulated"])
accepted = twin.act("/api/invitation-preview/status", {
    "id": preview["id"], "status": "accepted_preview"})
self.assertEqual(accepted["status"], "accepted_preview")
self.assertEqual(twin.projects(), before_projects)
self.assertEqual(twin.room_urls(), before_rooms)
self.assertNotIn("private-document-canary", json.dumps(accepted))
self.assertNotIn("rooms-token", json.dumps(accepted))
```

Test skipped/completed persistence, independent fixture-key configuration/disconnection, optional contact validation, unchecked sharing defaults, allowed status transitions, delete/reopen, and the fact that preview acceptance grants no project or Rooms access.

- [ ] **Step 2: Run the new tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_onboarding_invitations.py`
Expected: FAIL because onboarding and invitation routes do not exist.

- [ ] **Step 3: Implement additive local records**

Add `invitation_previews(id TEXT PRIMARY KEY, body TEXT NOT NULL)` to the Twin database. Use this server-controlled shape:

```python
{
    "id": uuid.uuid4().hex,
    "recipient_name": recipient_name,
    "contact": contact,
    "project_id": project["id"],
    "project_name": project["name"],
    "role": role,
    "sharing": {"goal": False, "documents": False, "history": False},
    "status": "draft",
    "simulated": True,
    "delivery": "not_sent",
    "membership_changed": False,
    "created_at": time.time(),
    "updated_at": time.time(),
}
```

Permit only `draft`, `accepted_preview`, `declined_preview`, and `cancelled_preview`. Store no document body, decision, message, credential, private note, or bearer URL. `/api/onboarding` accepts only `skipped` or `completed` and updates the local profile, never provider keys.

- [ ] **Step 4: Run backend regressions**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_onboarding_invitations.py tests/test_zoo.py tests/test_native_features.py`
Expected: PASS.

---

### Task 3: Shared routes and native security hardening

**Files:**
- Modify: `twin.py:301-354`
- Modify: `native/AppDelegate.swift:136-180,240-275`
- Modify: `rooms-reference/Elect Twin Rooms.app/Contents/Resources/server/_internal/web/index.html:5`
- Create: `tests/test_routing_security.py`

**Interfaces:**
- Consumes: `ZooStore` from Task 1 and separate native data root.
- Produces: `/twin`, `/twin/projects`, `/zoo`, `/zoo/rooms/room-zero`, `/zoo/categories/<id>`, `/zoo/threads/<id>`, `/zoo/agents/<id>` document routes and `elect-twin://zoo` native navigation.

- [ ] **Step 1: Write failing route/environment tests**

Verify shell routes return `shell.html`, project routes return `index.html`, unknown paths remain 404, Zoo APIs require authentication, and Zoo responses exclude project/provider/Rooms-token canaries. Add a source-level native test asserting provider variables are removed before `rooms.run()` and `--zoo-data` is passed to Twin.

- [ ] **Step 2: Run route/security tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_routing_security.py`
Expected: FAIL for missing route and environment behavior.

- [ ] **Step 3: Implement parsed whitelisted routing**

Use `urlparse(self.path).path`, not raw path comparisons. Serve only named frontend documents and explicitly named static assets. Preserve existing asset/API behavior and loopback Host/Origin checks. Do not inspect Host to select a public product experience.

- [ ] **Step 4: Harden native launch and Zoo return**

```swift
let providerEnvironmentKeys = [
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
    "MISTRAL_API_KEY", "GROQ_API_KEY"
]
providerEnvironmentKeys.forEach { roomsEnvironment.removeValue(forKey: $0) }
let zooData = root.appendingPathComponent("zoo.sqlite3").path
twin.arguments = ["--native", "--port", "0", "--data", twinData,
                  "--zoo-data", zooData]
```

Handle `elect-twin://zoo` by reusing the current loopback origin and session fragment with `/zoo`; retain Home as fallback. Add a visible Rooms Zoo link beside the existing Home link.

- [ ] **Step 5: Compile and run tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_routing_security.py tests/test_zoo.py tests/test_onboarding_invitations.py`
Run: `/usr/bin/swiftc -parse-as-library -O -target arm64-apple-macos26.0 -framework AppKit -framework WebKit -framework Foundation native/AppDelegate.swift native/NativeSelfTest.swift -o packaging/build/ElectTwin`
Expected: tests PASS and Swift compilation succeeds.

---

### Task 4: Zoo feed, profiles, and shared responsive frontend

**Files:**
- Create: `web/zoo.js`
- Create: `web/zoo.css`
- Modify: `web/shell.html`
- Modify: `web/index.html`
- Modify: `tests/check_js.py`
- Create: `tests/test_frontend_contracts.py`

**Interfaces:**
- Consumes: Zoo state/routes from Task 1 and global shell helpers `api`, `esc`, `note`, `refresh`, `openRoom`.
- Produces: `zoo()`, `zooAgentProfile(id)`, `enhanceZooPage()`, accessible `data-zoo-*` actions.

- [ ] **Step 1: Write failing frontend contract tests**

Assert the shell contains The Zoo Network and Collaboration destinations; Zoo contains Top Thread, Room Zero, all four categories, the exact example title, simulated labels, local-only labels, accessible reaction `aria-pressed`, and no public/live/federated claim. Assert project navigation contains Zoo and the JavaScript checker includes the new scripts.

- [ ] **Step 2: Run contracts and JavaScript checks**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_frontend_contracts.py && python3 tests/check_js.py`
Expected: contract FAIL before frontend implementation.

- [ ] **Step 3: Implement the shared Zoo view**

Rename the old `zoo()` view to `collaboration()`, retain its real Rooms gateway, and add a separate Zoo destination. Render the pinned example first, Room Zero local posting second, and category-filtered threads third. Keep agent statistics and permission/budget detail inside profile dialogs. Implement real local thread/post/follow/reaction mutations through `api()` and refresh from server state.

Use original whitelisted SVG variants with caps, geometric layers, color blocking, and collectible-figurine proportions. Do not fetch external images or copy existing characters. Provide accessible buttons, visible focus, tap details, and text labels in addition to color.

- [ ] **Step 4: Implement responsive and reduced-motion CSS**

Use flat surfaces, existing Elect Twin colors, no gradients/decorative shadows, and grids that collapse without horizontal document overflow at 375 px. Include `:focus-visible`, `prefers-reduced-motion`, scrollable dialogs, and reachable actions at 200% zoom.

- [ ] **Step 5: Run frontend and backend checks**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_frontend_contracts.py tests/test_zoo.py && python3 tests/check_js.py`
Expected: PASS.

---

### Task 5: Optional setup wizard and invitation-preview UI

**Files:**
- Create: `web/onboarding.js`
- Modify: `web/zoo.css`
- Modify: `web/shell.html`
- Modify: `tests/test_frontend_contracts.py`
- Modify: `tests/test_onboarding_invitations.py`

**Interfaces:**
- Consumes: onboarding/invitation routes from Task 2.
- Produces: `maybeShowSetup()`, `enhanceLocalPages()`, `showInvitationPreview(id)`, accessible setup and invitation dialogs.

- [ ] **Step 1: Add failing wizard/invitation contracts**

Assert Welcome, Providers, Collaborators steps; Skip setup and Not now; API key labels for all five providers; the subscription/API-access distinction; session-only/unverified copy; local-preview-only invitation wording; install/join steps; and no real Send invitation button.

- [ ] **Step 2: Implement the wizard**

Persist skip/completion through `/api/onboarding`. Let users connect multiple providers sequentially without closing the wizard, clear key fields after each attempt, and preserve other providers. Provide My Models and People return paths. Do not send model requests.

- [ ] **Step 3: Implement invitation previews**

Provide create, inviter view, invitee preview, accept/decline/cancel preview, copy with fallback, and delete. Default every sharing option to unchecked. Show the exact consent statement and that preview status changes do not alter membership. Show install/join instructions and the internal-build signing limitation instead of generating a public URL.

- [ ] **Step 4: Verify contracts and accessibility structure**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_frontend_contracts.py tests/test_onboarding_invitations.py && python3 tests/check_js.py`
Expected: PASS; dialogs have names/descriptions, step headings receive focus, status is announced, and close returns focus to the launcher.

---

### Task 6: End-to-end validation and 0.3.0 package

**Files:**
- Modify: `native/NativeSelfTest.swift`
- Modify: `tests/smoke_runtime.py`
- Modify: `packaging/Info.plist`
- Modify: `packaging/build.sh`
- Modify: `package.json`
- Modify: `README.md`
- Modify: `docs/INSTALL.md`
- Modify: `docs/SUPPORT-MATRIX.md`
- Create: `docs/ZOO-VERIFICATION.md`
- Create: `docs/WEB-AND-WINDOWS.md`
- Create: `demo/zoo/` screenshots and reports

**Interfaces:**
- Consumes: all previous routes and UI behavior.
- Produces: `Elect-Twin-0.3.0-arm64-internal.dmg` and SHA-256 sidecar, actual native first-launch/reopen evidence, and deployment/Windows boundaries.

- [ ] **Step 1: Extend bundled smoke tests**

Create a Zoo thread/post/reaction/follow, configure and disconnect two fixture provider keys without network, save onboarding state, create/accept an invitation preview, and assert private project/Rooms canaries never enter Zoo or invitation output. Reopen and verify persistence.

- [ ] **Step 2: Extend actual native validation**

Exercise wizard skip and return, Twin ↔ Zoo navigation, all categories, Top Thread simulated labels, Room Zero local posting, agent profile provenance, reactions/follows, invitation accept/decline preview with no membership change, project/Rooms regressions, and Zoo return from Rooms. Capture desktop, 920×640, 768 px, and 375 px WebKit layouts. Reopen and verify all local records. Keep the existing Tab assertion and add reaction `aria-pressed` checks.

- [ ] **Step 3: Run the complete offline verification suite**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_twin.py test_extra.py test_images.py test_control.py tests/test_native_features.py tests/test_zoo.py tests/test_onboarding_invitations.py tests/test_routing_security.py tests/test_frontend_contracts.py`
Run: `python3 tests/check_js.py && python3 tests/smoke_runtime.py && python3 tests/smoke_rooms.py`
Expected: all PASS with zero provider/LLM calls.

- [ ] **Step 4: Build and verify 0.3.0 without replacing 0.2.0**

Set version `0.3.0`, update About, and output `Elect-Twin-0.3.0-arm64-internal.dmg`. Mount read-only, copy the app, run native first-launch/reopen, verify `codesign --deep --strict`, record actual `spctl` rejection, confirm three arm64 executables, verify the checksum, stop test processes, and detach only the new test mount.

- [ ] **Step 5: Final documentation and evidence review**

Document real local behavior, simulated examples, unperformed live/multi-user tests, exact source/DMG locations, Windows requirements, and the safest sequence for production accounts, invitations, signing/notarization, web hosting, and eventual host routing. Check that no screenshot/report contains a provider key, session token, private project canary, or Rooms bearer link.
