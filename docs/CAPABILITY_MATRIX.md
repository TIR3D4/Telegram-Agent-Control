# Capability matrix

Registry snapshot: official Telegram Bot API **10.3**, **185 methods / 400 types**. Registry coverage means discoverable schemas and transport support, not live execution of every method. Authorizations and method-specific Telegram restrictions always apply.

| Area | Implemented | Evidence / boundary |
|---|---|---|
| Text/photo/video/audio/document/animation/voice/sticker | JSON/multipart operation gateway | Schema/transport tests; live channel acceptance pending |
| Albums | `sendMediaGroup` with asset bindings | Registry + mocked transport; native rendering unverified |
| Rich slideshows | `sendRichMessage` and referenced rich blocks | Pinned official contract; destination/client eligibility enforced upstream |
| Edit/delete/pin/unpin/copy/forward | Granted methods, own job tracking, exact human approval | Scope/channel/recovery tests; Telegram age/right restrictions remain |
| URL/callback keyboards | Builder, native styles, custom emoji field, edit/remove via operation | Semantic validation; callback responder not included |
| Premium emoji | Import by sticker set, file/preview catalog, visual labels/roles, image tool | No claim that a bare ID reveals appearance or that every account can use every emoji |
| Scheduled operations | UTC timestamps, durable queue and expiry | Worker/approval/restart tests |
| Workflows | Once/cron/update, result references, delays, finite count, pause/revise/history | Durable deterministic runtime; no arbitrary code execution |
| Incoming messages | Authenticated webhook storage, scoped reads, dedup | No general Bot API channel-history reader |
| Accounts / channel permissions | One configured bot; actual getMe/getChatMember through granted operations | Channel list reports unverified; no fake admin check |
| Analytics | Local delivery counts and worker/queue metrics | No native Telegram reach/views history |
| MTProto | Not implemented | No user session, FloodWait/session-revocation implementation claimed |
| Remote agents | 42 tools, REST/OpenAPI, SDK stdio/Streamable HTTP | Protocol tests + shared authorization |
| OAuth | JWT resource verification, discovery and subject mapping | External issuer needed; live ChatGPT/Codex OAuth linking untested |
| Agent governance | READ/OPERATE/ADMIN, scopes/channels/methods/ownership, expiry/rotation/revocation/quotas | Independent owner consent; in-flight Telegram calls cannot be recalled |
| Database/maintenance | PG migrations, safe metadata, verified backup, controlled restore/rollback | No SQL endpoint; rollback across arbitrary releases unverified |
| Internal LLM runtime | Not implemented | External agents use the gateway; no provider/model budget chosen |
| UI | Editor, approvals, history, catalog, media, keyboard builder, grants, maintenance, metrics/settings | Browser-tested core flows; English only, not full visual editors for all 185 methods |
| Logs/tracing | Redacted process/audit logs, filter/query, trace IDs, optional OTLP | In-memory exporter test; external collector deployment not tested |

Telegram Bot API is not MTProto or Telegram Ads. Channel admin status does not automatically imply every send/edit/delete permission. `getChatMember` results need to be read and checked for the exact intended capability. Use a test bot/channel before a production rollout.
