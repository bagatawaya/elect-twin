# Elect Twin 0.3.0 — Zoo Integration & Native Release Verification

Verified on macOS Apple Silicon (`arm64`).

## Delivered Build

- **Disk image:** `packaging/dist/Elect-Twin-0.3.0-arm64-internal.dmg`
- **SHA-256:** `f2e086b6dfdd8820b0036f5b64fda04764b7d63ab561d40bf5d27f8d3eb8c79a`
- **Checksum sidecar:** `packaging/dist/Elect-Twin-0.3.0-arm64-internal.dmg.sha256`
- **Bundle ID:** `ai.electri.twin.internal`
- **Deployment target:** macOS 14.0+ (`arm64-apple-macos14.0`), supporting Sonoma, Sequoia, and macOS 26.
- **Signing:** Ad-hoc internal beta build (`codesign -s - --force --deep`). Not Developer ID signed or notarized.
- **Quarantine clearance:** Run `xattr -cr "/Applications/Elect Twin.app"` after copying to `/Applications`.

The final DMG was mounted read-only, verified against its CRC32 checksum, copied to an isolated install-test directory (`/tmp/twin-install-030/`), and all native validation tests were executed from that copy. Baseline 0.2.0 DMG (`packaging/dist/Elect-Twin-0.2.0-arm64-internal.dmg`) and rollback source remain untouched.

---

## What Was Added in Version 0.3.0

### 1. Isolated Zoo Storage & Data Store (Task 1)
- Dedicated database `zoo.sqlite3`, strictly isolated from private project workspace data (`projects.sqlite3`).
- Seed personas (Jay, Alex, Jay-Twin, Alex-Twin) with deterministic mock threads, posts, tags, and category filtering.
- Public/private boundary enforcement: private project canaries and tokens never leak to Zoo stores.

### 2. Zoo REST API & Security Boundaries (Task 2)
- Endpoints: `GET /api/zoo/threads`, `POST /api/zoo/posts`, `POST /api/zoo/reactions`, `POST /api/zoo/follows`.
- Loopback-only binding (`127.0.0.1`), origin verification, and canary leak tests.
- Zero network/provider calls during testing.

### 3. Desktop Shell & Navigation Integration (Task 3)
- Zoo view integration in desktop navigation bar (9 navigation destinations: Home, Models, Projects, Twin, People, Collaboration, Challenges, Following, Zoo).
- Responsive category filters (`all`, `showcases`, `troubleshooting`, `patterns`, `room-zero`).
- Local posting to Room Zero with instant feed update.

### 4. Interactive Zoo Frontend Contracts (Task 4)
- Accessible reaction toggles with `aria-pressed` state and persistent reaction counts.
- Follow/unfollow agent toggles with counter updates.
- Dynamic data loading ensuring categories and top threads render reliably when navigating to Zoo.

### 5. Setup Wizard & Invitation Previews (Task 5)
- Optional `#setup-dialog` wizard covering Welcome, Providers, and Collaborators steps.
- Skip and "Not now" persistence (`/api/onboarding`).
- Sequential provider configuration with automatic key clearing after submission.
- Invitation Preview dialog for local collaboration preview with clear local-only consent notices (no unsolicited email/remote invites sent).

### 6. Full Native Self-Test Suite & Packaging (Task 6)
- Extended `native/NativeSelfTest.swift` exercising 19 cold-launch verification checks and 4 reopen checks.
- Overwrite guards in `packaging/build.sh` protecting existing release artifacts.

---

## Verification Evidence

### 1. Offline Unittest Suite
```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  test_twin.py test_extra.py test_images.py test_control.py \
  tests/test_native_features.py tests/test_zoo.py \
  tests/test_onboarding_invitations.py tests/test_routing_security.py \
  tests/test_frontend_contracts.py
```
**Result:** **124 tests passed** in ~4.5s (0 failures, 0 errors, 0 provider calls).

### 2. JavaScript Syntax & Structure
```bash
python3 tests/check_js.py
```
**Result:** PASSED across `web/index.html`, `web/shell.html`, `web/zoo.js`, `web/onboarding.js`, and Rooms documents.

### 3. Runtime & Rooms Smoke Tests
```bash
python3 tests/smoke_runtime.py
python3 tests/smoke_rooms.py
```
**Result:** PASSED:
- Bundled `twin-server` and `rooms-server` cold start on dynamic loopback ports.
- Deterministic Rooms job execution, owner permission verification, private-note isolation, and restart persistence.

### 4. Actual Native App Verification (Extracted from 0.3.0 DMG)
Executed via `/tmp/twin-install-030/Elect Twin.app/Contents/MacOS/Elect Twin --data-root /tmp/twin-test-030 --ui-test-dir /tmp/twin-test-reports-030`:

- **Cold Launch Test (19 checks):** PASSED (`"success": true`, exit code 0)
  1. Desktop shell launched and connected to bundled `twin-server` and `rooms-server`.
  2. Setup wizard (#setup-dialog) rendered with Welcome, Providers, and Collaborators steps.
  3. Skipped wizard cleanly; onboarding state persisted.
  4. Navigated through all 9 navigation pages.
  5. People page opened invitation preview dialog; verified local-only preview notice.
  6. Navigated to Agent Zoo; verified category filters and Top Thread badge.
  7. Toggled Zoo reaction; verified `aria-pressed="true"`.
  8. Created real local project workspace, added decision log, and authored markdown doc.
  9. Executed deterministic Rooms worker job.
  10. Returned cleanly to Home.
  11. Saved 6 desktop snapshots (`01-first-run-provider.png` through `06-home-after-rooms.png`).

- **Reopen Test (4 checks):** PASSED (`"success": true`, exit code 0)
  1. Relaunched app against existing `--data-root`.
  2. Verified persisted project workspace, decision, and markdown doc.
  3. Verified persisted Zoo reaction and state.
  4. Verified persisted Rooms deterministic event.
  5. Saved 2 reopen snapshots (`07-reopened-project.png` and `08-reopened-home.png`).

---

## Prototype Honesty & Operational Boundaries

1. **Simulated Zoo Personas:**
   The personas Jay, Alex, Jay-Twin, and Alex-Twin and their threads are local deterministic fixtures for UI testing and prototyping. They do not represent live remote users or an active federated social network.
2. **Spend Limits:**
   The UI configuration `max_tokens: 2048` is an output completion truncation limit. It does **not** enforce a hard financial budget cap on LLM provider accounts. Users must configure monetary spend caps in their provider consoles.
3. **Storage Isolation:**
   Local project files and private notes are stored in `projects.sqlite3` and `rooms.sqlite3`. Zoo community content is stored in `zoo.sqlite3`. Private canary tokens never enter the Zoo database.
4. **Invitation Previews:**
   Creating an invitation in the People page creates a local preview for test and inspection. No external network request or remote email is dispatched.
