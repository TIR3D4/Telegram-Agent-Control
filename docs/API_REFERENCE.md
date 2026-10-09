# REST API reference

For the automated web setup and separate REST/MCP paths, start with [CONNECTIONS.md](CONNECTIONS.md).


Prefix: **`/v1`**, preserved for existing clients. `/api/v1` is not implemented. Live request schemas and route inventory: `/openapi.json`, `/docs`, `/redoc`. Use `Authorization: Bearer <scoped credential>` over HTTPS. Only liveness/readiness, static console, discovery and OpenAPI are intentionally unauthenticated; protected-resource discovery is available only when OAuth is configured.

The [MCP tool contract](AGENT_TOOLS.md) describes shared effects, policy, errors and retry semantics. Both transports use the same operation/authorization services. No HTTP endpoint interprets arbitrary shell or SQL.

| Resource | Routes / operations |
|---|---|
| Health | GET `/health/live`, `/health/ready` |
| Discovery | GET `/v1/capabilities?q=&limit=&offset=`, `/v1/methods/{name}?detail=false`, `/v1/types/{name}`; POST `/v1/validate` |
| Operations | POST/GET `/v1/operations`; GET/PATCH `/v1/operations/{id}`; POST `/{id}/approve`, `/cancel`, `/resolve`, `/duplicate`, `/retry`; GET `/{id}/preview` |
| Media | POST multipart/GET `/v1/assets`; POST `/v1/assets/encoded`; GET `/v1/assets/{id}`, `/{id}/metadata` |
| Keyboards | POST `/v1/keyboards/build` with `{rows: [[button, button]]}` |
| Workflows | POST/GET `/v1/workflows`; PUT `/v1/workflows/{id}`; POST `/{id}/approve`, `/{id}/pause`; GET `/v1/workflow-runs` |
| Telegram | GET `/v1/accounts`, `/v1/channels`, `/v1/channels/{chat_id}/analytics`, `/v1/updates`; POST authenticated `/v1/webhook` |
| Catalog | GET `/v1/emojis`; POST `/v1/emojis/{id}/preview`; PATCH `/v1/emojis/{id}`; GET `/v1/emoji-roles`; PUT `/v1/emoji-roles/{role}` |
| Agent governance | Owner GET/POST `/v1/agents`; no self-service privilege expansion |
| Maintenance | POST/GET `/v1/admin/requests`; owner POST `/{id}/approve`, `/{id}/execute` |
| Diagnostics | GET `/v1/system`, `/v1/metrics`, `/v1/logs`, `/v1/traces/{id}`, `/v1/database/overview`, `/v1/database/status`, `/v1/settings`; POST `/v1/settings/validate` |
| Global pause | Owner POST `/v1/system/pause`; existing emergency control retained |

## Operation request

```json
{
  "method": "sendMessage",
  "payload": {"chat_id":"@allowed_test_channel", "text":"A reviewed draft"},
  "attachments": {},
  "idempotency_key": "editorial-2026-10-09-001",
  "run_at": "2026-10-10T10:00:00+03:30"
}
```

A 201 response is a persisted operation with `id`, `status`, `digest`, `actor`, `run_at`, `approved_until`, `attempts`, `result`, `error`, `trace_id` and `message_links`. Writes start as `draft`. Owner approval: POST `/{id}/approve` with `expected_digest` and optional timezone-aware `expires_at`. Revisions require `expected_digest`; stale review returns 409. For uploads, bind `attach://photo` to `attachments:{"photo":"asset_id"}`.

Lists are bounded and filtered by caller ownership. Operation pagination uses `before` creation timestamp (ties can require narrower querying; not a snapshot-stable cursor). Assets/workflows use limit/offset; logs and updates use monotonically increasing IDs. Current list caps are enforced in code; SDK defaults are smaller. There is no unbounded export endpoint.

Request responses contain `X-Request-ID` and `X-Trace-ID`; trace IDs correlate work but are not authentication. Uploads have configurable byte limits; JSON/MCP body limit is 2 MiB. Asset downloads are attachments. Methods requiring parameters unavailable from the Bot API cannot synthesize them: consult [capabilities](CAPABILITY_MATRIX.md).
