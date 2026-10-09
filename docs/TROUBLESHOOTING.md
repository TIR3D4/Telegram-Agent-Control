# Troubleshooting

Start with `./scripts/tacctl doctor`, `status`, `logs`, `/v1/metrics` and the operation ID. Never paste `.env`, full tokens or private payloads into issues.

| Symptom | Diagnosis / action |
|---|---|
| 401 | Wrong/expired/revoked key, legacy mode disabled, unmapped OAuth subject, wrong issuer/audience/lifetime. Inspect safe settings and issue a fresh least-privilege grant. |
| 403 | Required scope/method/channel missing; MCP rejects owner keys; source chat also needs authorization. |
| 404 on known ID | Creator/resource isolation or changed channel policy; ask the owner to inspect. |
| 409 | Stale digest, state conflict, repeated maintenance execution or idempotency collision. Read current record before retrying. |
| 429 | Per-agent request/operation quota or upstream Telegram rate limit; inspect Retry-After and job history. |
| Draft never runs | Owner review missing/expired, edit revoked approval or no bot configured. |
| Queued late | Worker stale, global pause, schedule timezone, policy revoked or upstream retry_after. |
| Uncertain | A write may already exist. Inspect Telegram and reconcile with evidence; do not resend blindly. |
| Telegram 403 | Bot/channel permissions; getMe then getChatMember with the bot ID. |
| MCP Invalid Host/Origin | Canonical HTTPS `TAC_PUBLIC_URL` or reverse-proxy configuration mismatch. |
| OAuth discovery works but login fails | IdP metadata, client registration, exact callback, PKCE, consent/resource audience; TAC is not the authorization server. |
| Tool returns truncated preview | Narrow filters, paginate or fetch one authorized REST detail. |
| Blank emoji preview | First animation frame can be transparent; inspect original. Rendering failure exposes only safe error category. |
| Restore rejected | Missing/incorrect manifest, corrupt/untrusted archive or expired/consumed approval. Do not bypass validation. |
| Update migration failed | Keep worker stopped, inspect revision/logs, restore the matching verified backup if necessary. |
| DB auth after password edit | Changing `.env` does not alter an existing PostgreSQL role password. Update the role through authorized operator procedures. |
| No OTLP spans | Install telemetry extra if using minimal package, enable TAC flag, check `OTEL_SDK_DISABLED`, exporter endpoint and collector. |

Database outages can prevent audit persistence; structured process logs remain the fallback. Consult [known limitations](KNOWN_LIMITATIONS.md) before interpreting absence of evidence as success.
