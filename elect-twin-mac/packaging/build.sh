#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYINSTALLER="$ROOT/packaging/build-venv/bin/pyinstaller"
if [[ ! -x "$PYINSTALLER" ]]; then
  echo "Create an isolated build environment first: python3 -m venv packaging/build-venv && packaging/build-venv/bin/pip install pyinstaller" >&2
  exit 1
fi
mkdir -p packaging/build packaging/dist packaging/dmg
"$PYINSTALLER" --noconfirm --onefile --name twin-server --add-data "$ROOT/web:web" --distpath packaging/dist --workpath packaging/build/pyinstaller --specpath packaging/build twin.py
/usr/bin/swiftc -parse-as-library -O -target arm64-apple-macos14.0 -framework AppKit -framework WebKit -framework Foundation native/AppDelegate.swift native/NativeSelfTest.swift -o packaging/build/ElectTwin
python3 brand/make_icons.py
APP="$ROOT/packaging/dmg/Elect Twin.app"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/Runtime" "$APP/Contents/Resources/Rooms" "$APP/Contents/Resources/Docs"
cp packaging/build/ElectTwin "$APP/Contents/MacOS/ElectTwin"
cp packaging/Info.plist "$APP/Contents/Info.plist"
cp brand/AppIcon.icns "$APP/Contents/Resources/AppIcon.icns"
cp packaging/dist/twin-server "$APP/Contents/Resources/Runtime/twin-server"
ditto "rooms-reference/Elect Twin Rooms.app/Contents/Resources/server/" "$APP/Contents/Resources/Rooms/"
cp LICENSE README.md docs/SUPPORT-MATRIX.md docs/INSTALL.md "$APP/Contents/Resources/Docs/"
/usr/bin/codesign --deep --force --sign - --timestamp=none "$APP"
/usr/bin/codesign --verify --deep --strict --verbose=2 "$APP"
ln -sfn /Applications packaging/dmg/Applications
DMG="$ROOT/packaging/dist/Elect-Twin-0.4.0-arm64-internal.dmg"
if [[ -e "$DMG" ]]; then
  echo "Refusing to overwrite existing DMG: $DMG" >&2
  exit 1
fi
/usr/bin/hdiutil create -volname "Elect Twin" -srcfolder packaging/dmg -format UDZO -imagekey zlib-level=9 "$DMG"
(cd packaging/dist && /usr/bin/shasum -a 256 "$(basename "$DMG")" > "$(basename "$DMG").sha256")
file "$APP/Contents/MacOS/ElectTwin" "$APP/Contents/Resources/Runtime/twin-server" "$APP/Contents/Resources/Rooms/rooms-server"
cat "$DMG.sha256"
