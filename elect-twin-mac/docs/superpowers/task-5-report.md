# Task 5 report: Optional setup wizard and invitation-preview UI

Status: DONE

## Baseline

Before adding Task 5 contracts or production code, the required suite passed:

```text
Ran 66 tests in 6.639s

OK
```

The existing JavaScript checker also passed for `web/index.html`, `web/shell.html`, `web/zoo.js`, and the bundled Rooms document.

## RED evidence

I added the wizard and invitation structural/DOM behavior contracts to `tests/test_frontend_contracts.py` before creating `web/onboarding.js` or changing the frontend. I ran:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_frontend_contracts.py
```

Result:

```text
Ran 34 tests in 1.898s

FAILED (failures=12)
```

All 22 prior frontend contracts still passed. The 12 new contracts failed for the expected missing features: absent standalone/inline onboarding source and checker coverage, missing wizard steps/provider boundaries/return paths, missing invitation consent/create/status/delete/copy/install UI, and absent DOM behavior for skip/not-now persistence, sequential provider configuration, field clearing, focus, and copy fallback.

## GREEN evidence

After implementing and synchronizing the wizard, dialogs, invitation previews, responsive styles, and checker coverage:

```text
Ran 34 tests in 2.498s

OK
```

The behavior contracts execute `web/onboarding.js` with a DOM/event harness. They exercise first-run and explicit return navigation, per-step heading focus, skip/not-now route persistence, replacement-launcher focus, sequential independent connect/disconnect operations, successful and failed key-field clearing, unchecked invitation creation, preview status/delete operations, safe clipboard fallback, and preview-only/privacy language.

## Additional accessibility review: RED and GREEN

Final self-review identified two focus-return cases not covered by the first green run: an invitee close could select the inviter action on the same record, and a create dialog launched inside setup could return to the underlying People button after a rerender. I added both regressions before changing production code and ran:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_frontend_contracts.OnboardingFrontendContractTests.test_invitee_close_restores_the_equivalent_view_launcher_behavior tests.test_frontend_contracts.OnboardingFrontendContractTests.test_nested_create_close_restores_setup_launcher_after_rerender_behavior
```

RED result:

```text
Ran 2 tests in 0.498s

FAILED (failures=2)
```

After retaining launcher view/source descriptors and selecting the equivalent connected launcher:

```text
Ran 2 tests in 0.659s

OK
```

All frontend contracts then passed:

```text
Ran 36 tests in 2.649s

OK
```

## Final required verification

Exact required Python command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_frontend_contracts.py tests/test_onboarding_invitations.py tests/test_zoo.py tests/test_routing_security.py tests/test_native_features.py
```

Result:

```text
Ran 80 tests in 8.363s

OK
```

Exact required JavaScript command:

```sh
python3 tests/check_js.py
```

Result:

```text
JavaScript syntax passed: web/index.html
JavaScript syntax passed: web/shell.html
JavaScript syntax passed: web/zoo.js
JavaScript syntax passed: web/onboarding.js
JavaScript syntax passed: rooms-reference/Elect Twin Rooms.app/Contents/Resources/server/_internal/web/index.html
```

A separate exact-source assertion confirmed that standalone and inline `web/zoo.js`, `web/zoo.css`, and `web/onboarding.js` all match their copies in `web/shell.html`.

## Implementation summary

- Created `web/onboarding.js` with `maybeShowSetup()`, `enhanceLocalPages()`, `showInvitationPreview(id)`, and local event/dialog helpers.
- Replaced automatic single-provider prompting with a returnable Welcome / privacy, Providers, and Collaborators wizard. Skip setup, Not now, and completion use `/api/onboarding`; explicit reopening does not mutate onboarding or provider state.
- Added five independent API-key forms for OpenAI, Anthropic, Gemini, Mistral, and Groq. Sequential connect/disconnect operations use only existing connection routes, leave the wizard open, clear the submitted field after success or failure, preserve other provider fields/configurations, and make no model request.
- Added explicit subscription/API-access, provider-charge, output-limit, session-only, and unverified-access explanations. Stored keys are never rendered or logged.
- Added My Models and People return paths plus a People invitation-preview list using only the existing server-controlled record fields.
- Added local create, inviter/invitee views, simulated accept/decline/cancel outcomes, delete, and explanatory copy. Sharing flags default unchecked and remain consent flags only.
- Included the exact local-preview consent statement, preview-only status language, install/join steps, and internal-build Developer ID/notarization/Gatekeeper limitation. There is no Send invitation action, public acceptance link, bearer/session link, delivery, membership change, or private project content sharing.
- Added clipboard-failure fallback using a focused, selectable read-only textarea containing only the local explanatory preview.
- Added named/described dialogs, focused step/view headings, polite status and assertive error announcements, keyboard/touch-sized controls, narrow/zoom-friendly wrapping, scrollable dialogs, reduced-motion handling, and flat styles without gradients, shadows, or external assets.
- Extended `tests/check_js.py` for standalone `web/onboarding.js`; mirrored the standalone JavaScript and updated shared CSS inline in `web/shell.html` for document-only routes.
- Preserved all prior Zoo interactions and focus fixes. No backend integration gap was found, so backend production code and backend tests were unchanged.

No Git operations, provider/model calls, real invitations, public URLs, paid operations, deployment, DNS changes, external assets, or changes outside this source directory were made.

## Concerns

None.
