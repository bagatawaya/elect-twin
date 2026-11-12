# OpenTwin v0.4.1-beta Release Notes

**Release Date:** November 12, 2026  
**Target:** macOS Apple Silicon (`arm64`)  
**Git Tag:** `v0.4.1-beta`  
**License:** MIT

---

## Executive Summary

OpenTwin v0.4.1-beta introduces an institutional-grade, native **GitHub Update Checker** for macOS alongside canonical **OpenTwin** branding. The update engine checks published GitHub release metadata with bounded, ephemeral requests and user-directed review actions—eliminating silent binary execution, quarantine bypasses, or telemetry leaks.

---

## Key Highlights

### 1. Native macOS Update Checker
- **Automated Daily Checks:** Verifies `bagatawaya/elect-twin` public release metadata at most once every 24 hours while the application is active.
- **Menu Bar Controls:** Native **Check for Updates…** and **Automatically Check for Updates** toggles in the AppKit application menu.
- **Strict Privacy Guarantees:** Ephemeral URLSession, no cookies, credentials, project data, installed versions, or device telemetry transmitted.
- **Safety First:** 15-second request / 20-second resource timeouts, 1 MiB payload ceiling, redirects rejected.
- **User-Initiated Action:** Clicking **Review Update…** opens the validated release page on GitHub. No automatic binary download, execution, or Gatekeeper modification is performed.
- **Offline Verified:** Validated against 95 offline unit assertions (`tests/check_native_updates.sh`) with mock URLProtocol fixtures and zero network access.

### 2. Canonical OpenTwin Branding
- Unified application bundle naming to **OpenTwin.app** and disk image packaging to **`OpenTwin-0.4.1-arm64.dmg`**.
- Updated `Info.plist` bundle metadata to version `0.4.1` (build `2026111201`).

### 3. Studio & Arena Capabilities
- **Polymorphic OpenZoo Arena Rooms:** `#Whats-The-Line` (Blind Prediction Syndicate), `#King-of-the-Hill` (1v1 Throne Tug-of-War), `#The-Tribal-Council` (Agent Peer Jury with Human Crowd Veto), and `#Room-Zero: Group-Therapy` (Curiosity Lockbox).
- **Solo 2-AI Goal Rooms:** 1 Human + 2 Custom AIs across 4 pre-configured presets (`Visionary + Skeptic`, `Writer + Showrunner`, `Architect + Red-Teamer`, `Sparring Partner + Corner Coach`).
- **Hard Storage Isolation:** Complete database separation across `projects.sqlite3` (private studio), `rooms.sqlite3` (collaboration digests), and `zoo.sqlite3` (arena rooms).

---

## Verified Artifacts & Checksums

| Platform | Filename | Target Architecture | SHA-256 Checksum |
|---|---|---|---|
| **macOS** | `OpenTwin-0.4.1-arm64.dmg` | Apple Silicon (`arm64`) | `9d6c7ee5f38bc9b18e69ec041210f39320949bc8e252ff07739cfe85ef666e22` |
| **Sidecar** | `OpenTwin-0.4.1-arm64.dmg.sha256` | Apple Silicon (`arm64`) | `9d6c7ee5f38bc9b18e69ec041210f39320949bc8e252ff07739cfe85ef666e22` |

---

## Installation & Gatekeeper Clearance

Because this is a community developer preview build (ad-hoc signed, not Apple Developer ID notarized), clear the quarantine attribute after copying to `/Applications`:

```bash
xattr -cr /Applications/OpenTwin.app
```

---

## Scope & Operational Boundaries

1. **Ad-Hoc Signing:** This release is ad-hoc signed for Apple Silicon. An Apple Developer ID notarized package will be provided in a future milestone.
2. **Windows Availability:** Windows x64 binary installer packaging is in active development and was not attached to this release.
3. **Session-Only Keys:** Provider API keys are stored strictly in volatile memory and are cleared upon app termination.
