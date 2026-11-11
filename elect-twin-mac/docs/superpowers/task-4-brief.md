# Task 4: Zoo feed, profiles, and shared responsive frontend

Work only in `/Users/mac/Documents/Kimi/Workspaces/ElecTWIN/elect-twin-mac`. Tasks 1–3 are complete and reviewed: 88 backend/routing tests pass and Swift compiles. Create `web/zoo.js`, `web/zoo.css`, `tests/test_frontend_contracts.py`; modify `web/shell.html`, `web/index.html`, `tests/check_js.py` only as needed. Onboarding/invitation UI is Task 5, not this task.

Follow strict TDD: create failing frontend contract tests and run them before implementation. Run the JavaScript checker after implementation. No Git repository: do not initialize or commit. No external images/fonts, provider calls, deployment, public/live/federated claims, real invitations, or external-agent claims.

## Existing integration and naming

The shared frontend uses global helpers `api`, `esc`, `note`, `refresh`, `openRoom`. Rename the existing `zoo()` Rooms gateway view to `collaboration()` and update its destination/navigation. Add a distinct Zoo feed destination while preserving the real deterministic Rooms gateway.

Expected nine page IDs: `home`, `models`, `projects`, `twin`, `people`, `collaboration`, `challenges`, `following`, `zoo`. Existing native assertions for eight destinations and “Agent Zoo” will be updated in Task 6; if current source-level native tests require additive updates now, keep them truthful and minimal.

Produce global functions `zoo()`, `zooAgentProfile(id)`, `enhanceZooPage()` and accessible `data-zoo-*` actions. Add Zoo navigation to the project workspace. Rooms already has `elect-twin://zoo` from Task 3.

## Real and simulated behavior

Consume the existing Zoo state/routes. Render the pinned example Top Thread first, Room Zero local posting second, category-filtered threads third. Required four categories: Free for All, Let’s Collaborate, Human Challenges, Ideas & Experiments. Exact pinned example title: What’s the deal with people?

Every example identity/message/activity/Top Thread must say Simulated example. Local user posts must say exactly `Stored on this Mac · not published`. Implement real local thread/post/follow/reaction mutations through `api()` and refresh from server state. Reactions are appreciate/curious/idea with exact server counts and `aria-pressed`; starts at zero. Follows persist. Keep agent statistics, permissions/activity/budget detail in profile dialogs, not crowded into the feed. Profiles must show `identity_origin`, `execution_mode`, `connectivity`, with external connectivity unavailable/unverified. No fake trending, engagement totals, public federation, autonomous agents, agent-led governance, or peer-to-peer resilience.

Support local path routes already implemented: `/zoo`, `/zoo/rooms/room-zero`, `/zoo/categories/<id>`, `/zoo/threads/<id>`, `/zoo/agents/<id>` and Twin navigation. These are local routes only, not hostname/deployment behavior.

## Visual direction and craft

Use the existing Elect Twin palette and flat surfaces; no gradients, decorative shadows, glassmorphism, external assets, emoji icon containers, or card-in-card nesting. Make the feed a scannable editorial index: thread rows use a compact metadata rail with bracketed provenance/category values, strong readable titles, and dividers instead of decorative frames. Give the pinned example a distinctive archival-index treatment without implying popularity. Use quiet system typography, sparse uppercase navigation labels, and visible text labels in addition to color. Preserve the existing fixed navigation’s responsive collapse.

Create original inline SVG collectible-figurine portrait variants with abstract caps/layers/color blocking/geometric details, large heads/simple bodies and carefully aligned shapes. No copied characters, national stereotypes, external image downloads, or blank/mismatched placeholders. Portraits should be the main visual carrier in agent/profile contexts, not decorative stock imagery.

All controls work with keyboard and touch. Include semantic buttons/dialog names, `:focus-visible`, meaningful status announcements, `aria-pressed`, scrollable dialogs, reduced-motion support, and layouts that avoid horizontal document overflow at 375px and remain usable at 200% zoom. Do not add meaningless motion.

## Tests

Contract tests must assert The Zoo Network and Collaboration destinations, Top Thread/Room Zero/all categories/exact example title, Simulated example and exact local-only labels, accessible reactions, original SVG portraits, responsive/reduced-motion/focus rules, project Zoo navigation, and JS checker coverage. Include negative checks against unsupported public/live/federated claims. Tests should validate structure and behavior contracts rather than merely count keywords.

Run:

`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_frontend_contracts.py tests/test_zoo.py tests/test_onboarding_invitations.py tests/test_routing_security.py tests/test_native_features.py`

`python3 tests/check_js.py`

Write RED/GREEN evidence, implementation summary, exact test counts and JS result to `docs/superpowers/task-4-report.md`. Return only status, test summary, and concerns.
