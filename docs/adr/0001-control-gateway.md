# ADR 0001 — Shared scoped control gateway

Status: accepted for v0.2.

Keep the modular monolith and PostgreSQL queue. Existing locks/migrations/recovery have test evidence. REST owns resource authorization and operation services; MCP calls it using the caller credential, never a shared elevated credential. Agents receive finite grants intersecting role preset, explicit scopes, explicit Telegram methods and channel allowlists. Bot API registry discovery does not grant execution. The worker rechecks persisted grant status immediately before claim. Approvals expire and cannot be self-approved by an agent. An already in-flight upstream request cannot be recalled.

OAuth is an external issuer plus a local resource-server verifier. Issuer, JWKS URL, audience and subject-to-grant binding are administrator configuration. No issuer/key URL from a token is trusted. Static scoped bearer grants remain useful for Codex and controlled clients. Owner bootstrap keys never enter MCP.

Consequences: fewer moving parts and a single auditable authority. One bot account is intentionally preserved. Telegram usernames and numeric IDs must be explicitly listed; unresolved aliases are denied. Third-party login/PKCE/client registration must be configured with the selected provider before ChatGPT OAuth linking is claimed.
