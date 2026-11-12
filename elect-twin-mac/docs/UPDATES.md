# Installed macOS app update checks

The native app checks published releases from `bagatawaya/elect-twin` on GitHub. This is an installed-app feature, not a website download-link change.

- Automatic metadata checks are enabled by default, after the local engines start and at most once every 24 hours while the app is running. Opening the app repeatedly does not generate extra automatic requests. There is no background process when the app is closed.
- The app menu includes **Check for Updates…** and **Automatically Check for Updates**. Manual checks bypass the daily interval, join an in-flight check, and report failures without blocking startup. Turning automatic checks off also suppresses any pending background notification; it does not prevent manual checks.
- **Later** suppresses reminders until a later daily check. **Skip This Version** suppresses only that release; a manual check can still show it. Background notifications wait until the app is active and has no native sheet/modal window.
- Beta builds include beta and stable releases. Stable builds exclude prereleases, including tags incorrectly marked stable by the release author. Versions use semantic precedence, not lexicographic or publication-date ordering. Older and equal versions are never offered.
- Only a matching uploaded macOS DMG with an uploaded `.sha256` sidecar is offered. Both URLs must be HTTPS on the exact repository's release path. Missing installers, wrong architectures, partial uploads, and unexpected redirects are not used. The newest compatible semantic version among the most recent 100 release entries is selected.

## Security and privacy

Checks fetch public metadata only with an ephemeral session and a generic User-Agent. They do not send project content, provider credentials, local-server URLs/tokens, installed version, device IDs, account IDs, or cookies. GitHub receives normal connection information such as IP address. Requests have 15-second request / 20-second resource timeouts, a 1 MiB body limit, no redirects, and no immediate retry. Errors in background checks do not interrupt local work.

This is **not a silent installer**. The update prompt opens the exact GitHub release page only after the user clicks **Review Update…**. No binary is downloaded, mounted, executed, replaced, or granted permission by the checker. It never removes quarantine or changes Gatekeeper settings. A checksum sidecar's presence is an availability gate, not cryptographic signature verification. Follow the release's compatibility and verification instructions before choosing to install it.

The current 0.4.0 beta is ad-hoc signed, not Developer ID signed/notarized. An authenticated automatic installer should be a separate future change using signed update metadata/artifacts, a pinned trust key, notarization/signature verification, and safe install/rollback behavior. Do not treat public GitHub access or an adjacent SHA-256 file as publisher authentication.

## Release maintenance

Before shipping a new build, update all of:

1. `CFBundleShortVersionString` (numeric version), `CFBundleVersion` (unique build), and `OpenTwinReleaseVersion` (full semantic version including `-beta.N` when applicable) in `packaging/Info.plist`.
2. Set `OpenTwinUpdateChannel` to `beta` or `stable` deliberately. Invalid/missing values fall back to stable.
3. Versioned filenames in the existing packaging script. Accepted installer names are `OpenTwin-<version>-<arm64|x86_64|universal>[-internal].dmg` or `Elect-Twin-…`. `<version>` can be the numeric core or full semantic version without `v`. Upload the corresponding exact `.sha256` sidecar to the same GitHub release. Never replace an old release in place; increment the version for a new build.
4. Publish the matching semantic Git tag (`vX.Y.Z[-beta.N]`) and correct prerelease flag. Draft releases are ignored. Uploads must be complete before publishing.

The source patch intentionally leaves the existing version at `0.4.0-beta`; it is not a new packaged release. **Already-installed 0.4.0 apps have no checker and require a one-time manual installation of a future build containing this code.** Neither editing source nor publishing a GitHub release retrofits old installations.

## Tests

From `elect-twin-mac`, run:

```sh
bash tests/check_native_updates.sh
```

The script runs an offline Swift test executable with URLProtocol fixtures and compiles the full AppKit/WebKit app on macOS. It does not start the app, access project databases, call model providers, install anything, or contact GitHub. The test executable/build directory is temporary. CI runs this check on macOS. The existing native UI self-test disables the updater so normal UI tests remain offline and do not write update preferences.

Before release, also exercise these native UI cases with isolated preferences/data: automatic check on/off, manual repeated clicks during a delayed check, current/new/beta/skipped release, Later then next-day check, offline/rate-limit response, inactive app then foreground, quit during a check, and Review Update/Later/Skip dismissal. Run the existing Python/JS/native regression suite after integration. Full native UI validation and signing/notarization remain distinct release gates.
