# Task 1: Persistent Zoo store and privacy boundary

Work only in `/Users/mac/Documents/Kimi/Workspaces/ElecTWIN/elect-twin-mac`.

Create `zoo.py` and `tests/test_zoo.py`; modify `twin.py` and, only if needed for its existing source contracts, `tests/test_native_features.py`.

Follow strict TDD: write the tests, run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_zoo.py`, and observe the expected missing-module failure before implementing. Then run all relevant old and new tests. There is no Git repository: do not initialize one or commit.

## Required interface and routes

`ZooStore(path)`, `.state() -> dict`, `.act(route: str, data: dict) -> dict`, `.close()`.

Routes: `GET /api/zoo/state`, `POST /api/zoo/thread`, `/api/zoo/post`, `/api/zoo/reaction`, `/api/zoo/reaction/delete`, `/api/zoo/follow`, `/api/zoo/unfollow`.

Use a physically separate JSON-row SQLite database with tables `threads`, `posts`, `reactions`, and `follows`. Fixed IDs: `room-zero`, `free-for-all`, `lets-collaborate`, `human-challenges`, `ideas-experiments`. Seed examples with fixed IDs and `INSERT OR IGNORE`.

Required category titles in order: Free for All, Let’s Collaborate, Human Challenges, Ideas & Experiments. Pinned simulated example thread title: What’s the deal with people? Example identities/messages/activity must all be explicitly marked simulated.

Local thread shape, enforced by the server even when the caller forges fields:

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

Allow reactions only `appreciate`, `curious`, `idea`. Counts must derive only from real local rows, begin at zero, and be exact after add/remove/idempotent repeats. Follows persist and allow only existing agents, rooms, and threads. Agent profiles expose `identity_origin`, `execution_mode`, `connectivity`; connectivity can be `local_only` or `unverified_external` only, never a claim of external interoperability.

Test local thread/post creation, rejection of forged provenance/visibility, reopen persistence and seed idempotency, unknown targets/reactions/input limits, and privacy canaries (`private-project-canary`, `provider-key-canary`, `rooms-token-canary`) absent from serialized state. Zoo content must stay out of Twin library search and provider preview context.

## Twin integration

Add `zoo_path=None` to `Twin.__init__`; default to `zoo.sqlite3` beside the Twin DB. Instantiate `ZooStore`. Delegate `/api/zoo/*` except state before the existing `self.project(...)` fallback in `Twin.act()`. Serve authenticated `GET /api/zoo/state` under the Twin lock. Do not add Zoo data to `Twin.state()`, `library_search()`, or `preview()`.

Preserve all 0.2.0 behavior and artifacts. No provider/LLM calls, deployment, DNS, publishing, real invitations, external-agent claims, or modifications outside this source directory. Close Zoo storage in `main()` shutdown if you touch that path; later native integration will add `--zoo-data`.

Final verification command:

`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_zoo.py tests/test_native_features.py test_twin.py test_extra.py test_images.py test_control.py`

Write a concise implementation and exact test report to `docs/superpowers/task-1-report.md`, including initial RED output and final counts. Return only status, test summary, and concerns.
