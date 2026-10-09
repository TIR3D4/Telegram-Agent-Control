#!/usr/bin/env python3
"""Interactive configuration; never print secrets or overwrite an existing .env."""

import getpass
import json
import os
import secrets
from pathlib import Path


def main():
    path = Path(".env")
    if path.exists():
        print("Existing .env preserved. Use tacctl config to edit.")
        return
    token = getpass.getpass("Telegram bot token (hidden; leave empty for setup only): ").strip()
    chats = input("Allowed channel IDs/usernames, comma separated: ").strip()
    domain = input("HTTPS domain (optional; DNS must point here): ").strip()
    if domain and (not all(c.isalnum() or c in ".-" for c in domain) or "." not in domain):
        raise SystemExit("Enter a hostname without a URL or path")
    password = secrets.token_urlsafe(32)
    values = {
        "TAC_BOT_TOKEN": token,
        "TAC_OWNER_KEY": secrets.token_urlsafe(40),
        "TAC_AGENT_KEY": secrets.token_urlsafe(40),
        "TAC_READER_KEY": secrets.token_urlsafe(40),
        "TAC_LEGACY_AGENT_KEYS_ENABLED": "false",
        "TAC_WEBHOOK_SECRET": secrets.token_urlsafe(40),
        "TAC_ALLOWED_CHATS": chats,
        "TAC_DB_PASSWORD": password,
        "TAC_DATABASE_URL": f"postgresql+psycopg://tac:{password}@postgres:5432/tac",
        "TAC_STORAGE_DIR": "/data/media",
        "TAC_PUBLIC_URL": "https://" + domain if domain else "http://127.0.0.1:8787",
        "TAC_TIMEZONE": "Asia/Tehran",
        "TAC_BIND": "127.0.0.1",
        "TAC_PORT": "8787",
        "TAC_DOMAIN": domain or "localhost",
        "COMPOSE_PROFILES": "tls" if domain else "",
    }
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as f:
        for k, v in values.items():
            f.write(k + "=" + json.dumps(v) + "\n")
    print("Configuration saved with mode 0600. Open .env privately to copy your owner key.")


if __name__ == "__main__":
    main()
