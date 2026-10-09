"""Docker Compose installation smoke: no real bot credentials or external sends."""

import json
import secrets
import subprocess
import time
from pathlib import Path
import httpx

password = secrets.token_urlsafe(32)
owner = secrets.token_urlsafe(40)
values = {
    "TAC_DB_PASSWORD": password,
    "TAC_DATABASE_URL": f"postgresql+psycopg://tac:{password}@postgres:5432/tac",
    "TAC_STORAGE_DIR": "/data/media",
    "TAC_OWNER_KEY": owner,
    "TAC_AGENT_KEY": secrets.token_urlsafe(40),
    "TAC_ALLOWED_CHATS": "@ci_test",
    "TAC_BOT_TOKEN": "",
    "TAC_PORT": "8787",
}
Path(".env").write_text("\n".join(k + "=" + json.dumps(v) for k, v in values.items()) + "\n")
try:
    subprocess.run(["docker", "compose", "up", "-d", "--build"], check=True)
    with httpx.Client(trust_env=False, timeout=5) as c:
        for attempt in range(45):
            try:
                response = c.get(
                    "http://127.0.0.1:8787/v1/system", headers={"Authorization": "Bearer " + owner}
                )
                if response.status_code == 200 and response.json().get("worker"):
                    assert response.json()["methods"] == 185
                    print("Compose API, PostgreSQL, migration and worker smoke passed")
                    break
            except httpx.HTTPError:
                pass
            time.sleep(2)
        else:
            raise RuntimeError("Compose not ready")
finally:
    subprocess.run(["docker", "compose", "down", "-v"])
    Path(".env").unlink(missing_ok=True)
