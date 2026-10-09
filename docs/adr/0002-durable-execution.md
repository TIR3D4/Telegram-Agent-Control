# ADR 0002 — Preserve the PostgreSQL execution engine

Accepted for v0.2. Existing operation/workflow tables, claim locks and lease fencing already have tests. Use them for schedules, delays, bounded runs, approvals, history and recovery rather than adding Redis/Celery/Temporal/LangGraph. Telegram does not provide general application idempotency; a second queue cannot remove ambiguous network outcomes.

Keep writes fail-closed on expired approval or revoked grant; stop uncertain work for reconciliation. Retry explicit 429 responses within a finite attempt budget. Revisit orchestration when measured throughput, long-lived model state or multi-service workflows justify the operational cost. Optional internal LLM runtime remains unimplemented; external agents execute through the same gateway.
