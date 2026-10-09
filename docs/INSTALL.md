# Installation and configuration

See [v0.2 installation](INSTALLATION.md) for the review-branch command and lifecycle overview.

## Requirements

Linux VPS, Python 3 for setup, Git, Docker Engine and Compose v2. Allow outgoing HTTPS to Telegram and image/package registries. For public HTTPS, point a domain at the server and open ports 80/443. The optional Caddy service obtains certificates. Do not expose PostgreSQL externally.

```bash
git clone --branch engineering/production-hardening-v0.2 https://github.com/TIR3D4/Telegram-Agent-Control.git
cd Telegram-Agent-Control
./scripts/install.sh
```

The bootstrap can offer [Docker's official convenience installer](https://docs.docker.com/engine/install/). For managed hosts install Docker from its official distribution-specific repository first. Setup never replaces an existing `.env`.

## Configuration

| Variable | Purpose |
|---|---|
| `TAC_BOT_TOKEN` | BotFather credential; server only |
| `TAC_OWNER_KEY` | Approval, reconciliation, maintenance and all read/write access |
| `TAC_AGENT_KEY`, `TAC_READER_KEY` | Legacy compatibility keys; disabled on fresh interactive installs |
| `TAC_LEGACY_AGENT_KEYS_ENABLED` | Disable after migration to scoped grants; new installer writes false |
| OAuth / expiry / quota controls | See [MCP setup](MCP_SETUP.md), [permissions](PERMISSIONS.md) and `.env.example` |
| `TAC_ALLOWED_CHATS` | Comma-separated numeric IDs and/or `@usernames`; denied when absent |
| `TAC_WEBHOOK_SECRET` | Verify `X-Telegram-Bot-Api-Secret-Token` on webhook requests |
| `TAC_DATABASE_URL` | SQLAlchemy PostgreSQL connection string |
| `TAC_DB_PASSWORD` | Compose PostgreSQL password; must match the URL |
| `TAC_STORAGE_DIR` | Media volume path, `/data/media` in Compose |
| `TAC_DOMAIN`, `TAC_PUBLIC_URL` | Public HTTPS hostname and canonical URL |
| `COMPOSE_PROFILES=tls` | Enable the Caddy service |
| `TAC_BIND`, `TAC_PORT` | Local interface/port; default `127.0.0.1:8787` |
| `TAC_UPLOAD_LIMIT_MB` | Application upload/download bound; default 50 MB |
| `TAC_TIMEZONE` | Default IANA timezone; `Asia/Tehran` |

Use `./scripts/tacctl config` to edit secrets privately, then restart. Never paste keys into GitHub issues. If rotating the database password on an existing PostgreSQL volume, change the database role password as well; changing `.env` alone does not update the initialized database.

## First-run acceptance

1. `./scripts/tacctl doctor` passes and the worker heartbeat appears in Overview.
2. Create a `getMe` operation; poll until succeeded.
3. Use returned bot ID in `getChatMember` for the intended channel. Check relevant post/edit/delete rights.
4. Send a prepared post to a test channel after owner approval. Inspect the returned URL and native rendering.
5. Repeat for photo, album, rich slideshow and required premium emoji contexts.
6. Schedule an approved operation a few minutes ahead, restart services and verify exactly one confirmed result.
7. Run a backup/restore drill on a separate test installation.

Do not interpret `201 Created` as Telegram delivery. It only acknowledges the operation record.

## Webhook

Set the webhook using an owner-approved `setWebhook` operation with the HTTPS URL ending `/v1/webhook`, the configured secret token and the required `allowed_updates`. The payload can contain the secret but API responses/logs redact it. Manage this from the owner console, without sharing the secret with the agent. A single bot cannot use webhook delivery and `getUpdates` polling simultaneously.

## Local source development

Create a virtual environment and install `requirements.lock`, then `pip install --no-deps -e .`. Set owner/agent keys in environment. `alembic upgrade head` creates the SQLite development database. Run `tac serve` and `tac worker` separately. Never run multiple workers on SQLite.


## Password login, mobile console and automated OAuth

See [CONNECTIONS.md](CONNECTIONS.md) for the current setup/update flow. The owner key remains a private recovery credential; normal browser use is username/password.
