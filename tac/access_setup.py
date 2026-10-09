"""Operator-only initial OAuth grant setup, using the existing owner API policy."""

from datetime import timedelta
import httpx
from sqlalchemy import select
from .config import settings
from .db import Session, AgentGrant, now


def ensure_grant():
    config = settings()
    subject = config.owner_oauth_subject
    if not subject:
        return
    with Session() as db:
        existing = db.scalar(select(AgentGrant).where(AgentGrant.oauth_subject == subject))
        if existing:
            print("Existing OAuth grant preserved; inspect its expiry/revocation in Agent permissions.")
            return
    with httpx.Client(timeout=20, trust_env=False) as client:
        response = client.post(
            "http://127.0.0.1:8787/v1/agents",
            headers={
                "Authorization": "Bearer " + config.owner_key.get_secret_value(),
            },
            json={
                "name": "Owner's AI connection",
                "preset": "OPERATE",
                "oauth_subject": subject,
                "chats": sorted(config.chats),
                "expires_at": (now() + timedelta(days=90)).isoformat(),
                "rpm": 120,
                "daily_operations": 500,
            },
        )
        if response.status_code != 201:
            raise SystemExit(
                f"Initial OAuth grant failed: HTTP {response.status_code}. Use Agent permissions in the console."
            )
    print(
        "Initial 90-day OPERATE grant created. Review or revoke it in the console; owner approval is still required for writes."
    )


if __name__ == "__main__":
    ensure_grant()
