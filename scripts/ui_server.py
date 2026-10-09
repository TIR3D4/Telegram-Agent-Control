import os
import subprocess
import sys

os.environ["TAC_DATABASE_URL"] = "sqlite:///./data/ui.sqlite"
os.environ["TAC_OWNER_KEY"] = "ui-test-owner-" + "x" * 40
os.environ["TAC_AGENT_KEY"] = "ui-test-agent-" + "x" * 40
os.environ["TAC_ALLOWED_CHATS"] = "@ui_test"
os.environ["TAC_PUBLIC_URL"] = "http://127.0.0.1:8790"
os.environ["TAC_API_URL"] = "http://127.0.0.1:8790"
subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
os.execv(
    sys.executable,
    [
        sys.executable,
        "-m",
        "uvicorn",
        "tac.api:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8790",
        "--no-access-log",
    ],
)
