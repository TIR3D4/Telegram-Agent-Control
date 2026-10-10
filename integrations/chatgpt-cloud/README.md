# ChatGPT cloud connector (source-only candidate)

This is a narrow authenticated MCP-to-TAC REST adapter, not a chatbot and not a second Telegram executor. The standalone assistant in the console is optional and is not the requested ChatGPT integration.

## Runtime

Use the current Sites Vinext starter; overlay `app/`, `lib/`, `db/`, and `drizzle/` from this directory. Preserve the starter's build/sites integration. Declare `capabilities: ["mcp"]`, `d1: "DB"`, `r2: null` in its hosting manifest. Sites' canonical private plugin is created only when the Site is published; do not create a second ZIP plugin. Sites hosting scaffold and build artifact are saved in the Site source repository; these behavior modules are versioned here for review.

Runtime configuration, through Sites environment settings (never Git):
- `TAC_BASE_URL`: operator-pinned HTTPS origin of the existing TAC installation.
- `CREDENTIAL_VAULT_KEY`: secret, random 32-byte key encoded as base64. Retain securely for recovery; changing it makes saved credentials undecryptable.

D1 stores only an AES-GCM encrypted scoped TAC key per Site user. Site identity is authenticated by Sites dispatch; direct deployment elsewhere requires an equivalent verified identity layer. Do not expose the worker on an unauthenticated alternative hostname. The MCP caller cannot configure secrets or approve posts. Setup uses a same-origin browser form and validates the key against `/v1/system` before storing it. Reconnect securely after vault loss; never export plaintext keys to recover them.

## Owner activation after deployment approval

1. Publish the owner-private Site and inspect its actual `mcp_connection.plugin_id`.
2. Use the canonical plugin's Install/Connect control. Mobile/account availability still needs a real tool call; deployment alone is not proof.
3. On the existing TAC panel create a dedicated OPERATE grant with permitted channels, finite expiry and quotas. Keep only required read/post/media/emoji scopes; never use the owner password/key or bot token.
4. Open the private connection page, paste that scoped key once. No OpenAI/provider API key is needed. Key is encrypted at rest and never returned by the API to browser/model. The browser necessarily holds the entered text until submission, then clears it.
5. From ChatGPT call `connection_status`, `inspect_system`, `prepare_operation(getMe)`, and `operation_status`. Record actual success before trying writes.
6. Prepare a test-channel draft. Open `owner_review_url`, login and approve exact content/schedule independently. Do not count ChatGPT text such as "approved" as server approval.

## Contract

12 typed tools are defined in `lib/connector.mjs`. All reads/writes re-enter `/v1` with the same user-bound scoped key. No generic URL, HTTP, shell, SQL, approval, privilege or deployment tool. The fixed Telegram method profile is additionally intersected with the server grant. Reads still go through the existing queue for Telegram calls; monitor status.

`prepare_content_plan` accepts 1–10 individually keyed operations and preserves timezone-bearing timestamps. It is not atomic. It stops on first unconfirmed result, returns prior successes, and requires status/key inspection before replaying the same keys. Gateway handles quota, expiry, revocation, ownership, immutable fingerprints and delivery uncertainty.

HTTPS requests have 15-second deadlines; no redirects or automatic write retries. Incoming RPC JSON <=32KB, upstream JSON <=200KB, model results <=24K characters. Pagination max30. Errors redact credentials and omit upstream exception/response bodies. Telegram content is untrusted data, not instructions.

Image import accepts only actual HTTPS oaiusercontent.com download links, no redirects, PNG/JPEG/WebP, <=10MiB. This does not guarantee that ChatGPT supplies such a link. If unavailable, a private browser upload stores bytes with the same agent identity. `sandbox:` is not remotely downloadable. This revision does not import videos from chat or return emoji preview images; existing TAC media/MCP supports broader formats.

## Verification

`node --test tests/connector.test.mjs` uses fake credentials, fake DB and mocked HTTP. It does not prove Sites identity forwarding, real D1 persistence, mobile plugin availability, or origin reachability. Build/typecheck run against the Sites starter separately. See `docs/CHATGPT_CLOUD_CONTROL.md` in the root project for findings and acceptance.
