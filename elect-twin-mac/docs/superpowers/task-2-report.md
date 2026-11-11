# Task 2 report: onboarding preferences and invitation-preview records

## Scope and constraints

- Worked only in `elect-twin-mac`.
- Added `collaboration.py` and `tests/test_onboarding_invitations.py`; modified `twin.py` additively.
- Preserved `zoo.py` and the Task 1 Twin/Zoo integration.
- Did not initialize Git, commit, make provider/LLM/network calls, deploy, send invitations, or change membership/shared content.

## Baseline evidence

Command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_zoo.py tests/test_native_features.py test_twin.py test_extra.py test_images.py test_control.py
```

Result:

```text
................................................................
----------------------------------------------------------------------
Ran 64 tests in 2.393s

OK
```

## RED evidence

The new test module was written before `collaboration.py` existed and before onboarding/invitation changes were made to `twin.py`.

Command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_onboarding_invitations.py
```

Initial result:

```text
Ran 11 tests in 0.056s

FAILED (errors=12)
```

The failures were the expected missing-feature failures: `KeyError: 'onboarding'`, `ValueError: Unknown action` for `/api/invitation-preview`, and the missing onboarding route falling through to `ValueError: Project not found`. One invalid-onboarding test initially passed only because it accepted any `ValueError`; before writing production code, that assertion was tightened to require an onboarding-specific validation error so it could not pass on the missing route.

The exact RED command was rerun after that test-only correction:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_onboarding_invitations.py
```

Final pre-production RED result:

```text
Ran 11 tests in 0.057s

FAILED (failures=9, errors=12)
```

All 11 tests now failed for the absent features. SubTest cases account for the separate failure/error entries. Representative observed failures:

```text
KeyError: 'onboarding'
ValueError: Unknown action
AssertionError: "onboarding status" does not match "Project not found"
```

No production code was written until this RED run was complete.

## GREEN evidence

Focused command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_onboarding_invitations.py
```

Result:

```text
...........
----------------------------------------------------------------------
Ran 11 tests in 0.079s

OK
```

## Exact final command and result

Command copied exactly from the brief:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_onboarding_invitations.py tests/test_zoo.py tests/test_native_features.py test_twin.py test_extra.py test_images.py test_control.py
```

Result:

```text
...........................................................................
----------------------------------------------------------------------
Ran 75 tests in 2.481s

OK
```

This comprises the 11 new Task 2 tests plus the original 64 tests.

## Implementation summary

### `collaboration.py`

Added `InvitationStore(db)` with the required interface:

- `list() -> list[dict]`
- `create(data, project) -> dict`
- `set_status(id, status) -> dict`
- `delete(id) -> dict`

The store creates and uses the Twin-side `invitation_previews(id TEXT PRIMARY KEY, body TEXT NOT NULL)` table. Records have the server-controlled UUID/timestamp shape from the brief, with `draft`, `simulated=True`, `delivery='not_sent'`, and `membership_changed=False` enforced by the server.

Validation and state behavior:

- Recipient name and role are required, trimmed, nonempty strings limited to 200 characters.
- Contact is optional, trimmed, and limited to 320 characters; non-string values other than `None` are rejected.
- Project IDs are validated and resolved against an existing project; project ID/name are copied as a snapshot.
- Sharing defaults to `goal=False`, `documents=False`, `history=False`; only those keys and actual booleans are accepted.
- Only `draft -> accepted_preview`, `draft -> declined_preview`, and `draft -> cancelled_preview` transitions are allowed. Terminal records cannot transition again.
- Invalid statuses, transitions, malformed IDs, unknown IDs, and repeated deletion raise `ValueError`.
- Unknown input fields are not copied. Document bodies, decisions, messages, credentials, tokens, bearer links, and private notes therefore cannot enter preview records through create input.

### `twin.py`

- Added the default persistent profile value `onboarding={'status':'not_started','updated_at':None}` while retaining compatibility with existing profiles that lack the field.
- Added `/api/onboarding`, accepting only `skipped` and `completed`, updating only `local_profile.onboarding` and its timestamp.
- Added `/api/invitation-preview`, `/api/invitation-preview/status`, and `/api/invitation-preview/delete` dispatch through `InvitationStore` under the existing Twin lock.
- Added `invitation_previews` to authenticated Twin state for listing and reopen persistence.
- Left provider connect/disconnect behavior unchanged: fixture keys remain independently configurable in session memory, unverified, and absent from onboarding updates.

## Test coverage

The new tests cover:

- Default, skipped, and completed onboarding state, reopen persistence, timestamps, and invalid status rejection.
- Two independent fixture provider keys, disconnect independence, onboarding independence, secret omission, and zero transport/network calls.
- Server-controlled preview shape, optional contact, recipient/role/project/contact limits, sharing defaults, and strict boolean/type validation.
- Create/list/reopen, table presence, all allowed status transitions, invalid transitions/statuses/targets, deletion, and deletion persistence.
- Accept/decline/cancel isolation from project snapshots and `room_urls()`, with no delivery, membership change, actual sharing, provider transport, or network request.
- Private document, decision, message, provider-key, Rooms-token, and private-note canaries excluded from create output, state listing, and stored invitation JSON.
- All existing Zoo/Twin/native/provider/image/control regression behavior through the exact final 75-test command.

## Concerns

None.
