import pytest
from jsonschema import Draft202012Validator
from tac.registry import registry, describe, validate


@pytest.mark.parametrize("method", list(registry()["methods"]))
def test_every_method_schema_resolves(method):
    schema = describe(method)["schema"]
    Draft202012Validator.check_schema({k: v for k, v in schema.items() if k != "$defs"})
    refs = []

    def walk(v):
        if isinstance(v, dict):
            if "$ref" in v:
                refs.append(v["$ref"])
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk({k: v for k, v in schema.items() if k != "$defs"})
    assert all(r.startswith("#/$defs/") and r[8:] in schema["$defs"] for r in refs)


def test_version_and_required_features():
    r = registry()
    assert r["version"] == "10.3"
    assert len(r["methods"]) == 185
    assert len(r["types"]) == 400
    for name in [
        "close",
        "sendRichMessage",
        "sendMediaGroup",
        "pinChatMessage",
        "unpinAllChatMessages",
        "deleteMessages",
    ]:
        assert name in r["methods"]
    assert "InputRichBlockSlideshow" in r["types"]


def test_nested_keyboard_rejects_invalid_payload():
    p = {
        "chat_id": "@test_channel",
        "text": "Hello",
        "reply_markup": {"inline_keyboard": [[{"text": "Open", "url": "https://t.me", "style": "pink"}]]},
    }
    with pytest.raises(ValueError):
        validate("sendMessage", p)
    p["reply_markup"]["inline_keyboard"][0][0]["style"] = "primary"
    validate("sendMessage", p)
    p["reply_markup"]["inline_keyboard"][0][0]["callback_data"] = "test"
    with pytest.raises(ValueError):
        validate("sendMessage", p)


def test_slideshow_and_unknown_fields():
    validate(
        "sendRichMessage",
        {
            "chat_id": "@test_channel",
            "rich_message": {
                "html": '<tg-slideshow><img src="https://example.com/a.jpg"/></tg-slideshow>',
                "is_rtl": True,
            },
        },
    )
    with pytest.raises(ValueError):
        validate("sendRichMessage", {"chat_id": 1, "rich_message": {"html": "x", "markdown": "x"}})
    with pytest.raises(ValueError):
        validate("sendPhoto", {"chat_id": 1, "photo": "file", "nonexistent": True})
    with pytest.raises(ValueError):
        validate("sendMediaGroup", {"chat_id": 1, "media": [{"type": "photo", "media": "f"}]})


def test_all_definitions_resolve():
    defs = {name: item["schema"] for name, item in registry()["types"].items()}
    Draft202012Validator.check_schema({"$defs": defs})


@pytest.mark.parametrize(
    "keyboard", [None, 7, "wrong", [None], [[None]], [[{"text": "X", "callback_data": 4}]]]
)
def test_malformed_keyboards_are_validation_errors(keyboard):
    with pytest.raises(ValueError):
        validate("sendMessage", {"chat_id": 1, "text": "X", "reply_markup": {"inline_keyboard": keyboard}})
