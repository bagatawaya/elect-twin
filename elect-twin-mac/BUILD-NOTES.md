# Elect Twin MVP build notes — November 10, 2026

Working product name: Elect Twin. This is an isolated, local-first prototype, not a production release.

## What informed the build
- Read Jay's shared Gemini assessment. Its scope recommendations were useful; unsourced competitor/version/price/savings claims were not adopted as facts.
- Read existing Skills Pilot package manifest, catalog entry and schema on Jay's Mac. Its current source is a separate pnpm/Next/React app with typed provenance and license metadata. Electri primary working tree was dirty. No existing source was changed or cleaned.
- Kept this prototype independent of live Electri, concurrent Kimi builds, all production services and provider accounts. No paid generation requests or deployment.

## Architecture
Python 3 standard library HTTP server bound only to 127.0.0.1. Single HTML/CSS/JS application. Local SQLite project library stores goals, documents, human decisions, conversation messages, provider attribution and exact approved context snapshots. No third-party runtime packages needed.

Five provider adapters: OpenAI, Anthropic, Gemini, Mistral and Groq. Choose an available model ID from your provider. Requests require review of the exact system/context packet then separate consent. API keys stay in process memory or user-provided environment; they are never written to the project DB or browser storage. Provider accounts remain independently authorized. Connection status means a key is present, not verified credentials.

This is explicit context sharing, not provider-native shared memory. Each turn chooses documents, decisions, skill text and optional prior conversation. Completed output is stored locally, with provider/model attribution, so a later provider can receive it only when selected. No implicit access to other projects.

Skills Pilot integration reads an existing local catalog with --catalog. Only portable prompt templates with prompt text and explicit supported permissive license evidence are eligible. No scripts, package installation, network catalog fetching or tool execution. Bundled starters work without the catalog. Lexical matches are suggestions with reasons, not claims of best-fit intelligence.

## Explicitly not implemented
- OAuth, Google Drive or other remote library storage, syncing or enterprise connection.
- Autonomous routing, workflows, parallel tool-using agents, background execution, MCP, Prompt Pilot, automatic skill mode.
- PDF extraction, semantic retrieval, audio/video generation, a complete 1,501-item catalog runtime. OpenAI image generation is the bounded exception described below.
- Streaming, guaranteed cancellation, billing estimates or hard monetary cap. Output length is capped; provider charges still apply.
- Credential vault / encrypted database / multiuser remote hosting.

Local text documents and generated text outputs are usable now; remote storage and richer assets must not be presented as working.

## Release gate
Before public GitHub release: review license/branding, independent security review, provider live tests with explicit budget authorization, install tests on macOS/Windows/Linux, accessibility audit and documentation review. No public repository was created.

## Scope extension during the build
Jay requested at least five providers and a first multimodal path. The registry is extensible; separate adapter specs add Gemini, Mistral and Groq alongside OpenAI and Anthropic. Contracts are tested with mocked HTTP, not live credentials. OpenAI image generation now has a separate explicit-consent path, one low-quality 1024-square PNG per request, stored in the project database and served only through authenticated local requests. Current provider API reference was checked; retired gpt-image-1 is rejected, model ID remains user-specified. PNG signature/size are checked; this is not full pixel decoding or aesthetic quality verification. No image was purchased/generated during this build.

Source checked: https://developers.openai.com/api/reference/resources/images
Cross-device storage design and its unsolved implementation gates are in STORAGE-ROADMAP.md. Earlier 'not implemented' references to image generation are superseded by this bounded OpenAI path; audio/video and other image providers remain unimplemented.
