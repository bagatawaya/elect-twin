#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
BUILD="$(mktemp -d "${TMPDIR:-/tmp}/opentwin-update-tests.XXXXXX")"
trap 'rm -rf "$BUILD"' EXIT
swiftc -parse-as-library -swift-version 5 native/UpdateChecker.swift tests/UpdateCheckerTests.swift -o "$BUILD/update-tests"
"$BUILD/update-tests"
if [[ "$(uname -s)" == "Darwin" ]]; then
  swiftc -parse-as-library -swift-version 5 -target arm64-apple-macos14.0 \
    -framework AppKit -framework WebKit -framework Foundation \
    native/AppDelegate.swift native/NativeSelfTest.swift native/UpdateChecker.swift native/UpdateController.swift \
    -o "$BUILD/ElectTwin"
  echo "PASS: full native app compiled; app not launched or installed."
fi
