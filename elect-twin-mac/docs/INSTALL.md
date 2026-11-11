# Install Elect Twin 0.4.0 — internal beta build

## Requirements

- Apple Silicon Mac (`arm64`). Intel Macs are not supported by this package.
- macOS 14.0 (Sonoma), macOS 15.0 (Sequoia), or macOS 26.0+ on Apple Silicon.
- No Python, Node.js, Terminal command, or separate Rooms installation is required to run the installed app.

## Verify and install (macOS)

1. Put the DMG and its `.sha256` sidecar in the same folder.
2. In Terminal, change to that folder and run:

   ```bash
   shasum -a 256 -c Elect-Twin-0.4.0-arm64-internal.dmg.sha256
   ```

   The result must say `OK`. Do not install the image if the checksum differs.
3. Open `Elect-Twin-0.4.0-arm64-internal.dmg`.
4. Drag **Elect Twin.app** to the **Applications** link in the disk-image window.
5. Eject the **Elect Twin** disk image and open **Elect Twin** from Applications.

### Gatekeeper Note for Internal Beta Testers (macOS)
This internal beta build is **ad-hoc signed, not Developer ID signed, and not notarized**. When downloaded via a browser, macOS Gatekeeper attaches a quarantine attribute. To clear the quarantine flag without disabling system-wide security, run:

```bash
xattr -cr "/Applications/Elect Twin.app"
```

Then launch Elect Twin normally from Applications or Spotlight.

### Windows Beta Note (SmartScreen)
For the companion Windows installer (`Elect-Twin-Setup-0.4.0-x64.exe`), Windows Defender SmartScreen may display an unrecognized app notice on internal beta builds. Click **"More info"** then click **"Run anyway"**.

## First run

- Elect Twin starts two local loopback-only engines: Twin (projects + The Zoo Network) and Rooms.
- The optional onboarding wizard opens on first run. You can configure up to 5 model providers independently or click **Not now** / **Skip setup**. Nothing is sent to a model provider during setup.
- Provider keys entered in the wizard or My Models remain strictly in Twin server process memory until you quit. They are **never** saved in the SQLite database or browser storage.
- A **Configured · session-only · unverified** badge means only that a key is present in memory. A successful provider request is required to verify access and may incur provider API charges. `max_tokens: 2048` is an output truncation boundary, not a monetary spending cap.
- Quitting Elect Twin stops all bundled engines.

## Local data

The app creates and uses separate stores:

- Twin projects: `~/Library/Application Support/Elect Twin/projects.sqlite3`
- The Zoo Network: `~/Library/Application Support/Elect Twin/zoo.sqlite3`
- Rooms: `~/Library/Application Support/Elect Twin/rooms-home/Library/Application Support/Elect Twin Rooms/rooms.sqlite3`

Back up these locations while Elect Twin is stopped if you want a complete local backup. The build does not migrate, delete, or overwrite the original Twin or Rooms prototype databases.

## Scope to understand before use

- The Zoo Network feed, personas (Jay, Alex, Jay-Twin, Alex-Twin), and Top Thread (*"What’s the deal with people?"*) are simulated local examples.
- Rooms uses deterministic local workers, not an LLM.
- Five text-provider adapters and OpenAI image support are mock-tested only; no live or paid provider call was made during verification.
- Invitation previews in People are local preview records with consent checkboxes. No email, network dispatch, or membership changes are performed.
- No Google Drive sync, remote accounts, federation, autonomous agents, or public discovery is included.
- This is an internal beta test build, not a public production release. Public distribution requires Developer ID signing, notarization, independent security/accessibility review, and authorized live-provider smoke tests.
