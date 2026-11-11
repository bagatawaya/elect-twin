# Task 2: Onboarding preferences and invitation-preview records

Work only in `/Users/mac/Documents/Kimi/Workspaces/ElecTWIN/elect-twin-mac`. Task 1 is complete and reviewed: `zoo.py` and its Twin integration must remain intact. Create `collaboration.py` and `tests/test_onboarding_invitations.py`; modify `twin.py` additively. No frontend in this task.

Follow strict TDD: write failing tests and observe their expected route/store failure before production code. There is no Git repository: do not initialize or commit. No provider/LLM calls, networking, deployment, real invitations, or changes outside this source directory.

## Required interfaces

`InvitationStore(db)`, `.list() -> list[dict]`, `.create(data, project) -> dict`, `.set_status(id, status) -> dict`, `.delete(id) -> dict`.

Persistent onboarding state lives in existing `local_profile`: `{"status": "not_started" | "skipped" | "completed", "updated_at": float | None}`.

Routes: `/api/onboarding`, `/api/invitation-preview`, `/api/invitation-preview/status`, `/api/invitation-preview/delete`. Listing can be through Twin state or an explicit authenticated route if needed by existing conventions, but do not expose secrets.

Add Twin-side table `invitation_previews(id TEXT PRIMARY KEY, body TEXT NOT NULL)`. Server-controlled preview shape:

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

Allowed statuses: `draft`, `accepted_preview`, `declined_preview`, `cancelled_preview`. Default every sharing option false; if enabled they remain consent flags only, never actual shared content. Store recipient/contact/project name/role/sharing choices only—never document bodies, messages, decisions, keys, tokens, bearer links, or private notes. There is no public acceptance URL.

`/api/onboarding` accepts only `skipped` or `completed` and updates local profile; it never changes provider keys. Existing provider connect/disconnect behavior must remain session-memory only and independently configurable for multiple fixture keys with no verification/network request.

## Required tests

- skipped/completed persistence and invalid onboarding status.
- Two fixture provider keys configure/disconnect independently without transport/network; onboarding does not change them.
- Optional contact validation; recipient and field limits; unchecked sharing defaults and strict boolean/type validation.
- Create/list/reopen, allowed status transitions, invalid transitions/status/targets, delete/reopen.
- Preview accept/decline/cancel changes only its record: project snapshots and `room_urls()` stay exactly unchanged, no membership or sharing occurs.
- Private canaries (`private-document-canary`, private decisions/messages, provider key, Rooms token/private-note canary) never appear in preview output/listing.
- Existing Zoo/Twin behavior remains green.

Final command:

`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_onboarding_invitations.py tests/test_zoo.py tests/test_native_features.py test_twin.py test_extra.py test_images.py test_control.py`

Write exact RED/GREEN commands and results plus implementation summary to `docs/superpowers/task-2-report.md`. Return only status, one-line test summary, and concerns.
