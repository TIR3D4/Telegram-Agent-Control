import os
import tempfile
from pathlib import Path
import pytest

ROOT = Path(tempfile.mkdtemp(prefix="tac-tests-"))
os.environ["TAC_DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", "sqlite:///" + str(ROOT / "test.sqlite"))
os.environ["TAC_STORAGE_DIR"] = str(ROOT / "media")
os.environ["TAC_OWNER_KEY"] = "owner-" + "x" * 40
os.environ["TAC_AGENT_KEY"] = "agent-" + "x" * 40
os.environ["TAC_READER_KEY"] = "reader-" + "x" * 40
os.environ["TAC_WEBHOOK_SECRET"] = "webhook-" + "x" * 40
os.environ["TAC_ALLOWED_CHATS"] = "@test_channel,-100123456789"
os.environ["TAC_BOT_TOKEN"] = "123456:test-token-for-local-mocks-only"
from tac.db import Base, engine
from tac.api import app
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def owner():
    return {"Authorization": "Bearer " + os.environ["TAC_OWNER_KEY"]}


@pytest.fixture
def agent():
    return {"Authorization": "Bearer " + os.environ["TAC_AGENT_KEY"]}


class FakeTelegram:
    def __init__(self, result=None, error=None):
        self.calls = []
        self.result = result
        self.error = error

    def call(self, method, payload, attachments=None, db=None):
        self.calls.append((method, payload))
        if self.error:
            raise self.error
        if self.result is not None:
            return self.result
        if method.startswith("send"):
            return {
                "message_id": 42,
                "chat": {"id": -100123456789, "username": "test_channel"},
                "text": payload.get("text", ""),
            }
        return True
