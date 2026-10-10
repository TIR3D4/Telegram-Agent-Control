# Automatic optimizer behavior

This file defines the default low-friction behavior after installation.

The user should not need to manually run optimizer commands during normal work.

## During normal tasks

- Use AGENTS.md and atlas-map.md for orientation when present.
- Start with the smallest relevant source set.
- Expand context whenever correctness, tests, dependencies, or uncertainty require it.
- Never sacrifice correctness to reduce tokens.
- Avoid broad rescans and rereading unchanged files without a reason.
- Preserve unrelated working-tree changes.

## Automatic Git safety

If this project already has Git metadata:

- run lightweight `git status --short` before substantial edits when useful;
- use targeted `git diff -- <relevant paths>` instead of loading broad diffs;
- preserve all unrelated/uncommitted user changes;
- never run destructive reset/clean/stash behavior automatically;
- never initialize Git if the project does not already use it;
- do not create commits unless the user or project workflow asks for them.

Use branch/worktree isolation only when it materially helps, especially for parallel Codex chats or risky/large changes. Do not create a worktree for every small task.

See `docs/git-safety.md` in the optimizer repository for the full design.

## Quiet health checks

At sensible task boundaries, not on every turn:

1. Check context health using the local optimizer tool when available.
2. Do this quietly unless there is an actionable issue.
3. Do not interrupt an active edit just because context usage is high.
4. Do not repeatedly run telemetry commands within the same short task.

## When context becomes heavy

If context pressure is HIGH or CRITICAL, or the current thread is clearly becoming inefficient:

- finish the current safe unit of work first;
- create/update a compact handoff;
- recommend starting a fresh chat for the next task boundary;
- give the user one short sentence to continue;
- do not require the user to understand benchmark/report commands.

Suggested continuation message:

~~~text
Start a new chat for better context efficiency, then send:
Read .codex-context/HANDOFF.md and continue my task.
~~~

## Reporting

Do not show token statistics unless:
- the user asks about savings/usage;
- there is a meaningful degradation;
- a fresh chat is recommended.

When reporting, keep it simple:
- estimated saving trend;
- number of post-optimizer responses;
- context pressure;
- one recommended action if needed.

## Advanced commands

The following are implementation details and should not be required for normal use:

- report
- doctor
- fresh-start
- benchmark-start
- benchmark-end
- benchmark-compare
- handoff

They remain available for debugging and advanced users.
