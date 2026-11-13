# OpenTwin & OpenZoo v0.5.0-beta Release Notes

- **Release date:** November 12, 2026
- **Application version:** 0.5.0 (`2026111205`)
- **Target:** macOS 14.0 or later, Apple Silicon (`arm64`)
- **Git tag:** `v0.5.0-beta`
- **License:** MIT

---

## A Local Personal Intelligence OS

OpenTwin 0.5.0 turns the local-first studio into a five-tab personal intelligence workspace while preserving explicit approval boundaries, session-only provider credentials, separate local data stores, and deterministic OpenZoo fixtures.

### Five-Tab Studio

- **My Command:** A customizable Bento dashboard with local model, skill, project, task, privacy, and OpenZoo widgets.
- **Open News:** Local three-bucket framing heuristics, supplied-source receipts, Scan and Split Reader modes, and an explicitly unavailable Audio Brief until a speech engine is connected.
- **My AI & Code:** Model routing, OpenSkills discovery, prompt-bundle inspection, and local builder/challenger guidance.
- **My Markets & Odds:** Clearly labeled local fixtures and configurable policy displays—not live financial advice or autonomous trading.
- **My Zoo & Studio:** OpenZoo arena entry points and creative/remix surfaces with local state kept separate from private projects.

Tabs, widget order, widget titles, spans, deletion/Undo, and custom additions persist locally. Task Center controls save policy only; they do not start schedules, provider calls, or external writes.

### Open News

Open News analyzes only the headline and source text supplied by the user. It separates **FACT**, **INFERENCE**, and **COULDNT_VERIFY**, labels framing hypotheses, and never fetches a submitted URL or invents live coverage. Its percentages describe a local keyword heuristic, not measured outlet coverage.

### OpenSkills v2

- **1,501 catalog entries:** 300 full `source_prompt` playbooks and 1,201 `metadata_only` entries.
- **1,462 active entries**, with 39 deprecated entries excluded by default.
- Local SQLite FTS5 discovery, guild filters, bounded selection, and builder/challenger/verification bundle construction.
- Metadata-only records are identified as such; selection does not claim access to unavailable source prompts.

### Smart Model-Version Router

The router selects only from model IDs the user declares as connected. It supports automatic, economy-locked, and frontier-focused tiers, considers task complexity and skill recommendations, and returns reasons plus alternatives. **Routing never dispatches a provider request.** Credit-tier labels are configuration guidance, not measured savings or benchmark results.

### Smart Swarm Gate

The gate evaluates independent fan-out opportunities deterministically. It detects shared-state/path collisions, sequential or external-write intent, and worst-case budget violations. It returns advisory acceptance state with `execution_started: false`; external writes still require separate explicit approval.

### Procedural SVG Studio v2 — Companion OpenZoo Tooling

The dependency-free renderer turns bounded JSON specs into deterministic SVG artwork at zero API cost. It includes seven templates (`flowchart`, `comic_strip`, `trading_card`, `versus_poster`, `greentext_meme`, `infographic`, and `pixel_avatar`), eight palettes, eight vector stamps, and SHA-256 content-addressed receipts carrying the source spec and optional remix provenance.

The original v1 schema remains supported. Security contracts include an 8,192-byte input cap, strict validation, ASCII/XML escaping, no active SVG content or external assets, and `O_NOFOLLOW` / `O_EXCL` writes with mode `0600`.

### Existing Studio and Arena Foundations

- Solo 2-AI goal presets and deterministic multiplayer Rooms.
- Isolated project, Rooms, and OpenZoo data stores.
- Session-only provider credentials.
- Native GitHub release-metadata update checks with user-directed review and no silent binary download or execution.

---

## Verified macOS Artifact

| Artifact | Size | SHA-256 |
|---|---:|---|
| `OpenTwin-0.5.0-arm64.dmg` | 20,679,909 bytes | `975565823095acb97b86002c746cef4d2c1badd771433c944fa66c34deabe7d5` |

Download:

- [OpenTwin-0.5.0-arm64.dmg](https://github.com/bagatawaya/elect-twin/releases/download/v0.5.0-beta/OpenTwin-0.5.0-arm64.dmg)
- [OpenTwin-0.5.0-arm64.dmg.sha256](https://github.com/bagatawaya/elect-twin/releases/download/v0.5.0-beta/OpenTwin-0.5.0-arm64.dmg.sha256)

Verification completed on the exact release image:

- Sidecar SHA-256 verification passed.
- `hdiutil verify` passed.
- `codesign --verify --deep --strict` passed.
- Native cold launch: **27 assertions passed**, eight WKWebView screenshots captured.
- Native reopen: **10 assertions passed** against the isolated persisted workspace.
- Native QC made **zero provider calls**.
- Offline Python discovery: **170 tests passed**.
- JavaScript syntax: **7 documents passed**.
- Native update checker: **95 assertions passed** without external network requests.
- SVG v1/v2 renderer and security suites: **26 tests passed**.

## Installation

1. Download the DMG and SHA-256 sidecar from `v0.5.0-beta`.
2. Verify the download:

   ```bash
   shasum -a 256 -c OpenTwin-0.5.0-arm64.dmg.sha256
   ```

3. Open the disk image and drag **OpenTwin.app** to `/Applications`.
4. This is an **ad-hoc signed, non-notarized arm64 community preview**. If macOS quarantine prevents launch, the documented preview workaround is:

   ```bash
   xattr -cr /Applications/OpenTwin.app
   ```

   Run this only after verifying the DMG checksum and intentionally copying the app to `/Applications`.

## Operational Boundaries

- Provider keys remain in memory for the active app session; connecting a key does not prove access until a reviewed request succeeds.
- No paid provider call is required by the native QC or deterministic test suites.
- OpenZoo resident agents and arena events are local illustrative fixtures unless a separately configured Hub connection is explicitly enabled.
- Windows x64 binary packaging is not part of this prerelease; the Windows source shell remains in `elect-twin-windows/`.
- The legacy on-disk data-directory name remains `Elect Twin` to preserve existing user data.
