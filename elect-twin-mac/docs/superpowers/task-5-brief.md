# Task 5: Optional setup wizard and invitation-preview UI

Work only in `/Users/mac/Documents/Kimi/Workspaces/ElecTWIN/elect-twin-mac`. Tasks 1–4 are complete and reviewed: 22 frontend contracts and 66 required tests pass; JS checks pass. Create `web/onboarding.js`; modify `web/zoo.css`, `web/shell.html`, `tests/test_frontend_contracts.py`, `tests/check_js.py`, and backend tests only if a real integration gap is found. Preserve all Zoo interaction/focus fixes and inline/standalone source synchronization.

Follow strict TDD: add failing wizard/invitation contracts and observe expected failures before implementation. Run JS checks after. No Git repository: do not initialize or commit. No provider/model calls, paid operations, real invitations, public URLs, deployment, DNS, or changes outside this source directory.

## Setup wizard

Produce `maybeShowSetup()`, `enhanceLocalPages()`, and accessible setup dialogs. Steps: Welcome/privacy, Providers, Collaborators. Every step is optional, skippable, and returnable. Include `Skip setup` and `Not now`. Persist skip/completion via existing `/api/onboarding`; reopening from My Models or People must work without resetting provider or onboarding state.

Every provider uses an **API key**, never OAuth/subscription sign-in. Include all five existing providers (OpenAI, Anthropic, Gemini, Mistral, Groq) with independent fields/buttons. Clearly state:
- Ordinary web subscriptions do not automatically include API access.
- Charges depend on the provider account.
- Output limits are not a spending cap.
- Fixture/local configuration is session-only and unverified until a real provider request, which this wizard never makes.

Allow connecting multiple providers sequentially without closing the wizard, clear the key field after each attempt, preserve other providers, and use existing `/api/connect`/`/api/disconnect` without model requests. Never display/log stored keys. My Models and People provide return paths.

## Invitation previews

Produce `showInvitationPreview(id)` and accessible inviter/invitee preview dialogs. Provide local create, inviter view, invitee preview, accept/decline/cancel preview, copy with fallback, and delete. Do not provide a real `Send invitation` button or generate a public acceptance URL. `clipboard.writeText` may copy only a local explanatory preview, never a bearer/session link; provide a selectable-text fallback when clipboard is unavailable.

Every sharing option defaults unchecked. Show the exact consent statement and explain that accepting/declining/cancelling changes only the preview record: nothing is sent, no account/membership/access changes, and no private project content is shared. Store/display only the fields allowed by `collaboration.py`. Include install/join steps and the internal-build signing limitation rather than pretending a public join flow exists.

## Accessibility and design

Match the flat editorial Zoo/Twin visual system, with no new gradients/shadows/external assets. Dialogs need accessible names/descriptions, step headings receive focus, status is announced, close returns focus to the launcher (including rerenders), all actions work by keyboard/touch, and narrow/200%-zoom layouts remain reachable. Respect reduced motion. Keep wizard optional rather than blocking navigation.

## Tests

Add structural and meaningful DOM behavior contracts for Welcome/Providers/Collaborators, skip/not-now persistence and return, five API-key labels and subscription/API distinction, sequential independent provider configuration and field clearing without network, invitation unchecked defaults/create/status/delete/copy fallback/no-send/no-membership language, and focus/status semantics. Synchronize `web/onboarding.js` inline in `web/shell.html` just like Zoo, and extend `tests/check_js.py`.

Run:

`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_frontend_contracts.py tests/test_onboarding_invitations.py tests/test_zoo.py tests/test_routing_security.py tests/test_native_features.py`

`python3 tests/check_js.py`

Write RED/GREEN evidence, implementation summary, exact counts and JS result to `docs/superpowers/task-5-report.md`. Return only status, test summary, and concerns.
