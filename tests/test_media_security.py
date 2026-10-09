from tac.security import redact
from tac.telegram import Telegram
from tac.media import index_pack
from tac.db import Session, Emoji


def test_redaction():
    assert redact({"secret_token": "hidden", "x": "123456789:" + "x" * 36}) == {
        "secret_token": "[REDACTED]",
        "x": "[REDACTED]",
    }


def test_emoji_index_preserves_visual_labels():
    pack = {
        "name": "FinanceEmoji",
        "sticker_type": "custom_emoji",
        "stickers": [
            {"custom_emoji_id": "6000000000000000001", "file_id": "f", "emoji": "✅", "is_animated": True}
        ],
    }
    with Session.begin() as db:
        index_pack(db, pack)
        db.flush()
        e = db.get(Emoji, "6000000000000000001")
        e.labels = {"description": "blue glass check"}
        e.reviewed = True
    with Session.begin() as db:
        index_pack(db, pack)
        db.flush()
        e = db.get(Emoji, "6000000000000000001")
        assert e.format == "tgs"
        assert e.labels["description"] == "blue glass check"


def test_bot_file_paths_reject_traversal():
    import pytest

    for path in ["../.env", "/etc/passwd", "https://bad.example/x"]:
        with pytest.raises(ValueError):
            Telegram().download(path)
