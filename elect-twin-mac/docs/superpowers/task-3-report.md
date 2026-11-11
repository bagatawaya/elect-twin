# Task 3: Shared routes and native security hardening

## Scope

Implemented only the requested shared routing and native hardening changes in `twin.py`, `native/AppDelegate.swift`, and the copied Rooms reference HTML. Added `tests/test_routing_security.py`. No Zoo frontend assets or visuals were created. No provider or external network calls were made.

## RED evidence

Before production edits, ran:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_routing_security.py
```

Result: **Ran 13 tests; FAILED (failures=29), with no errors.** The failures were the expected missing behavior: shared Twin/Zoo document routes, query parsing, local thread routing, `--zoo-data` parsing/forwarding, Rooms provider-environment scrubbing, the native Zoo deep link, and the Rooms Zoo return link.

## GREEN evidence

After the minimal implementation, ran the same new-module command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_routing_security.py
```

Result: **Ran 13 tests in 4.718s; OK.**

The tests use a real temporary loopback server and real temporary Twin/Zoo stores. They cover existing and new document routes, query strings, valid fixed and created Zoo IDs, malformed/unknown 404s, Zoo GET authentication, Host/Origin enforcement, private project/provider/Rooms-token canary exclusion, POST path parsing, CLI forwarding and shutdown closure, and native source-level security requirements.

## Exact full regression command

Ran the brief's exact command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_routing_security.py tests/test_zoo.py tests/test_onboarding_invitations.py tests/test_native_features.py test_twin.py test_extra.py test_images.py test_control.py
```

Result: **Ran 88 tests in 7.256s; OK.** This preserves the 75 passing Tasks 1–2 tests and adds 13 passing Task 3 tests.

## Exact Swift compile command

Ran the brief's exact command:

```sh
/usr/bin/swiftc -parse-as-library -O -target arm64-apple-macos26.0 -framework AppKit -framework WebKit -framework Foundation native/AppDelegate.swift native/NativeSelfTest.swift -o packaging/build/ElectTwin
```

Result: **Exit code 0; compile succeeded with no diagnostics.** Output: `packaging/build/ElectTwin`.
