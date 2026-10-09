# Installation — Ubuntu 24.04

Requirements: Git, Python 3, Docker Engine and Compose v2; outbound HTTPS to Telegram and package/image registries. Production uses PostgreSQL 17 and persistent volumes. Suggested initial VPS size is 2 vCPU / 2–4 GB RAM / 20 GB disk, an estimate rather than a load benchmark.

For the review branch:

```bash
git clone --branch engineering/production-hardening-v0.2 https://github.com/TIR3D4/Telegram-Agent-Control.git
cd Telegram-Agent-Control
./scripts/install.sh
```

Review source before executing installation scripts. The bootstrap offers Docker installation after a local prompt. For managed servers, install Docker from its official Ubuntu repository first. Existing `.env` is preserved. Configuration prompts hide the bot token, generate random bootstrap secrets and create `.env` with mode 0600. New installations disable legacy shared agent keys; issue scoped grants in the console.

The default host port binds only to `127.0.0.1:8787`. Use an SSH tunnel, or configure the optional Caddy HTTPS profile with a real hostname, DNS and ports 80/443. PostgreSQL has no published host port. Application processes run as UID 10001 in the container. The application listens on all container interfaces so the proxy can reach it; direct source execution defaults to localhost.

```bash
ssh -L 8787:127.0.0.1:8787 user@server
./scripts/tacctl doctor
./scripts/tacctl status
```

Read [configuration and first-run tests](INSTALL.md). `.env.example` contains all newly introduced options. Do not use example credentials. The console stores its key only in tab memory, not localStorage. Login as the human owner; create finite grants for agents. [OAuth setup](MCP_SETUP.md) requires an independently configured issuer.

## Lifecycle commands

| Command | Effect |
|---|---|
| `tacctl` / `menu` | Interactive numbered terminal menu |
| `install`, `config`, `doctor` | Setup, private environment editing, configuration and DB readiness |
| `start`, `stop`, `restart`, `status`, `logs` | Compose service lifecycle and bounded log tail |
| `update` | Backup, fast-forward source, build, migrate, pause execution, restart |
| `backup`, `verify-backup PATH` | Consistent snapshot and manifest verification |
| `restore PATH`, `restore-request ID` | Controlled destructive restore and execution pause |
| `rollback PATH` | Restore code commit and backup after typed confirmation |
| `credentials` | Guidance to the audited scoped-credential console workflow |
| `uninstall` | Remove services, retain data and secrets |
| `purge` | Separately confirm permanent volume deletion; backups and `.env` remain |

There is no systemd installer, fancy terminal dashboard, unattended destructive updater or automatic production rollout. Compose is the supported service manager; the terminal UI is a simple interactive menu. See [upgrade](UPGRADE.md) and [backup/restore](BACKUP_RESTORE.md).
