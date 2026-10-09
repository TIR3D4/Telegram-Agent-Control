# Mobile assistant decision and source audit

Reviewed 2026-10-09. Project baseline: `1dd50cf3271bfe01e24300aa8a53c173a47d4389` on `engineering/production-hardening-v0.2`. Changes are additive on `engineering/mobile-assistant`; existing OAuth, users, operations, quotas and approval services are preserved.

## Three distinct access paths

| Path | Evidence and limitation | Decision |
|---|---|---|
| ChatGPT mobile / Work | Owner reports Desktop only and no Add custom MCP server option. Official [custom MCP documentation](https://developers.openai.com/api/docs/guides/custom-mcp-server) requires web registration, subject to workspace permissions/security. [Plugin guidelines](https://developers.openai.com/plugins/plugin-guidelines) require mobile-compatible submitted plugins, but do not grant account registration capability. | No manifest edit, proxy or OAuth installation can enable a missing account feature. This change does **not** connect tools to the current ChatGPT conversation. |
| GPT Actions | Official [Actions](https://developers.openai.com/api/docs/actions/introduction) use REST/OpenAPI, with [API key or OAuth authentication](https://developers.openai.com/api/docs/actions/authentication). Requires access to the GPT editor and an actual action-enabled GPT. | Possible future separate client; owner-account availability/mobile execution not verified. Never expose owner approval endpoints or owner credentials to an Action. |
| Independent mobile chat | Existing responsive FastAPI panel, owner password + HttpOnly session + CSRF, PostgreSQL, scoped REST and worker are already present. | Selected: bounded Persian chat within the same panel, no additional chat database/container/proxy. Provider API billing is separate from a ChatGPT subscription. |
| Development / deployment | Telegram credentials authorize Telegram operations, not GitHub writes or server commands. | Separate coding branch/PR and operator-only pinned upgrade; chat saves development specifications. Autonomous coding/deployment is **not** implemented or advertised. |

## Actual source comparison

Repository trees and source files were fetched at these immutable commits, not inferred solely from README claims. No source was copied into this project. Runtime RAM/CPU was **not benchmarked**; deployment footprint below is from Docker/code, not measured MB estimates.

| Candidate / commit | License | Source inspected | Resource / maintenance implications |
|---|---|---|---|
| [LibreChat](https://github.com/LibreChat-AI/LibreChat/tree/e1dfc10449ff713faffacd60273fddcfe2c0a698), `e1dfc10449ff713faffacd60273fddcfe2c0a698` (commit date Oct 6) | MIT (`LICENSE`) | `docker-compose.yml`; `api/server/services/Tools/mcp.js`; `packages/api/src/mcp/tools.ts`; `mcp/oauth/handler.ts`, `tokens.ts`; `packages/api/src/credentials.ts` | Default Compose includes API, MongoDB, Meilisearch, vector PostgreSQL, RAG and admin panel. Mature tool/OAuth UI; additional user store and deployment lifecycle. Optional components can be removed, but MongoDB and separate auth still add operational work. |
| [Open WebUI](https://github.com/open-webui/open-webui/tree/8bd8b4fac5e059578ac0c74b3c18d11139f88b7d), `8bd8b4fac5e059578ac0c74b3c18d11139f88b7d` (commit date Sep 21) | Open WebUI License; **not simply MIT**. Branding restrictions and stated exceptions in `LICENSE`; older materials retain history terms. | `LICENSE`, `LICENSE_NOTICE`, `docker-compose.yaml`; `backend/open_webui/utils/tools.py`, `utils/mcp/client.py`; `models/oauth_sessions.py` | Native OpenAPI conversion and execution; MCP support exists too. API-only deployment can omit Ollama. Still another application, login, settings and upgrade surface. Native Python/terminal tools should remain disabled for this project. |
| [mcpo](https://github.com/open-webui/mcpo/tree/788ff92e5288a899a743a252edd5748f4ad4ab1f), `788ff92e5288a899a743a252edd5748f4ad4ab1f` (commit date Feb 27; repository push metadata May 17) | MIT (`LICENSE`) | `Dockerfile`; `src/mcpo/main.py`, `utils/auth.py`, `utils/oauth.py` | Extra Python process translating MCP to OpenAPI. Static API key middleware; OAuth storage has in-memory and file variants, file variant writes token JSON. Adds credential/transport lifecycle without benefit where REST already exists. |
| In-panel chat (selected) | Project MIT | `tac/assistant.py`, existing security/gateway/operations/worker; one additive migration | No MongoDB/vector store/Redis/Ollama/mcpo. One bounded assistant thread per worker. We maintain a small explicit tool list and provider adapter instead of a general chat platform. Deliberately omits RAG, browser automation, arbitrary Python, shell, autonomous coding and offline execution. |

### Tool execution and credential findings

LibreChat `createMCPStructuredTool` wraps execution in approval transport/assertions, maps input schemas, handles MCP tool error results and user/server catalog boundaries. OAuth handler checks client/resource provenance and registration; token storage uses `encryptV2` / `decryptV2` and refresh fencing across replicas. These client approvals do not replace our server's human approval policy. Its [MCP documentation](https://www.librechat.ai/docs/features/mcp) confirms agent tool integration.

Open WebUI `get_tool_servers_data` reads OpenAPI 3.x and builds tool payloads; `execute_tool_server` resolves operationId, path/query/body parameters and forwards configured auth. `get_terminal_tools` also exists: it is unnecessary and inappropriate for the Telegram assistant. OAuth sessions encrypt token JSON with Fernet using an environment encryption key. Its [OpenAPI documentation](https://docs.openwebui.com/features/extensibility/plugin/tools/openapi-servers/) states complete-result rather than streamed tool responses and limited interactive events. A separate native confirmation UI would still need integration with TAC exact-digest approvals.

mcpo's `get_verify_api_key` / `APIKeyMiddleware` implement shared-key protection; its file token storage uses `json.dump` while memory storage does not survive restarts. Neither supplies TAC channel policy, owner approval, durable Telegram operations or GitHub deployment authorization. Do not add it here.

## ADR: bounded server chat over existing REST

The browser sends user messages only to the owner-authenticated chat routes. The provider secret and scoped Telegram credential are Fernet-encrypted in RuntimeState. The random 0600 vault key is persisted in the media volume, has no Asset entry, and is included in verified backups. It must be restored with the encrypted database. Encryption protects copied DB dumps without the vault; it does not protect a fully compromised server/complete backup.

The worker submits tool requests to the same FastAPI REST application using an agent bearer, never an owner session. The model receives only the explicit tool schemas and sanitized results. No approve/grant/restore/shell/deploy tool exists. The browser reviews the exact operation digest via the existing independent owner approval route. Unknown tool names and out-of-schema arguments are rejected. Prompt instructions are additional context, not the security boundary.

Provider URLs are pinned HTTPS endpoints for OpenAI, OpenRouter and Groq. Arbitrary model-directed URLs/redirects are forbidden. Model ID and key are configured via the web form; actual model tool-calling availability depends on provider/account. Official [OpenAI](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create), [OpenRouter](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion), and [Groq](https://console.groq.com/docs/api-reference) request documentation was checked. Live paid inference was not performed.

Chat turns are persisted, have an idempotency key, finite tool/HTTP budgets and cancellation. A crashed running turn becomes interrupted after its lease, with no automatic provider or tool replay. Telegram's own durable worker and uncertain-delivery behavior remain unchanged. The worker's separate chat thread keeps Telegram processing responsive; multi-worker PostgreSQL claims use row locking and a conditional state transition.

## Acceptance and residual gaps

Implemented: independent mobile chat, provider settings, encrypted keys, persisted turns/events, limited tools, draft/owner review links, read-only connection-test button, proposal records, explicit commit upgrade and failure reports. Existing approval/quota/idempotency are tested through the shared REST boundary.

Pending actual installation acceptance: authenticated getMe through the new UI on the owner's server, paid model inference, real iPhone Safari keyboard/Home Screen behavior. Browser emulation is not physical Safari. ChatGPT registration remains blocked by the reported account UI. Autonomous GitHub coding/PR generation and web-triggered deployment require a separately authorized isolated runner and are not part of this implementation. The assistant can collect specifications; coding work is delivered separately as a reviewable branch/PR.
