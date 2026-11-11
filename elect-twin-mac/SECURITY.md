# Elect Twin security notes

This is a single-user local development prototype, not a hardened service or a security audit. Do not expose it through a reverse proxy, tunnel, public network or shared workstation.

## Current boundaries

- The server binds only to IPv4 loopback. Host and Origin checks reject other sites.
- API requests require a random per-process token from the private launch URL. The token is not a provider key and is not a durable user login.
- Model endpoints are fixed HTTPS OpenAI, Anthropic, Gemini, Mistral and Groq endpoints, not user-configured arbitrary URLs. Provider redirects are rejected rather than followed, so credentials are not forwarded to redirect destinations. Text responses are limited to 5 MB and image responses to 30 MB.
- Provider keys are accepted into server memory through the authenticated Connect form, or taken from the process environment. Session keys are not stored in SQLite and are discarded at restart or explicit disconnect. Environment credentials can only be removed by changing the server process environment. State responses expose configuration booleans, not key values. Server access logs are suppressed and upstream error bodies are not returned.
- SQLite file permissions are set to owner read/write. The launch process uses a restrictive umask. A newly created storage directory is owner-only.
- Each send requires a one-use, expiring preview and explicit consent. Exact selected context is frozen at preview time and stored in the run audit record.
- No execution tools or external write connectors exist. Documents and suggested skills are sent as reference material, with instructions not to treat them as authorization.
- Failed and interrupted calls are not automatically retried. This reduces accidental duplicates but **cannot guarantee that a provider did not execute or bill a request**.

## Important limitations

Project data is **not encrypted at rest**. The SQLite database contains project knowledge, source text, chat outputs and copies of transmitted context. Operating-system administrators, malware and other software with access to the same user account may read it. Use OS disk encryption and avoid sensitive data until this threat model is acceptable.

Environment variables are not a secure hardware vault. Other same-user processes, debugging tools, crash reporting and terminal setup may expose credentials. Use provider-specific, revocable keys with the minimum available permissions and sensible provider billing limits. Never save keys in the repository or include them in a prompt.

The local session token is a bearer credential. Anyone who obtains it and can reach the machine's loopback service may read the database through the API or submit requests. Launch URLs may appear in terminal scrollback or browser history. Restart to invalidate a token. The opt-in `--development-preview` mode embeds this token in the root HTML for local preview tooling; it provides no additional authentication and must never be exposed beyond loopback. Protect the workstation.

Prompt-injection defenses are advisory. A model can still follow malicious instructions in reference documents or produce false claims. The absence of tools limits direct execution risk; it does not prevent a model from exposing any context you chose to send. Read previews carefully and use least-context sharing.

The application currently has no cancel button for an in-flight provider request. Text requests use a 90-second socket timeout and image requests a 180-second socket timeout; these are not total request deadlines. Closing the browser or terminating this process cannot revoke a request already received by a provider. Inspect provider records after uncertain outcomes.

Input/context sizes are bounded per request, but project count, document count, transcript storage and run history are not globally quota-limited. Long-lived use can fill a disk. Projects, documents, decisions and generated images can be deleted. Deleting a source item does not erase copies in previously saved handoff records; deleting the whole project removes its handoffs. There is no organization isolation, granular multi-user authorization, automated retention policy or automated backup system.

Provider output and model capability compatibility were tested with fixtures, not with paid live calls. Endpoint behavior, token usage, billing, rate limits and supported model IDs must be checked against the actual provider account. A configured-key indicator is not an authentication test.

## Before a public release

- Independent security and dependency/license review; test credential lifecycle and error redaction.
- Adopt an OS keychain or explicitly designed encrypted vault if durable key storage is added.
- Review CSP and all UI rendering of user/model-supplied text; sanitize any future Markdown/HTML renderer.
- Add storage limits, retention/export/delete controls, backup restoration guidance and crash/parallel-request stress tests.
- Test allowed endpoint redirect behavior and provider protocol changes.
- Test keyboard navigation, screen readers and browser safety boundaries.
- Add each executable connector behind a separately designed authorization and idempotency boundary. Do not equate a skill recommendation with permission to execute it.

If you find a vulnerability, do not include secrets, real private documents or live session tokens in a public issue. An official private disclosure channel must be established before publishing this project.
