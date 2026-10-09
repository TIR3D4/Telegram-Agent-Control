# REST API

Current route map and governance contract: [API_REFERENCE.md](API_REFERENCE.md).


Base URL: your installation. All `/v1` routes require `Authorization: Bearer <key>` except `/v1/webhook`, which authenticates with Telegram's secret header. `/docs` and `/openapi.json` describe the control API. Requests return `X-Request-ID` for application-log correlation.

## Discover → validate → submit → inspect

```http
GET /v1/capabilities?q=slideshow
GET /v1/methods/sendRichMessage
GET /v1/types/InputRichBlockSlideshow
```

`GET /v1/methods/{name}` includes complete referenced type definitions, required fields and official field descriptions. Transport coverage includes JSON bodies, nested objects, URLs/file IDs and `attach://` multipart bindings. All 185 registered methods use one gateway; there is no SDK method-name gap.

```json
POST /v1/validate
{"method":"sendRichMessage","payload":{"chat_id":"@your_channel","rich_message":{"is_rtl":true,"html":"<h1>عنوان</h1><tg-slideshow><img src=\"https://example.com/1.jpg\"/><img src=\"https://example.com/2.jpg\"/></tg-slideshow>"}}}
```

The example URLs are placeholders, not bundled media. Use valid media URLs or the explicit Rich Message media fields documented in the method schema.

```json
POST /v1/operations
{
  "method":"sendMessage",
  "payload":{"chat_id":"@your_channel","text":"Approved content"},
  "attachments":{},
  "idempotency_key":"campaign-20261010-post-001",
  "run_at":"2026-10-10T09:00:00+03:30"
}
```

The response contains `id`, `digest` and `status`. Reads queue automatically; writes require an owner key:

```json
POST /v1/operations/OPERATION_ID/approve
{"expected_digest":"DIGEST_RETURNED_BY_SERVER"}
```

Poll `GET /v1/operations/OPERATION_ID` until a terminal state. `succeeded` includes the actual Telegram result; published channel messages include `message_links` when enough information exists. An immediate zero message ID or Boolean result cannot produce a trustworthy message link.

## Content and attachments

Upload multipart form field `file` to `POST /v1/assets`. The returned asset ID can be bound:

```json
{
  "method":"sendPhoto",
  "payload":{"chat_id":"@your_channel","photo":"attach://photo","caption":"Caption"},
  "attachments":{"photo":"ASSET_ID"},
  "idempotency_key":"photo-post-001"
}
```

The same mechanism supports arrays/nested media. Uploaded asset bytes are immutable; changing media requires a new asset and new approval. `GET /v1/assets/{id}` is authenticated. External URLs are passed to Telegram rather than fetched by a generic URL proxy.

## Revisions and controls

- `PATCH /v1/operations/{id}`: body `payload`, `attachments`, optional `run_at`, and `expected_digest`; editing a queued draft revokes approval.
- `POST /v1/operations/{id}/cancel`: only before execution starts.
- `POST /v1/operations/{id}/resolve`: owner reconciles an `uncertain` outcome using `{status:"succeeded"|"failed", result:..., note:...}` after checking Telegram.
- Edit/pin/unpin/delete published content by submitting the corresponding official method with the stored target/message ID. These are new audited operations.
- `POST /v1/system/pause?enabled=true`: stop new execution. An already running HTTP request may finish.

## Inspectability

| Endpoint | Evidence |
|---|---|
| `/v1/system` | Build/API versions, method counts, queue counts, heartbeat, configured targets |
| `/v1/operations?status=failed&limit=50` | Failed requests and structured errors |
| `/v1/logs?after=0&resource_id=...` | Cursor-based audit events, actor/action/resource/details |
| `/v1/database/overview` | Tables, column types and row counts |
| `/v1/workflows`, `/v1/workflow-runs` | Definitions and execution progress |
| `/v1/updates?after=...` | Captured Telegram updates; not arbitrary chat history |
| `/v1/assets`, `/v1/emojis`, `/v1/emoji-roles` | Media/catalog metadata |

Credentials and token-like strings are redacted. Raw SQL and host shell commands are deliberately not API capabilities. Database inspection follows documented resources.

## Errors and guarantees

`401`: missing/bad key. `403`: wrong role. `409`: stale revision, duplicate key conflict or invalid state transition. `422`: validation failure. Telegram errors are stored on the operation. `429` with `retry_after` delays retry; transport failures become `uncertain`.

The application validates structure and selected semantic constraints; it does not claim to encode every condition in the official prose. Telegram remains authoritative for permissions, contexts, limits and runtime eligibility. Method schemas are input contracts; returned Telegram data is stored and redacted, not automatically rejected when Telegram adds new output fields.
