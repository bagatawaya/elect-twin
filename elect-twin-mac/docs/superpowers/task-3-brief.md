# Task 3: Shared routes and native security hardening

Work only in `/Users/mac/Documents/Kimi/Workspaces/ElecTWIN/elect-twin-mac`. Tasks 1–2 are complete and reviewed: 75 backend tests pass. Modify `twin.py`, `native/AppDelegate.swift`, `rooms-reference/Elect Twin Rooms.app/Contents/Resources/server/_internal/web/index.html` only as required, and create `tests/test_routing_security.py`. Do not implement Zoo frontend visuals in this task.

Follow strict TDD: write failing route/security tests, run them and observe expected failures before production edits. No Git repository: do not initialize or commit. Do not modify the separate `reference/Elect Twin Rooms.app`, other workspaces, active remote sessions, DNS, hosting, or Google Sites. No provider/network calls.

## Routes

Parse request paths with `urlparse(self.path).path`, not raw comparisons. Preserve `/`, `/home`, `/projects` and all existing token/Host/Origin checks. Serve:
- `/twin`, `/twin/projects` as project `index.html`.
- `/zoo`, `/zoo/rooms/room-zero`, `/zoo/categories/<id>`, `/zoo/threads/<id>`, `/zoo/agents/<id>` as `shell.html` for the named valid fixed categories and existing local/example thread/agent IDs as appropriate; malformed/unknown paths stay 404.
- Do not inspect Host to choose a public product experience. `twin.electri.ai` and `zoo.electri.ai` remain future entry points only.
- Zoo GET API requires existing local authentication. Zoo responses never include project/provider/Rooms-token canaries.
- Preserve existing asset/API behavior and loopback Host/Origin protections. Only explicitly named frontend documents/static assets are served; unknown paths remain 404. Include future `zoo.js`, `zoo.css`, `onboarding.js` in the static whitelist if implementing asset serving now, without creating those frontend files in this task.

Add `--zoo-data` argparse support and pass it to `Twin`; native storage remains separate. Close both stores on shutdown (already partly implemented).

## Native hardening

In `native/AppDelegate.swift`, before `rooms.run()` remove these inherited variables from the Rooms process environment:

```swift
let providerEnvironmentKeys = [
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
    "MISTRAL_API_KEY", "GROQ_API_KEY"
]
providerEnvironmentKeys.forEach { roomsEnvironment.removeValue(forKey: $0) }
```

Pass the separate Zoo path to Twin:

```swift
let zooData = root.appendingPathComponent("zoo.sqlite3").path
twin.arguments = ["--native", "--port", "0", "--data", twinData,
                  "--zoo-data", zooData]
```

Handle `elect-twin://zoo` using the existing loopback origin and session fragment, with Home as safe fallback. Do not weaken existing navigation/token controls. Add a visible Rooms `elect-twin://zoo` link beside its existing Home link; keep the deterministic local Rooms behavior unchanged.

## Tests and compile

Create real temporary-server tests for whitelisted routes, query parsing, 404s, Zoo authentication and private-canary exclusion. Add source-level tests asserting environment scrubbing occurs before `rooms.run()`, `--zoo-data` is passed, and Rooms exposes the Zoo return. Avoid brittle tests where practical.

Run:

`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_routing_security.py tests/test_zoo.py tests/test_onboarding_invitations.py tests/test_native_features.py test_twin.py test_extra.py test_images.py test_control.py`

Compile exactly:

`/usr/bin/swiftc -parse-as-library -O -target arm64-apple-macos26.0 -framework AppKit -framework WebKit -framework Foundation native/AppDelegate.swift native/NativeSelfTest.swift -o packaging/build/ElectTwin`

Write RED/GREEN evidence, exact test count, and compile result to `docs/superpowers/task-3-report.md`. Return only status, test/compile summary, and concerns.
