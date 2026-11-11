# Elect Twin 0.2.0 — reuse, verification, and limitations

Verified on 2026-11-10 on macOS 26.5, Apple Silicon (`arm64`).

## Delivered build

- Disk image: `packaging/dist/Elect-Twin-0.2.0-arm64-internal.dmg`
- SHA-256: `5e05bf5e09227a1c0a877834ab459129b71f5de09d293e8fabc4c42d428cba7c`
- Checksum sidecar: `packaging/dist/Elect-Twin-0.2.0-arm64-internal.dmg.sha256`
- Bundle ID: `ai.electri.twin.internal`
- Declared minimum macOS: 26.0, inherited from the available Rooms engine
- Signing: ad-hoc; not Developer ID signed or notarized

The final DMG was mounted read-only, its app was copied to a separate install-test folder, and all native results below were produced from that copy. The checksum sidecar passed `shasum -a 256 -c`.

## What was reused and what was added

### Reused

- The verified Twin project workspace, provider adapters, SQLite behavior, context preview, explicit approval flow, local library, and baseline tests remain intact in the separate `elect-twin` source folder.
- The existing arm64 Rooms engine and `_internal` resources are bundled. Rooms retains its deterministic worker model, owner permissions, private-note isolation, jobs, handoffs, and persistence.
- The original Rooms prototype outside `elect-twin-mac/rooms-reference/` was not modified.

### Added or changed in the integrated app

- Original Swift/AppKit `WKWebView` shell with explicit delegate startup, loopback-only navigation, bundled engine lifecycle, native menus, isolated `--data-root` support, and keyboard Tab focus for links.
- Original Home, My Models, My Twin, People, Agent Zoo, Agent Challenges, Following, local profile, and real project activity presentation.
- Direct project and Rooms navigation, including the Rooms `← Elect Twin` return.
- Original flat SVG participant portraits and the **Counterpart**, **Relay**, and **Common Ground** editable branding concepts. Counterpart is the selected app icon.
- Rooms web changes are limited to the Elect Twin return link and matching participant portraits in worker cards and conversation events.
- A test-only native runner, active only with an explicit `--ui-test-dir` argument, exercises real WebKit flows and captures `WKWebView` snapshots. It makes no provider calls.

## Verification evidence

### Backend and runtime

The final source passed:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  test_twin.py test_extra.py test_images.py test_control.py \
  tests/test_native_features.py
python3 tests/check_js.py
python3 tests/smoke_runtime.py
python3 tests/smoke_rooms.py
```

Results:

- **49 tests passed**, including all 44 baseline tests.
- JavaScript syntax passed for Twin Home, the project workspace, and Rooms.
- Bundled Twin and Rooms cold start passed with isolated storage.
- Real local project and decision creation, challenge review, Following, and Rooms-link injection passed.
- Rooms owner authorization, a completed deterministic worker job, private-note isolation, and restart persistence passed.
- No provider or LLM calls were made.

### Actual native app from the final DMG

`demo/native/native-report.json` records a successful first launch covering:

- First-run provider setup and dismissal without entering or retaining a key.
- Home plus all seven other navigation destinations.
- A real Tab event moving from My Models to My Projects with a visible 3 px outline.
- Project, decision, and Markdown document creation through WebKit.
- Participant tap details.
- Challenge submission, explicit local review, and Following.
- Rooms owner authorization and a real deterministic worker completion.
- Return from Rooms to Twin Home with project context intact.

`demo/native/reopen-report.json` records a successful quit/reopen cycle restoring:

- The project, decision, and Markdown document.
- The reviewed challenge and Following entry.
- Rooms human and deterministic agent events.

Eight implementation screenshots are in `demo/native/`. They are actual `WKWebView` snapshots from the final copied app, not browser mockups or generated illustrations. All were visually reviewed.

### Package and process checks

- `codesign --verify --deep --strict` passed on the copied app.
- The native launcher, Twin server, and Rooms server are all Mach-O arm64 executables.
- `spctl -a -vv` returned `rejected` with exit status 3, consistent with an ad-hoc internal build.
- The checksum sidecar reports `OK`.
- No Elect Twin test app or bundled engine processes remained after validation.
- Only the Elect Twin test disk-image mount was detached; no original Rooms mount was targeted.

## Real versus simulated

- **Real:** local SQLite writes and persistence, project knowledge, challenge review state, Following references, Rooms membership/authorization, deterministic jobs and events, private-note isolation, and native navigation.
- **Local fixtures:** Jay and Alex are test identities on the same Mac, not remote people.
- **Deterministic, not an LLM:** Rooms produces a local context digest and does not call the five model providers.
- **Mock-tested only:** OpenAI, Anthropic, Gemini, Mistral, and Groq text adapters, plus OpenAI image generation.
- **Not verified:** provider credentials, account access, model availability, billing, or live generation quality. A configured badge means only that a session key exists.

## Limitations and release requirements

- Apple Silicon only. macOS 26.0 is declared, but only macOS 26.5 was tested. No compatibility claim is made for macOS 26.0–26.4 or earlier macOS versions.
- This is an internal test build. Do not bypass Gatekeeper. Public distribution requires Developer ID signing and notarization.
- No Google Drive sync, invitations, independent remote users, public discovery, federation, autonomous agents, arbitrary external tools, or live Rooms LLM is included.
- No scheduler is included; Scheduled was omitted rather than represented as working.
- Provider keys are session-only and are not shared with Rooms. There is no verified hard spending cap; provider-side billing controls remain necessary.
- Reduced-motion CSS is present, but the macOS reduced-motion setting was not toggled during native validation.
- The tested keyboard path passed, but this is not an independent VoiceOver, full keyboard-access, contrast, or accessibility audit.
- Native tests used isolated storage and did not migrate, delete, or overwrite either prototype database. Coexistence with a populated default native data directory was not separately exercised.
- Public release still requires independent security/accessibility review and authorized live-provider smoke tests.

## Installation and support

See `docs/INSTALL.md` for checksum verification, installation, first-run behavior, and storage paths. See `docs/SUPPORT-MATRIX.md` for feature-by-feature scope.
