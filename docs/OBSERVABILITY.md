# Observability

Process logs are structured JSON, redacted before formatting. Correlation fields include time, severity/logger, request ID, trace ID, actor, operation, method, path, duration/status and error type when available. Request bodies, Authorization headers and Telegram token URLs are not logged. HTTP library request logging is suppressed. Do not turn verbose upstream logging back on with a live token.

Persistent audit records include HTTP requests and domain transitions such as creation, review, cancellation, execution, denial and maintenance. `/v1/logs` supports `after`, `limit`, `resource_id`, `action`, `q` and `trace_id`. Ordinary callers see their own records and their operation events. `/v1/traces/{id}` returns bounded correlated events. Trace IDs can be supplied for correlation, never for authorization. MCP tool names are discoverable at the protocol layer, but persisted audit currently records the underlying REST/domain action, not a separate tool-name event for each call.

| Surface | Meaning |
|---|---|
| `/health/live` | Process responds |
| `/health/ready` | Database access; not a Telegram/worker success claim |
| `/v1/system` | Version, identity/scopes, registry counts, pause state, worker data |
| `/v1/metrics` | Own operation counts, oldest due age, worker heartbeat age/freshness |
| `/v1/database/status` | Migration revision, installed dependency versions, last verified backup manifest |
| Operation record | Delivery status, attempts, confirmed upstream IDs/links and sanitized errors |

`TAC_WORKER_STALE_SECONDS` defaults to 90. A single global heartbeat means **some worker** has reported; it is not a per-worker census. The UI shows stale/healthy explicitly. No CPU/RAM billing analytics or Telegram reach statistics are synthesized.

## Retention and tracing

Compose rotates app logs at 10 MB × 5 and PostgreSQL logs at 10 MB × 3. Once per worker hour, retention removes up to 1,000 expired quota buckets and 1,000 `http.request` audit rows older than `TAC_RETENTION_DAYS` (default 90). Approval/operation audit, updates, media and idempotency records remain retained. Large installations must monitor growth and design an explicit archive policy; there is no automatic deletion of evidence.

Set `TAC_OTEL_ENABLED=true` and a trusted `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` to enable optional OpenTelemetry HTTP export (SDK/exporter included in the locked environment, optional `telemetry` extra for minimal installs). HTTP and Telegram call spans contain safe identifiers, not payloads or credentials. Exception text is deliberately not auto-recorded. Export timeout is five seconds; shutdown flush budget is three seconds. `OTEL_SDK_DISABLED=true` disables the SDK even if TAC's flag is on. Propagation is via application trace IDs; complete W3C distributed tracing across a separate worker is not claimed.

The in-memory exporter is tested. A live external collector, dashboards and alerts have not been deployed. Audit is append-only through the application API, not tamper-proof against a database/VPS administrator. During a database outage, inspect container process logs; audit writes may be unavailable.
