# Persian mobile assistant

Use the independent HTTPS console in Safari; it does not require a ChatGPT custom MCP registration option. This does not add a plugin to the current ChatGPT chat.

1. Sign in using the existing username/password. Cookies are HttpOnly, SameSite Strict; mutations require CSRF. No localStorage credential is introduced.
2. Open **دستیار گفتگو**. Choose OpenAI, OpenRouter or Groq, enter the exact tool-capable model ID available to your account, and paste its API key in the password field. Enter permitted channels from the server allowlist. Never paste keys into chat.
3. Save. Server responses return configuration status, not stored credentials. Reopening the form leaves the key empty. Blank means preserve, not erase. Changing provider requires its own key.
4. Use **تست اتصال فقط‌خواندنی Telegram**. This queues getMe with the same restricted assistant grant, without a model call or Telegram writes. Inspect the operation until `succeeded`; queued is not proof of connectivity.
5. Ask in Persian. Tool events and states remain visible. Writes are drafts; open **بررسی عملیات و تأیید مستقل مالک**, review exact payload/destination/schedule and approve independently. A chat message saying “approve” cannot authorize publication.
6. Reload after disconnection: persisted recent turns and running status are fetched again. Cancel stops future tool steps, not an operation already submitted to Telegram. A worker interruption is not automatically retried; inspect existing operations first.

The grant lasts 30 days, 60 requests/minute, 100 Telegram operations/day, selected channels and known read/post methods. It has no administrative scopes. Renewal/replacement is an explicit owner checkbox; revoked/expired grants are not silently renewed. Changing channel selection applies only when creating/replacing a grant. Inspect/revoke it in Agent permissions. The runtime also limits chat submissions to 6/minute and 60/day, four model calls per turn, at most three tools per round, 1500 completion tokens per model request, and 60-second provider HTTP timeout. These are usage controls, **not** a dollar-denominated billing guarantee. Configure hard spending limits with the provider. API charges are separate from ChatGPT subscriptions.

## Installation / upgrade

Fresh installation: `./scripts/install.sh` installs the console and prompts once for login. Managed OAuth is optional via `./scripts/tacctl setup`; fresh installs no longer provision Keycloak just to use independent chat. Existing OAuth and all identity data are preserved on upgrade.

For an existing installation, use the reviewed branch/commit in the PR and run **one command** from the checkout:

```bash
git fetch origin engineering/mobile-assistant && git show FETCH_HEAD:scripts/upgrade.py | python3 - --branch engineering/mobile-assistant --commit REVIEWED_FULL_COMMIT_SHA
```

Replace `REVIEWED_FULL_COMMIT_SHA` with the exact reviewed commit, not a model-supplied arbitrary revision. Do not run until deployment is authorized. The helper refuses staged/unrecognized local changes, requires a fast-forward from the installed commit, retains config, performs DB/media and existing OAuth DB backup, records old/target commits, builds, pauses execution, inspects migration heads, migrates and checks readiness/doctor. It does not rerun console/OAuth provisioning when login already exists. Failure reports live in `backups/upgrade-*/upgrade-report.json` (0600); no automatic DB rollback. Execution remains paused for owner review/resume. The upgrade is operator-only; no chat shell or root tool exists.

After adopting this branch, subsequent pinned upgrades use:

```bash
./scripts/tacctl update --commit REVIEWED_FULL_COMMIT_SHA
```

Only the two engineering branches are accepted by the upgrade helper. Main is not overwritten. An unrelated deployment checkout requires explicit operator review.

## Backups and rollback

The encrypted settings need both the database and `.assistant-vault` from the media archive. Keep complete backups private. Archive validation accepts only existing flat media files and this exact 44-byte 0600 vault entry; traversal, links and arbitrary dotfiles are rejected. Do not delete/recreate the vault to “fix” a decryption failure. Restore matching backup material, or securely reconfigure keys and replace the grant.

Cross-revision database rollback is blocked by `rollback.py`. A same-revision tested restore remains available. To revert a schema-changing release, review application/schema compatibility and test a restore in isolation before planning a production restore; prefer a forward fix. Migration downgrade removes chat history and is only tested in an isolated database. OAuth databases/configuration backups remain separately protected; app rollback does not automatically roll them back.

## Development from a phone

Ask the assistant to prepare a development specification; it stores an owner-visible proposal, with no GitHub key or deployment capability. Use GitHub/Codex mobile or this coding assistant to work on a separate branch, run CI, review the diff/PR, then authorize a pinned operator upgrade. This release does **not** contain a self-hosted coding agent, automatic PR writer or web deployment executor. Granting such access to the Telegram assistant would violate the separation of privileges.

## Home Screen / PWA

Safari Share → Add to Home Screen can use the web manifest and standalone display metadata. This is an online web application; there is no service worker, offline publishing, cached API payload or offline credential store. Background execution occurs on the server, not in Safari. Physical iPhone Home Screen/keyboard behavior remains an installation acceptance check. Existing console views are primarily English; the assistant and its settings are Persian RTL and localization is additive.

## REST extension

All `/v1/assistant/*` routes require the human owner; agent credentials are rejected. Existing session/CSRF protections apply. GET config has a sanitized public schema; PUT uses `Configure` (SecretStr API key). POST turns uses `Message` with idempotency key and optional completed parent. GET history is bounded to 30 recent turns. GET turn inspects persistent status/events/usage. POST cancel cancels future assistant work. POST connection-test queues getMe. GET development-proposals lists at most 50 records. Interactive OpenAPI at `/docs` includes exact input schemas.

Model tools: `system_status`, `method_schema`, `prepare_operation`, `operation_status`, `development_proposal`. JSON schemas reject extra fields. Telegram tools preserve grant scope/channel/method/rate/daily quota and operation ownership checks; method authorization is checked again at execution. There is no arbitrary REST path or Telegram admin executor.

Errors: 401 expired/revoked grant or login, 403 permission/CSRF failure, 409 active turn or conflicting key/parent, 422 validation, 429 quota, 503 unconfigured/vault failure. Provider errors record an HTTP status or exception class, never provider response bodies/secrets. Tool outcomes are recorded without chat text in audit logs; bounded owner-only conversation records use normal retention settings.
