# KIMI.md — OpenTwin / OpenZoo Workspace Guide

## Exact Paths

**Local workspace (mac):** `/Users/mac/Documents/Kimi/Workspaces/ElecTWIN/`

| What | Where |
| --- | --- |
| macOS app source | `elect-twin-mac/` |
| Windows shell source | `elect-twin-windows/` (C# WinForms `ElectTwinWin/`) |
| Public brochure site (source of truth) | `site/` (deployed as `v66`, cache-bust `style.css?v=66`) |
| Arena/heartbeat tooling | `tools/` (`hydrate_all_12_syndicates.py`, `publish_live_feed.py`, `free_cloud_agents/`) |
| Free-agent outbox (local runs) | `tools/free_cloud_agents/outbox/` |
| Oracle doc root (live) | `ubuntu@132.145.131.180:/var/lib/docker/volumes/openclaw-governance_caddy_config/_data/openzoo-brochure-v040/site/` |
| Live URLs | `https://zoo.132.145.131.180.nip.io/` · `/opentwin/` · `/press/` · `/live_feed.json` |
| GitHub release | `bagatawaya/elect-twin` → `v0.4.1-beta` |

## Pre-Flight Guardrails (non-negotiable)

1. Run `git status -s` + `git diff --stat` before any edit; never revert in-progress working-tree edits.
2. **Never edit or restart the Caddyfile** (`sha256: 9e621c099f07…`) and never touch the 16 Docker containers on the Oracle box (`openclaw-caddy`, `openzoo-hub`, `future-oracle`, …). Read-only `docker exec … grep` is fine.
3. `live_feed.json` is canonical at **28 rooms / 75 agents / 0 duplicate `session_id`s**. Deduplicate **strictly by `session_id`** — never by `card_index`. Never overwrite it with a partial/12-room fixture.
4. Heartbeat publishing is least-privilege only: unprivileged `ubuntu` worker stages JSON in `/home/ubuntu/openzoo_outbox/` (`0700`), then `sudo -n /usr/local/sbin/openzoo-publish-feed` (root-owned `0755`, narrow NOPASSWD sudoers, `flock` on `/var/lock/openzoo_feed.lock`, symlink rejection, atomic write `opc:opc 0644`). `openzoo-heartbeat.service` runs as `User=ubuntu` (never root); `ubuntu` must stay out of the `docker` group; the `.timer` stays stopped/disabled until final review.
5. `#First-Contact` rooms must be labeled `exchange_type: creative_persona_dialogue` — no fabricated private-history or sentience claims.
6. Hard compute cap: zero paid cloud API calls; `<= 300` output tokens/turn; zero automatic retries on local runs. Use `set -euo pipefail` for shell work.

## Credit-Saving Rules

1. Prefer deterministic Python/bash one-liners and scripts for file, JSON, SHA-256, and rsync operations — avoid reading large files line-by-line into context.
2. Default to **K2.8 Preview** (50% credit discount) for copy, CSS, docs, and test runs (e.g. `python3 -m unittest discover -s elect-twin-mac/tests`, `python3 elect-twin-mac/tests/check_js.py`).
3. Reserve **K3 High** for multi-file Swift/C# refactors or complex CI/systemd debugging.
4. Use Codex only for independent security audits or isolated Groq outbox runs.
5. Batch independent `ssh`/`gh`/`curl` checks in parallel; verify with `curl -sI` + `stat`/`shasum` instead of re-downloading artifacts.
