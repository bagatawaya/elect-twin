# Elect Twin — Cross-Platform & Windows Architecture Guide

This document outlines the architecture, platform boundaries, and implementation plan for bringing Elect Twin and Agent Zoo to Windows and Web environments.

---

## 1. Current State (macOS 0.3.0 Baseline)

- **Desktop Shell:** Native Swift AppKit wrapper (`native/AppDelegate.swift` + `WKWebView`).
- **Core Engine:** Python `twin-server` backend compiled with PyInstaller into a standalone executable.
- **Rooms Engine:** Bundled arm64 PyInstaller binary (`rooms-server`).
- **Protocol:** HTTP over loopback interface (`127.0.0.1:<random-port>`). Handshake via JSON over child stdout.
- **Data Stores:** SQLite databases (`projects.sqlite3`, `zoo.sqlite3`, `rooms.sqlite3`).

---

## 2. Windows Architecture Strategy

### 2.1 Desktop Wrapper: C# / .NET 8 + WebView2
- **Why C# / .NET 8:**
  - Native Windows look and feel with minimal runtime overhead.
  - Microsoft Edge WebView2 control provides evergreen Chromium rendering matching macOS WebKit capabilities.
  - Native Win32 Job Object support ensures child process lifecycle management without orphan processes.
- **Process Lifecycle Guard:**
  - Create a Win32 Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`.
  - Assign `twin-server.exe` and `rooms-server.exe` to this Job Object upon creation.
  - If the UI shell crashes, terminates, or is killed via Task Manager, the Windows kernel automatically terminates all child engines immediately.
- **Custom URI Scheme:**
  - Register `elect-twin://` protocol to handle deep linking (`elect-twin://home`, `elect-twin://zoo`).

### 2.2 Reconstitution of Rooms (`rooms_server.py`)
- The macOS build currently bundles an arm64 binary for `rooms-server`.
- For Windows (and future cross-platform builds), we implement a clean, pure-Python standard-library server (`rooms_server.py`):
  - Zero external Python package dependencies (uses `http.server`, `sqlite3`, `json`, `urllib.parse`).
  - Implements the exact JSON handshake on stdout: `{"ready": true, "urls": {"jay": "http://127.0.0.1:PORT/#token=...", "alex": "http://127.0.0.1:PORT/#token=..."}}`.
  - Pass the complete `tests/smoke_rooms.py` regression suite.
  - Frozen into `rooms-server.exe` using PyInstaller on Windows.

### 2.3 Installer: Inno Setup
- **Output:** `Elect-Twin-Setup-0.3.0-x64.exe`.
- **Features:**
  - Installs to `{autopf}\Elect Twin` or `{localappdata}\Programs\Elect Twin`.
  - Bundles `ElectTwin.exe` (shell), `twin-server.exe`, and `rooms-server.exe`.
  - Performs WebView2 runtime presence check; bootstraps Evergreen installer if missing.
  - Clean uninstaller removing registry keys and binaries while preserving user database directories unless explicitly chosen.

### 2.4 CI/CD Automation: GitHub Actions
- Workflow file: `.github/workflows/build-windows.yml`.
- Runner: `windows-latest`.
- Steps:
  1. Setup Python 3.12 and install PyInstaller.
  2. Compile `twin-server.exe` and `rooms-server.exe`.
  3. Setup .NET 8 SDK and compile `ElectTwin.exe`.
  4. Run Windows offline unittests.
  5. Compile Inno Setup installer.
  6. Generate SHA-256 sidecar and upload release artifacts.

---

## 3. Platform Boundary & Security Principles

1. **Loopback Port Lockdown:**
   All HTTP services bind strictly to `127.0.0.1` on dynamically allocated ports (`--port 0`). No remote network interfaces are opened.
2. **Navigation Policy:**
   The WebView2 control restricts navigation to the negotiated local loopback ports. Any navigation attempt to external HTTP/HTTPS domains is intercepted and delegated to the user's default system browser.
3. **SmartScreen Guidance:**
   Unsigned/ad-hoc internal beta builds on Windows will trigger Microsoft SmartScreen warnings. Beta documentation provides instructions: click "More info" followed by "Run anyway".
4. **Data Isolation:**
   Local SQLite databases reside in `%LOCALAPPDATA%\ElectTwin\` on Windows (analogous to `~/Library/Application Support/ElectTwin/` on macOS).
