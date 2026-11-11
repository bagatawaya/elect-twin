# Elect Twin — Windows Architecture & Build Kit (0.3.0)

This directory provides the complete Windows native wrapper, clean Python Rooms implementation, and Inno Setup packaging kit for Elect Twin.

---

## Directory Overview

- **`rooms_server.py`**: Clean, pure-Python standard-library implementation of the Rooms coordination server. Zero 3rd-party dependencies. Compatible with Python 3.10+.
- **`test_rooms_server.py`**: Full regression test suite verifying all 37 Rooms contracts, authorization, private note isolation, deterministic worker execution, and restart persistence.
- **`web/index.html`**: Bundled web client for Rooms.
- **`ElectTwinWin/`**: C# / .NET 8 WinForms desktop wrapper using Microsoft Edge WebView2:
  - **Job Object Process Lifecycle**: Uses Win32 Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` to ensure all child engines (`twin-server.exe`, `rooms-server.exe`) exit when the main window closes or crashes.
  - **Loopback Lockdown**: Restricts internal web view navigation to negotiated 127.0.0.1 ports.
  - **External URL Delegation**: Automatically routes external HTTP/HTTPS links to the user's default browser.
  - **Custom Protocol**: Supports `elect-twin://home` and `elect-twin://zoo` deep linking.
- **`installer.iss`**: Inno Setup 6 compilation script creating `Elect-Twin-Setup-0.3.0-x64.exe`.
- **`start.bat`**: Convenience developer launcher.
- **`.github/workflows/build-windows.yml`**: GitHub Actions workflow to build the complete installer automatically on a `windows-latest` runner.

---

## Local Build Instructions (on Windows)

### Prerequisites
1. **Python 3.10+**: `pip install pyinstaller`
2. **.NET 8 SDK**: `dotnet --version`
3. **Inno Setup 6**: Available from `https://jrsoftware.org/isdl.php` (or `choco install innosetup`)
4. **Microsoft Edge WebView2**: Pre-installed on Windows 10/11; evergreen installer bootstrapped if missing.

### Build Steps

1. **Verify Offline Test Suite**:
   ```cmd
   python test_rooms_server.py
   python -m unittest discover -s ..\elect-twin-mac\tests -p "test_*.py"
   ```

2. **Freeze Standalone Python Engines**:
   ```cmd
   mkdir dist
   pyinstaller --noconfirm --onefile --name twin-server --add-data "..\elect-twin-mac\web;web" --distpath dist ..\elect-twin-mac\twin.py
   pyinstaller --noconfirm --onefile --name rooms-server --add-data "web;web" --distpath dist rooms_server.py
   ```

3. **Publish C# WebView2 Shell**:
   ```cmd
   dotnet publish ElectTwinWin\ElectTwinWin.csproj -c Release -r win-x64 --self-contained false
   ```

4. **Compile Inno Setup Installer**:
   ```cmd
   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
   ```

5. **Generate SHA-256 Checksum**:
   ```powershell
   Get-FileHash dist\Elect-Twin-Setup-0.3.0-x64.exe -Algorithm SHA256
   ```

---

## Automated GitHub Actions Build

Push to your repository with GitHub Actions enabled:
- The `.github/workflows/build-windows.yml` workflow will automatically run on `windows-latest`.
- Produces `Elect-Twin-Setup-0.3.0-x64.exe` and its SHA-256 sidecar.
- Uploads the artifacts ready for beta testing with friends.
