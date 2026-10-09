# Scheduling and automation

## Single posts

Use `run_at` on any operation. Include an explicit UTC offset. Times are stored in UTC and displayed in the browser's local timezone. The hash approved by the owner includes the exact scheduled time. Cancel or revise a queued operation before it starts; a revision requires approval again.

## Workflows

A workflow has a name, immutable approved step list, trigger, IANA timezone and bounded `max_runs`. Each step has `method`, `payload`, optional `attachments` and `delay_seconds`. JSON payloads may reference a previous result with `$steps.0.result.message_id` or array positions such as `$steps.0.result.0.message_id`. No Python/JavaScript or template evaluation is used. Target chats must be fixed when approved.

```json
{
  "name":"Publish, pin, unpin",
  "timezone":"Asia/Tehran",
  "max_runs":1,
  "trigger":{"type":"once","at":"2026-10-10T09:00:00+03:30"},
  "steps":[
    {"method":"sendMessage","payload":{"chat_id":"@your_channel","text":"Final reviewed content"}},
    {"method":"pinChatMessage","payload":{"chat_id":"@your_channel","message_id":"$steps.0.result.message_id"}},
    {"delay_seconds":86400,"method":"unpinChatMessage","payload":{"chat_id":"@your_channel","message_id":"$steps.0.result.message_id"}}
  ]
}
```

Submit to `POST /v1/workflows`; owner approves at `/v1/workflows/{id}/approve` with `expected_digest`. This approval authorizes the complete frozen plan and bounded repetitions. It does not authorize an agent to generate and publish arbitrary new content later.

Other triggers:

```json
{"type":"cron","expression":"0 9 * * 1-5"}
```

```json
{"type":"update","event":"channel_post","chat_id":-100123456789}
```

Cron evaluates in the workflow timezone. Missed occurrences coalesce to a single due run; there is no unbounded backlog replay. Event rules match the named update and fixed chat. Use a different source chat for publish-to-channel workflows to avoid feedback; the run limit is mandatory. The event body is stored for inspection and is not injected into approved output text.

## Failure and control

Every occurrence has a unique key. Each step creates a durable operation and waits for a confirmed success. Failed or uncertain steps stop the run; later steps do not execute. Delays live in the database, so restart does not lose them.

`POST /v1/workflows/{id}/pause` disables new triggers and pauses running plans; queued child operations are cancelled. Owner can resume an unchanged plan at `/v1/workflow-runs/{id}/resume`. A running HTTP call can still complete during a pause.

To revise, pause first, then `PUT /v1/workflows/{id}` with the full new definition plus `expected_digest`. Revision clears approval and resets the new definition's run count. Previously started runs retain their step snapshot. Changed plans cannot resume old runs; review and create a new run instead.
