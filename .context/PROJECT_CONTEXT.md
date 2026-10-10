# Telegram Agent Control

Owner goal: converse inside ChatGPT, Codex or Claude to prepare/manage Telegram content; use the operator console for connection setup, independent approvals, schedules and diagnostics. Do not redirect normal work into another standalone chatbot.

Python 3.12+ modular monolith: FastAPI REST `/v1`, official SDK Streamable HTTP `/mcp/`, shared scoped gateway, PostgreSQL, durable worker, media volume, optional OAuth/Keycloak, Caddy and Docker Compose. Persian RTL responsive console. Optional internal chat remains secondary. The private hosted ChatGPT bridge is a separate deployment from the VPS.

Preserve owner-independent approvals, exact operation digests, scopes/channel limits, quotas, idempotency, durable scheduling, uncertain outcomes and secret redaction. No arbitrary agent SQL/shell/root access. All Telegram writes use the existing state machine.

Root AGENTS.md is authoritative guidance; code and tests override stale context summaries. Secrets are deliberately absent. The pinned optimizer is a development aid, not an application service or Telegram connector.
