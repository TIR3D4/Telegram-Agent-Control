import json
import re
from pathlib import Path
from functools import lru_cache
from jsonschema import Draft202012Validator


@lru_cache
def registry():
    return json.loads((Path(__file__).parent / "data/registry.json").read_text())


def describe(name):
    data = registry()
    if name not in data["methods"]:
        raise ValueError("Unknown method for pinned API version")
    entry = dict(data["methods"][name])
    all_defs = {n: e["schema"] for n, e in data["types"].items()}
    defs = {}

    def visit(value):
        if isinstance(value, dict):
            ref = value.get("$ref", "")
            if ref.startswith("#/$defs/"):
                name = ref.removeprefix("#/$defs/")
                if name not in defs:
                    defs[name] = all_defs[name]
                    visit(all_defs[name])
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(entry["schema"])
    entry["schema"] = {
        **entry["schema"],
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": defs,
    }
    return entry


def validate(name, payload):
    spec = describe(name)
    errors = [
        f"{'/'.join(map(str, e.absolute_path)) or '$'}: {e.message[:220]}"
        for e in Draft202012Validator(spec["schema"]).iter_errors(payload)
    ]
    # Cross-field rules assume the structure has already passed JSON Schema.
    if errors:
        raise ValueError("; ".join(errors[:8]))

    def walk(obj):
        if isinstance(obj, dict):
            if "inline_keyboard" in obj:
                for row in obj["inline_keyboard"]:
                    for b in row:
                        actions = set(b) - {"text", "icon_custom_emoji_id", "style"}
                        if len(actions) != 1:
                            errors.append("Inline button must have exactly one action")
                        if b.get("style") not in (None, "primary", "success", "danger"):
                            errors.append("Invalid inline button style")
                        if "callback_data" in b and not 1 <= len(b["callback_data"].encode()) <= 64:
                            errors.append("callback_data must be 1–64 bytes")
            if "rich_message" in obj:
                if sum(k in obj["rich_message"] for k in ("html", "markdown", "blocks")) != 1:
                    errors.append("rich_message requires exactly one of html/markdown/blocks")
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(payload)
    if name == "sendMediaGroup" and not 2 <= len(payload.get("media", [])) <= 10:
        errors.append("Album requires 2–10 items")
    if name == "getCustomEmojiStickers" and len(payload.get("custom_emoji_ids", [])) > 200:
        errors.append("At most 200 IDs")
    if errors:
        raise ValueError("; ".join(errors[:8]))
    return spec


def attachment_names(obj):
    if isinstance(obj, str):
        return set(re.findall(r"attach://([A-Za-z0-9_-]+)", obj))
    if isinstance(obj, dict):
        return set().union(*(attachment_names(v) for v in obj.values()))
    if isinstance(obj, list):
        return set().union(*(attachment_names(v) for v in obj))
    return set()
