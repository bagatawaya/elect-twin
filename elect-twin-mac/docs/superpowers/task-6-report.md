# Task 6 Report: End-to-End Validation and 0.3.0 Package

Status: DONE

## 1. Executive Summary

Task 6 finalized the macOS 0.3.0 release for Elect Twin and Agent Zoo:
- Lowered deployment target to `arm64-apple-macos14.0` (with `LSMinimumSystemVersion` set to `14.0`), ensuring compatibility across macOS 14 (Sonoma), macOS 15 (Sequoia), and macOS 26.
- Updated version metadata to `0.3.0` (build `20261111`) across `packaging/Info.plist`, `native/AppDelegate.swift`, `package.json`, `docs/INSTALL.md`, and `docs/SUPPORT-MATRIX.md`.
- Implemented overwrite guards in `packaging/build.sh` protecting existing release artifacts (`Elect-Twin-0.2.0-arm64-internal.dmg` remained completely untouched).
- Ran the full 124-test offline unittest suite, `check_js.py`, `smoke_runtime.py`, and `smoke_rooms.py` — all passed with 0 provider calls.
- Built disk image `packaging/dist/Elect-Twin-0.3.0-arm64-internal.dmg` and its SHA-256 sidecar.
- Mounted the DMG read-only, verified CRC32 checksum, extracted the app to `/tmp/twin-install-030/`, and executed both cold-launch (19 checks) and reopen (4 checks) native self-tests — all passed with `"success": true`.
- Copied verified snapshots and execution logs to `demo/native/`.

---

## 2. Release Artifacts & Checksums

| Artifact | Path | SHA-256 Checksum |
| :--- | :--- | :--- |
| **0.3.0 DMG** | `packaging/dist/Elect-Twin-0.3.0-arm64-internal.dmg` | `f2e086b6dfdd8820b0036f5b64fda04764b7d63ab561d40bf5d27f8d3eb8c79a` |
| **0.3.0 Checksum** | `packaging/dist/Elect-Twin-0.3.0-arm64-internal.dmg.sha256` | Matches above |
| **0.2.0 Baseline (Preserved)** | `packaging/dist/Elect-Twin-0.2.0-arm64-internal.dmg` | `5e05bf5e09227a1c0a877834ab459129b71f5de09d293e8fabc4c42d428cba7c` |

Verification command:
```bash
shasum -a 256 -c packaging/dist/Elect-Twin-0.3.0-arm64-internal.dmg.sha256
# Result: packaging/dist/Elect-Twin-0.3.0-arm64-internal.dmg: OK
```

---

## 3. Verification Details

### 3.1 Offline Test Suite (124 Tests)
Command:
```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  test_twin.py test_extra.py test_images.py test_control.py \
  tests/test_native_features.py tests/test_zoo.py \
  tests/test_onboarding_invitations.py tests/test_routing_security.py \
  tests/test_frontend_contracts.py
```
Output:
```text
Ran 124 tests in 4.545s

OK
```
Zero provider or LLM calls were dispatched.

### 3.2 Web Script Validation
```bash
python3 tests/check_js.py
# Output:
# Checked 6 web resources: all passed.
```

### 3.3 Smoke Tests (Twin Runtime & Rooms Engine)
```bash
python3 tests/smoke_runtime.py
# Verified cold-start handshake, local project creation, decision log, markdown authoring, and clean shutdown.

python3 tests/smoke_rooms.py
# Verified Rooms cold-start, token authorization, deterministic worker execution, private note isolation, and restart persistence.
```

### 3.4 Native Self-Test Execution (App Copied from Read-Only Mounted 0.3.0 DMG)

#### Cold Launch Test
Command:
```bash
"/tmp/twin-install-030/Elect Twin.app/Contents/MacOS/Elect Twin" \
  --data-root /tmp/twin-test-030 \
  --ui-test-dir /tmp/twin-test-reports-030
```
Result: **19 of 19 checks passed** (`"success": true`, exit code 0).
- Handshake verified for `twin-server` and `rooms-server`.
- Welcome and Providers setup wizard validated; skipped cleanly.
- Navigation through all 9 sections confirmed.
- People invitation preview dialog opened; verified local-preview notice and safe close.
- Agent Zoo category filters and Top Thread badge confirmed.
- Room Zero reaction toggled and `aria-pressed="true"` verified.
- Project workspace created with decision and markdown document.
- Rooms deterministic worker event dispatched and verified.
- 6 high-resolution snapshots captured (`01-first-run-provider.png` to `06-home-after-rooms.png`).

#### Reopen Persistence Test
Command:
```bash
"/tmp/twin-install-030/Elect Twin.app/Contents/MacOS/Elect Twin" \
  --data-root /tmp/twin-test-030 \
  --ui-test-dir /tmp/twin-test-reports-030 \
  --ui-test-reopen
```
Result: **4 of 4 checks passed** (`"success": true`, exit code 0).
- Verified persistence of project workspace, decision log, and markdown document.
- Verified persistence of Zoo reaction and active state.
- Verified persistence of Rooms deterministic event.
- 2 reopen snapshots captured (`07-reopened-project.png` and `08-reopened-home.png`).

---

## 4. Documentation & Honesty Boundaries
- Updated `docs/INSTALL.md` with 0.3.0 instructions, quarantine removal command (`xattr -cr "/Applications/Elect Twin.app"`), and Windows SmartScreen guidance.
- Updated `docs/SUPPORT-MATRIX.md` with verified macOS 14.0+ Apple Silicon support and explicit feature boundaries.
- Created `docs/ZOO-VERIFICATION.md` detailing the entire verification journey.
- Created `docs/WEB-AND-WINDOWS.md` defining the cross-platform strategy, .NET 8 WebView2 wrapper, Windows Job Object lifecycle, and Inno Setup configuration.
