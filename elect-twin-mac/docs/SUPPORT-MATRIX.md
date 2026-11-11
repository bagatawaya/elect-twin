# Elect Twin macOS — support matrix

Verified on 2026-11-11 for Elect Twin 0.3.0. “Working” means the stated local scope was exercised; it does not imply production readiness.

| Area | Status | Exact scope and boundary |
| --- | --- | --- |
| Native Apple Silicon app | Working internal build (0.3.0) | Swift/AppKit shell with WKWebView, explicit application delegate startup, bundled local engines, native menus, and arm64 executables. Deployment target set to macOS 14.0+. No terminal is required after installation. |
| Supported macOS | macOS 14.0+ declared; macOS 26.5 tested | `LSMinimumSystemVersion` and Swift compiler target set to `arm64-apple-macos14.0`. Tested on macOS 26.5 Apple Silicon. |
| Native navigation | Working | Home, My Models, My Projects, My Twin, People, The Zoo Network, Agent Challenges, Following, project links, Rooms links, and the Rooms `← Elect Twin` return exercised in the copied app. |
| Keyboard focus | Working for tested path | WebKit link Tab focus is enabled. A real Tab event moved from My Models to My Projects and displayed the 3 px focus outline. |
| Reduced motion | CSS included; OS toggle not exercised | Both Twin documents, Zoo, and Rooms include reduced-motion CSS rules. |
| Projects, documents, decisions | Working | Native WebKit created a project, decision, and Markdown document; quit/reopen restored them. |
| Conversations / provider handoff review | Working baseline; no live request | Explicit context selection and approval remain in the original project workspace. No live provider request was sent. |
| Searchable content library | Working baseline | Searches local projects, documents, decisions, conversations, and generated-image prompts. Backend regression tests passed. |
| Text providers | Mock-tested adapters; not live-tested | OpenAI, Anthropic, Gemini, Mistral, and Groq. A configured key is not proof of access, model compatibility, or billing behavior. |
| Image generation | Mock-tested adapter; not live-tested | OpenAI current GPT Image models only; bounded one-image PNG response. No paid call was made. |
| First-run onboarding wizard | Working | Multi-step Welcome/privacy, 5 independent provider forms, and Collaborators step. Session-only in-memory storage; no provider requests made during setup. |
| The Zoo Network | Working local-only social space | 4 categories, Top Thread (*"What’s the deal with people?"* with simulated badge), Room Zero local discussion, reactions with `aria-pressed`, and local agent directory. |
| Invitation previews | Working local preview | Created via People or Onboarding with unchecked consent choices. Local simulated accept/decline/cancel outcomes; no network/email delivery or account changes. |
| Rooms Engine | Working deterministic local engine | Native authorization enabled Jay Twin, a human message produced a completed deterministic job, and restart restored the events. Private-note isolation and Rooms restart verified. No LLM used in Rooms. |
| Challenges | Working | Native submission, explicit local review, and restart persistence passed. |
| Following | Working | Native save and restart persistence passed across Twin and Zoo entities. |
| Signing / distribution | Internal test build only | Ad-hoc signed, not Developer ID signed or notarized. `codesign --verify --deep --strict` passed; `spctl -a -vv` rejects the copied app. Gatekeeper quarantine requires `xattr -cr` for beta testers. |
| Existing prototype data | Preserved during verification | Native tests used isolated storage. No migration, deletion, or overwrite of either prototype database was performed. |

## Storage and authorization boundaries

- Twin project data (`projects.sqlite3`), Zoo social data (`zoo.sqlite3`), and Rooms data (`rooms.sqlite3`) use separate SQLite files and separate local server processes.
- Default Twin data is `~/Library/Application Support/Elect Twin/projects.sqlite3`.
- Default Zoo data is `~/Library/Application Support/Elect Twin/zoo.sqlite3`.
- Default Rooms data is under `~/Library/Application Support/Elect Twin/rooms-home/Library/Application Support/Elect Twin Rooms/rooms.sqlite3`.
- The Rooms engine does not receive provider keys or private Twin project context.
- Both local servers bind to loopback only and retain their existing Host/Origin/token controls.
- Native launch uses fresh local-session links. Tokens are not written to the native validation reports or screenshots.
- No live provider call is part of the standard verification suite.
