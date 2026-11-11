# Elect Twin

A local-first personal project companion. Keep your goals, documents, decisions and conversation in one place, then deliberately hand selected context to another model without starting from scratch.

**Status: working development prototype, not a public release.** No cloud account, hosted database, package installation or paid service is required to start the interface. Model calls require your own provider account and can incur charges.

## Start locally

Requires Python 3.10+ and a modern browser. No Python dependencies.

```sh
cd elect-twin
python3 twin.py
```

Open the **private localhost URL printed by the process**. The URL contains a temporary local-session token. Do not share it. Keep the terminal running. Stop with Ctrl+C. The server listens only on `127.0.0.1:4321`, not your LAN.

For the Kimi Work development preview, run `npm run dev`. This uses port 7100 and a separate `.local-data/projects.sqlite3` database. Its `--development-preview` option embeds the per-process token in the root HTML so the preview can open directly; never use that option for a normal launch or shared environment. Node is only a launcher here—there are no npm runtime dependencies.

Alternative port and storage location:

```sh
python3 twin.py --port 4322 --data ./private-data/projects.sqlite3
```

Default project data is `~/.electri-twin/projects.sqlite3`. Back up that database while the app is stopped. Treat the file as private: it contains documents, messages and exact context sent to models, in plaintext.

## Connect a model

This version has text adapters for five providers: OpenAI, Anthropic, Gemini, Mistral and Groq. Use **Connect model** to provide a key for the current server session only; it is not saved to the database and is lost when the server restarts. Alternatively, supply keys in the server process environment. Do not paste keys into a chat, project document or source file. For example, in Bash, hidden entry avoids saving the key itself in shell history:

```bash
read -r -s -p 'OpenAI API key: ' OPENAI_API_KEY; printf '\n'
export OPENAI_API_KEY
python3 twin.py
```

For other providers use the environment variable in the matrix below. Multiple keys can be set before starting. A configured badge means a key is present, **not that authentication or billing has been verified**. Enter a model ID available to your account and compatible with the selected endpoint. There is no universal provider OAuth, subscription-login bridge, automatic signup or shared authentication across independent services.

### Text provider matrix

| Provider | Environment variable | API route | Validation |
| --- | --- | --- | --- |
| OpenAI | `OPENAI_API_KEY` | `https://api.openai.com/v1/chat/completions` | Offline adapter contract tests |
| Anthropic | `ANTHROPIC_API_KEY` | `https://api.anthropic.com/v1/messages` | Offline adapter contract tests |
| Gemini | `GEMINI_API_KEY` | `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions` | Official endpoint docs + offline contract tests |
| Mistral | `MISTRAL_API_KEY` | `https://api.mistral.ai/v1/chat/completions` | Official endpoint docs + offline contract tests |
| Groq | `GROQ_API_KEY` | `https://api.groq.com/openai/v1/chat/completions` | Official endpoint docs + offline contract tests |

For Gemini, Mistral and Groq, endpoint/auth/payload design was checked against official documentation on November 10, 2026: [Gemini OpenAI compatibility](https://aistudio.google.com/docs/openai), [Mistral Chat API](https://docs.mistral.ai/api), and [Groq Chat API](https://console.groq.com/docs/api-reference#chat-create). OpenAI-compatible does not mean every model or feature is interchangeable. These adapters send text only, do not advertise tool execution, and use the model ID you select. No model availability, account access, price or live output-quality claim is made.

The adapters request a bounded output length (2,048 tokens), but that is **not a verified cost cap**. Gemini's compatibility documentation does not clearly specify token-limit accounting; its requested `max_tokens` behavior requires a live account test. Reasoning models may consume budget before returning visible text. Use provider billing controls; failed/empty responses do not establish zero charge.

## First useful session

1. Create a project with a name and goal.
2. Add plain-text reference documents and record important decisions.
3. Write a task; choose provider and model.
4. Select the documents, decisions, optional prior conversation and skill guidance relevant to this task.
5. Preview the exact context and destination. Only **Send** submits it to that provider.
6. Switch providers for the next turn. Include history deliberately to hand off prior work.

Context is saved by Elect Twin, not invisibly synchronized among model companies. The selected provider receives only the approved preview. A preview expires after ten minutes and can be sent once. Editing the project after a preview does not alter that preview: regenerate it to include changes.

## Included and deferred

Included:
- Persistent local projects, text documents, decisions and conversations.
- Search across projects, documents, decisions, conversations and generated-image prompts, with project-scoped filtering.
- Edit/delete controls for documents and decisions, plus project and generated-image deletion. Deleting source items does not erase old handoff snapshots; deleting the project does.
- Explicit, inspectable context selection and cross-provider handoffs.
- Provider/model provenance, request status and provider-reported usage where available.
- Session-only provider connect/disconnect, redirect blocking and bounded provider responses.
- Three original, bundled starter skill suggestions with transparent keyword matching.
- Local session protection and no automatic request retries.

Not yet included:
- Automatic production Skills Pilot catalog sync or plugin-host integration.
- PDF/Office extraction, vector search, automatic summarization or unlimited context.
- Tool execution, MCP servers, external writes, autonomous agents or workflow scheduling.
- Automatic quality/cost routing, reliable price estimates or a global hard spending cap.
- Company workspace sync, multi-user access, mobile packaging or cloud hosting.
- Encrypted local vault, provider OAuth or a provider-authentication verification flow.

The starter suggestions are not a claim that these are the best skills in the public catalog. They are optional prompt guidance, not executable plugins. Model output remains untrusted and may be wrong. Nothing in this version can execute a generated command or publish an artifact.

## Reuse an existing Skills Pilot catalog

```sh
python3 twin.py --catalog "/path/to/Skill Pilot/data/catalog/skills.json"
```

This reads the existing catalog in place without modifying it or downloading anything. It imports only non-deprecated `prompt-template` records with nonempty `promptText` and catalog license evidence marked `file-verified` for CC0, MIT or Apache-2.0. Other record types are skipped. Source/revision/license metadata is retained. These are catalog assertions, not a fresh legal or runtime verification. Review upstream terms before redistribution.

No third-party catalog is bundled. Suggestions remain simple keyword matches with explanations, not semantic rankings or claims of best fit. Skill content is only included when explicitly selected in the reviewed prompt. No package installation or skill execution occurs.

## Verification

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v test_twin.py test_extra.py test_images.py test_control.py
```

All 44 tests pass. The suite covers persistent SQLite state; consent, expiry and replay; project/document isolation; approved history across two providers; immutable previews; data edit/delete and library search; stable project ordering; redirect credential containment; provider response bounds; outbound adapter payloads; and real localhost HTTP authorization/origin boundaries. Provider responses are mocked at the network boundary. **Passing tests does not establish live provider access, output quality, current model compatibility, price or billing behavior.** No paid generation was used.

A cold-start Chrome check on macOS also passed project creation, text upload/edit/delete, decision creation/deletion, library search, provider connect/disconnect, project deletion and 375 px mobile overflow checks with zero console errors and zero HTTP errors. Desktop and mobile captures are in `demo/`. Browser checks used a temporary database and no provider calls.

## Failed or interrupted requests

Requests are not retried automatically. After a timeout or process interruption the provider may still have processed and charged the call. The run is marked failed/unknown or interrupted/unknown. Check the provider before deciding to submit a new preview. Closing the browser does not cancel an already submitted request.

## Development and release

See [SECURITY.md](SECURITY.md) before handling sensitive material. Keep API keys, private project databases, browser tokens and real customer documents out of commits. Public release still needs independent security review, live provider smoke tests under an approved budget, license/attribution review for any imported catalog and a packaging/accessibility review. No production Electri service is modified by this standalone folder.


## Image generation and content library
Choose Image mode, OpenAI, and a current GPT Image model available to your account. Review the exact prompt/context and approve a separate billed image request. One low-quality 1024×1024 PNG is requested; the result and provenance are saved in the project library, with authenticated preview/download. No automatic text-model rewrite or extra generation occurs. You can first ask any text provider to craft a visual brief, then copy the chosen prompt to Image mode.

The image adapter was contract-tested with a fixture, not a paid generation. Current API reference: https://developers.openai.com/api/reference/resources/images . Retired gpt-image-1 is rejected. Other image providers, image edits, audio and video are not implemented. PNG header/size validation is not a full decoder or quality assessment.

## Local launch and installation status
Unzip into a folder you own, install Python 3.10+ from its official source if necessary, and run `python3 twin.py`. macOS/Linux can run `./start.command`; Windows can run `start.bat` with the Python launcher installed. macOS may require Terminal launch or executable permission after unzipping. These are convenience launchers, not signed native installers. The Python server and Chrome interface were exercised on macOS; the shell launcher and Windows launcher still require validation, and Linux was not retested in this continuation. Nothing is installed into existing Electri/Kimi projects.

For chosen local storage and planned cross-device Google Drive authorization/sync/conflict design, see STORAGE-ROADMAP.md. Drive is not connected in this version.
