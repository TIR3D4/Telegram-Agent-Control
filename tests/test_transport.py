import json
import pytest
import httpx
from tac.telegram import Telegram, TelegramError
from tac.registry import registry
from tac.db import Session
from tac.media import store


@pytest.mark.parametrize("method", list(registry()["methods"]))
def test_each_method_transports_without_sdk_gaps(method):
    seen = []

    def reply(request):
        seen.append(request)
        return httpx.Response(200, json={"ok": True, "result": True})

    api = Telegram(httpx.Client(transport=httpx.MockTransport(reply)))
    assert api.call(method, {}) is True
    assert seen[0].url.path.endswith("/" + method)
    assert json.loads(seen[0].content) == {}


def test_multipart_preserves_nested_json_and_binary():
    seen = []

    def reply(request):
        seen.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 4}})

    api = Telegram(httpx.Client(transport=httpx.MockTransport(reply)))
    with Session.begin() as db:
        a = store(db, b"binary-contents", "test.jpg", "image/jpeg")
        api.call(
            "sendMediaGroup",
            {"chat_id": "@test_channel", "media": [{"type": "photo", "media": "attach://a"}]},
            {"a": a.id},
            db,
        )
    raw = seen[0].content
    assert b"binary-contents" in raw
    assert b"attach://a" in raw
    assert "multipart/form-data" in seen[0].headers["content-type"]


def test_telegram_error_contains_retry_after():
    api = Telegram(
        httpx.Client(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(
                    429,
                    json={
                        "ok": False,
                        "error_code": 429,
                        "description": "retry",
                        "parameters": {"retry_after": 7},
                    },
                )
            )
        )
    )
    with pytest.raises(TelegramError) as error:
        api.call("getMe", {})
    assert error.value.retry_after == 7
