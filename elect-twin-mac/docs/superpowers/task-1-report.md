# Task 1 report: Persistent Zoo store and privacy boundary

## Status

DONE

## Implementation

- Added `zoo.py` with `ZooStore(path)`, `state()`, `act(route, data)`, and `close()`.
- Added a physically separate JSON-row SQLite database containing `threads`, `posts`, `reactions`, and `follows` tables. The database is created with mode `0600` and uses locked access for shared-thread use.
- Added fixed room/category IDs, the four required category titles in order, and fixed-ID `INSERT OR IGNORE` simulated seed content. The pinned thread is `What’s the deal with people?`; all example agents, threads, and posts are explicitly marked simulated.
- Implemented local thread/post creation with validated categories, existing-thread checks, text limits, server-controlled authorship/provenance/visibility, and rejection of forged local-boundary fields. Category IDs must be strings, so malformed list/dict JSON values produce `ValueError` rather than `TypeError`.
- Implemented `appreciate`, `curious`, and `idea` reactions. Reaction counts are calculated exclusively from persisted local reaction rows, start at zero, and remain exact across idempotent adds, repeated removals, and reopen.
- Implemented persistent, idempotent follows restricted to existing Zoo agents, rooms, and threads. Reaction deletion and unfollow return the same successful deletion result on repeated requests without changing serialized state; malformed non-string IDs remain validation errors.
- Agent profiles expose `identity_origin`, `execution_mode`, and `connectivity`; all current profiles are simulated and `local_only`. No external interoperability is claimed.
- Modified `twin.py` to accept `zoo_path=None`, default to `zoo.sqlite3` beside the Twin database, instantiate `ZooStore`, delegate non-state `/api/zoo/*` actions under the Twin lock before project fallback, and serve authenticated `GET /api/zoo/state` under the same lock.
- Twin/Zoo path identity is checked before loading or opening either store. Resolved-path comparison rejects identical paths and symlink aliases; `os.path.samefile` also rejects existing hard-link aliases. Rejections raise `ValueError` before `sqlite3.connect` or `ZooStore` construction.
- `main()` now closes Zoo storage during shutdown in addition to the Twin database.
- Twin project state, library search, and provider preview construction were not given access to Zoo data. No provider/LLM calls, networking features, deployment, DNS, publishing, invitations, or external-agent behavior were added.
- Added `tests/test_zoo.py` with 15 tests covering store behavior, persistence, validation, reactions, follows, pre-open path separation, Twin integration, HTTP authentication, privacy canaries, and search/provider-context isolation. `tests/test_native_features.py` required no changes.

## Required RED observation

Command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_zoo.py
```

Observed before creating `zoo.py`:

```text
E
======================================================================
ERROR: test_zoo (unittest.loader._FailedTest.test_zoo)
----------------------------------------------------------------------
ImportError: Failed to import test module: test_zoo
Traceback (most recent call last):
  File "/Applications/Kimi.app/Contents/Resources/resources/daimon-bundle/runtime/python/cpython-3.12/lib/python3.12/unittest/loader.py", line 137, in loadTestsFromName
    module = __import__(module_name)
             ^^^^^^^^^^^^^^^^^^^^^
  File "/Users/mac/Documents/kimi/Workspaces/ElecTWIN/elect-twin-mac/tests/test_zoo.py", line 15, in <module>
    from zoo import ZooStore
ModuleNotFoundError: No module named 'zoo'


----------------------------------------------------------------------
Ran 1 test in 0.000s

FAILED (errors=1)
```

This was the expected missing-module failure. No production implementation existed before this RED run.

## Initial new-suite GREEN result

The initial suite after implementation:

```text
............
----------------------------------------------------------------------
Ran 12 tests in 0.600s

OK
```

## Review-fix RED observations

Three tests were added for explicit identical paths, symlink aliases, and unhashable category IDs. The existing reaction/follow tests were strengthened to require successful repeated removals and byte-for-byte-equivalent serialized states. Before any review-fix production edits, the new suite was run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_zoo.py
```

Observed output:

```text
.F..F..E..E..EE.
======================================================================
ERROR: test_follows_validate_targets_are_idempotent_and_persist (tests.test_zoo.ZooStoreTests.test_follows_validate_targets_are_idempotent_and_persist)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/Documents/kimi/Workspaces/ElecTWIN/elect-twin-mac/tests/test_zoo.py", line 210, in test_follows_validate_targets_are_idempotent_and_persist
    repeated = self.store.act("/api/zoo/unfollow", {"id": item["id"]})
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/mac/Documents/kimi/Workspaces/ElecTWIN/elect-twin-mac/zoo.py", line 365, in act
    return self._unfollow(data)
           ^^^^^^^^^^^^^^^^^^^^
  File "/Users/mac/Documents/kimi/Workspaces/ElecTWIN/elect-twin-mac/zoo.py", line 345, in _unfollow
    raise ValueError("Followed Zoo item not found")
ValueError: Followed Zoo item not found

======================================================================
ERROR: test_reaction_counts_are_exact_idempotent_and_persistent (tests.test_zoo.ZooStoreTests.test_reaction_counts_are_exact_idempotent_and_persistent)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/Documents/kimi/Workspaces/ElecTWIN/elect-twin-mac/tests/test_zoo.py", line 171, in test_reaction_counts_are_exact_idempotent_and_persistent
    repeated = self.store.act("/api/zoo/reaction/delete", {"id": first["id"]})
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/mac/Documents/kimi/Workspaces/ElecTWIN/elect-twin-mac/zoo.py", line 361, in act
    return self._delete_reaction(data)
           ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/mac/Documents/kimi/Workspaces/ElecTWIN/elect-twin-mac/zoo.py", line 300, in _delete_reaction
    raise ValueError("Zoo reaction not found")
ValueError: Zoo reaction not found

======================================================================
ERROR: test_unhashable_category_ids_raise_value_error_without_creating_rows (tests.test_zoo.ZooStoreTests.test_unhashable_category_ids_raise_value_error_without_creating_rows) (category_id=[])
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/Documents/kimi/Workspaces/ElecTWIN/elect-twin-mac/tests/test_zoo.py", line 220, in test_unhashable_category_ids_raise_value_error_without_creating_rows
    self.store.act("/api/zoo/thread", {
  File "/Users/mac/Documents/kimi/Workspaces/ElecTWIN/elect-twin-mac/zoo.py", line 355, in act
    return self._thread(data)
           ^^^^^^^^^^^^^^^^^^
  File "/Users/mac/Documents/kimi/Workspaces/ElecTWIN/elect-twin-mac/zoo.py", line 221, in _thread
    if category_id not in {category["id"] for category in CATEGORIES}:
       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: unhashable type: 'list'

======================================================================
ERROR: test_unhashable_category_ids_raise_value_error_without_creating_rows (tests.test_zoo.ZooStoreTests.test_unhashable_category_ids_raise_value_error_without_creating_rows) (category_id={})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/Documents/kimi/Workspaces/ElecTWIN/elect-twin-mac/tests/test_zoo.py", line 220, in test_unhashable_category_ids_raise_value_error_without_creating_rows
    self.store.act("/api/zoo/thread", {
  File "/Users/mac/Documents/kimi/Workspaces/ElecTWIN/elect-twin-mac/zoo.py", line 355, in act
    return self._thread(data)
           ^^^^^^^^^^^^^^^^^^
  File "/Users/mac/Documents/kimi/Workspaces/ElecTWIN/elect-twin-mac/zoo.py", line 221, in _thread
    if category_id not in {category["id"] for category in CATEGORIES}:
       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: unhashable type: 'dict'

======================================================================
FAIL: test_identical_twin_and_zoo_paths_are_rejected_before_opening_stores (tests.test_zoo.TwinZooIntegrationTests.test_identical_twin_and_zoo_paths_are_rejected_before_opening_stores)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/Documents/kimi/Workspaces/ElecTWIN/elect-twin-mac/tests/test_zoo.py", line 279, in test_identical_twin_and_zoo_paths_are_rejected_before_opening_stores
    with self.assertRaisesRegex(ValueError, "physically separate"):
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: ValueError not raised

======================================================================
FAIL: test_symlink_aliased_twin_and_zoo_paths_are_rejected_before_opening_stores (tests.test_zoo.TwinZooIntegrationTests.test_symlink_aliased_twin_and_zoo_paths_are_rejected_before_opening_stores)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/Documents/kimi/Workspaces/ElecTWIN/elect-twin-mac/tests/test_zoo.py", line 293, in test_symlink_aliased_twin_and_zoo_paths_are_rejected_before_opening_stores
    with self.assertRaisesRegex(ValueError, "physically separate"):
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: ValueError not raised

----------------------------------------------------------------------
Ran 15 tests in 0.624s

FAILED (failures=2, errors=4)
```

These were the intended failures: missing pre-open path rejection, `TypeError` for list/dict categories, and non-idempotent reaction/follow removal.

## Review-fix new-suite GREEN result

After only the three targeted production fixes:

```text
...............
----------------------------------------------------------------------
Ran 15 tests in 0.635s

OK
```

## Exact final regression

Command run verbatim:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_zoo.py tests/test_native_features.py test_twin.py test_extra.py test_images.py test_control.py
```

Output:

```text
................................................................
----------------------------------------------------------------------
Ran 64 tests in 2.391s

OK
```

Final count: **64 tests run, 64 passed, 0 failures, 0 errors**.

## Concerns

None.
