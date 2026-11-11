# Task 4 report: Zoo feed, profiles, and shared responsive frontend

Status: DONE

## RED evidence

Before creating `web/zoo.js`, `web/zoo.css`, or modifying the frontend, I created `tests/test_frontend_contracts.py` and ran:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_frontend_contracts.py
```

Result:

```text
Ran 14 tests in 0.003s

FAILED (failures=12)
```

The failures were the expected missing-feature failures: absent Zoo source, missing nine-destination navigation, missing Zoo actions/routes/provenance/portraits/profile/responsive contracts, missing project Zoo navigation, and missing standalone JavaScript checker coverage. The first attempted run exposed a syntax error in the new test's project-navigation regular expression; I corrected that test error and reran to obtain the valid contract RED above before any production implementation.

## GREEN evidence

After implementation and correction of three frontend contract failures (category literals, feed-order wording, and inline-source newline synchronization):

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_frontend_contracts.py
```

```text
Ran 14 tests in 0.409s

OK
```

The suite includes a real Node-rendered behavior contract that checks section order, exact server reaction counts, selected and unselected `aria-pressed` states, and simulated/local provenance rather than only counting source keywords.

Required combined command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_frontend_contracts.py tests/test_zoo.py tests/test_onboarding_invitations.py tests/test_routing_security.py tests/test_native_features.py
```

Result:

```text
Ran 58 tests in 5.783s

OK
```

JavaScript command:

```sh
python3 tests/check_js.py
```

Result:

```text
JavaScript syntax passed: web/index.html
JavaScript syntax passed: web/shell.html
JavaScript syntax passed: web/zoo.js
JavaScript syntax passed: rooms-reference/Elect Twin Rooms.app/Contents/Resources/server/_internal/web/index.html
```

## Implementation summary

- Created `web/zoo.js` with global `zoo()`, `zooAgentProfile(id)`, and `enhanceZooPage()` functions.
- Created `web/zoo.css` with a flat editorial index, archival pinned treatment, bracketed metadata, responsive 375 px layouts, 200%-zoom-friendly wrapping, visible focus, scrollable dialogs, and reduced-motion rules.
- Created `tests/test_frontend_contracts.py` with 14 structural and behavioral contracts, including negative checks for unsupported public/live/federated claims.
- Renamed the existing Rooms gateway to `collaboration()` and retained its deterministic Jay/Alex Rooms behavior.
- Added nine page destinations, with Collaboration and The Zoo Network as separate views.
- Added the pinned Top Thread first, Room Zero local composition second, category-filtered thread index third, and simulated example identity directory fourth.
- Implemented local thread, post, reaction, and follow mutations through `api()` followed by `refresh()` and fresh `/api/zoo/state` state.
- Rendered appreciate/curious/idea counts directly from `reaction_counts`, with zero-preserving output and `aria-pressed` state derived from server reactions.
- Added original inline SVG collectible-figurine variants with abstract caps, geometric layers, color blocking, large heads, simple bodies, and accessible labels.
- Added named profile dialogs containing `identity_origin`, `execution_mode`, `connectivity`, external-connectivity boundaries, and statistics/permissions/activity/budget detail without inventing execution or spending.
- Added local path enhancement for room, category, thread, and agent routes, plus Twin and Collaboration navigation.
- Added The Zoo Network navigation to the project workspace.
- Extended `tests/check_js.py` to validate standalone `web/zoo.js` and attributed inline scripts.
- Mirrored the standalone Zoo CSS/JavaScript inline in `web/shell.html` because the existing document-only server intentionally keeps `/zoo.css` and `/zoo.js` as 404 routes; routing security tests remain unchanged and passing.

No Git operations, external assets, provider calls, invitation UI, deployment changes, backend changes, or external-agent claims were introduced.

## Interaction review fixes: RED evidence

Before the review-fix production edits, I added five DOM-level interaction regressions and one flexible-header CSS contract to `tests/test_frontend_contracts.py`, then ran:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_frontend_contracts.py
```

Result:

```text
Ran 20 tests in 1.007s

FAILED (failures=6)
```

The six failures were the requested behaviors: stale category after Back to `/zoo`, a newly created thread hidden by a stale filter, stale Follow text and `aria-pressed` in the open profile dialog, lost focus after reaction/feed-follow refresh, failure to find an equivalent launcher after rerender, and fixed-height project-header overlap risk.

## Interaction review fixes: GREEN and final verification

After route-derived filtering, refreshed dialog semantics, equivalent-control focus restoration, and flexible header changes:

```text
Ran 20 tests in 0.947s

OK
```

The behavioral regressions execute `web/zoo.js` with a DOM/event harness. They exercise route transitions, thread-form submission, profile-follow clicks, reaction/feed-follow refreshes, dialog close, and focus on replacement controls rather than checking source markers.

Final required combined command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_frontend_contracts.py tests/test_zoo.py tests/test_onboarding_invitations.py tests/test_routing_security.py tests/test_native_features.py
```

Result:

```text
Ran 64 tests in 6.498s

OK
```

Final JavaScript command:

```sh
python3 tests/check_js.py
```

Result:

```text
JavaScript syntax passed: web/index.html
JavaScript syntax passed: web/shell.html
JavaScript syntax passed: web/zoo.js
JavaScript syntax passed: rooms-reference/Elect Twin Rooms.app/Contents/Resources/server/_internal/web/index.html
```

Self-review was limited to the changed interaction and project-header code. `enhanceZooPage()` now resets category state for every route and derives a thread route's category from refreshed state. Reaction and feed-follow actions capture semantic control descriptors before refresh and restore focus to connected equivalents. Dialog follow actions update the currently visible button from refreshed state while keeping the dialog open, including when a direct agent-route refresh replaces dialog contents. Dialog launchers are captured as semantic descriptors only when opening, so rerenders do not disconnect the eventual focus-return target. Standalone and inline Zoo sources are synchronized. The project header now uses minimum heights, wrapping, gaps, and vertical padding at desktop and mobile widths rather than fixed heights.

## Closed-details focus review: RED evidence

Before changing the focus-restoration production code, I strengthened the DOM harness with parent links, real open/closed `details` behavior, and focusable summaries, then added the two concrete reviewer scenarios. The focused command was:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_frontend_contracts.FrontendContractTests.test_post_reaction_reopens_active_conversation_for_focus_behavior tests.test_frontend_contracts.FrontendContractTests.test_profile_close_skips_closed_author_and_uses_directory_or_summary_behavior
```

Result:

```text
Ran 2 tests in 0.605s

FAILED (failures=2)
```

The failures confirmed that a post reaction's replacement remained inside a closed conversation and that Alex profile close selected a hidden post-author control instead of the visible directory launcher.

## Closed-details focus review: GREEN and final verification

Focused GREEN result:

```text
Ran 2 tests in 0.512s

OK
```

All frontend contracts:

```text
Ran 22 tests in 1.185s

OK
```

Final required combined suite:

```text
Ran 66 tests in 6.490s

OK
```

Final JavaScript checker:

```text
JavaScript syntax passed: web/index.html
JavaScript syntax passed: web/shell.html
JavaScript syntax passed: web/zoo.js
JavaScript syntax passed: rooms-reference/Elect Twin Rooms.app/Contents/Resources/server/_internal/web/index.html
```

Focus descriptors now retain the originating conversation. Post-reaction restoration reopens that conversation before finding the equivalent control. Restoration rejects connected controls inside closed `details`, selects a visible equivalent such as the Alex directory launcher, and falls back to the originating conversation summary when no visible equivalent exists. Inline and standalone Zoo sources are synchronized.

## Concerns

None.
