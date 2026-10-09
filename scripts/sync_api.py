#!/usr/bin/env python3
"""Build a reproducible registry from Telegram's official HTML. Never run at app startup."""

import argparse
import hashlib
import json
import re
import urllib.request
from pathlib import Path
from bs4 import BeautifulSoup

URL = "https://core.telegram.org/bots/api"


def build(html):
    soup = BeautifulSoup(html, "html.parser")
    sections = {}
    for h in soup.select("h4"):
        name = h.get_text(strip=True)
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]+", name):
            continue
        nodes = []
        for n in h.next_siblings:
            if getattr(n, "name", "") in ("h3", "h4"):
                break
            if getattr(n, "name", None):
                nodes.append(n)
        sections[name] = nodes
    methods, types, unknown = {}, {}, set()

    def schema(raw):
        raw = raw.strip()
        if raw.startswith("Array of "):
            return {"type": "array", "items": schema(raw[9:])}
        parts = re.split(r"\s+(?:or|and)\s+|,\s*(?:or\s+)?", raw)
        if len(parts) > 1:
            return {"anyOf": [schema(x) for x in parts if x]}
        primitive = {
            "String": "string",
            "Integer": "integer",
            "Boolean": "boolean",
            "Float": "number",
            "Float number": "number",
        }
        if raw in primitive:
            return {"type": primitive[raw]}
        if raw == "True":
            return {"const": True}
        if raw == "InputFile":
            return {"type": "string", "description": "Use attach://name with an uploaded asset binding."}
        if raw in sections:
            return {"$ref": "#/$defs/" + raw}
        unknown.add(raw)
        return {"description": "Unresolved: " + raw}

    for name, nodes in sections.items():
        description = "\n".join(n.get_text(" ", strip=True) for n in nodes if n.name == "p")
        table = next((n for n in nodes if n.name == "table"), None)
        method = name[0].islower()
        if method and name in ("getting-updates",):
            continue
        fields, required = {}, []
        if table:
            for row in table.select("tbody tr"):
                cells = row.find_all("td", recursive=False)
                if len(cells) < 3:
                    continue
                field, raw = [c.get_text(" ", strip=True) for c in cells[:2]]
                desc = cells[-1].get_text(" ", strip=True)
                fields[field] = schema(raw)
                fields[field]["description"] = desc
                if (method and len(cells) == 4 and cells[2].get_text(strip=True) == "Yes") or (
                    not method and not desc.startswith("Optional")
                ):
                    required.append(field)
                fixed = re.search(r"(?:always|must be) [“\"]([^”\"]+)[”\"]", desc, re.I)
                if fixed and "type" in fields[field] and fields[field]["type"] == "string":
                    fields[field]["const"] = fixed.group(1)
            obj = {
                "type": "object",
                "properties": fields,
                "required": required,
                "additionalProperties": False,
            }
        elif not method:
            links = [a.get_text(strip=True) for n in nodes if n.name == "ul" for a in n.select("li > a")]
            links = [x for x in links if x in sections and x != name]
            obj = (
                {"anyOf": [{"$ref": "#/$defs/" + x} for x in links]}
                if links
                else {"type": "object", "properties": {}, "additionalProperties": False}
            )
        else:
            obj = {"type": "object", "properties": {}, "additionalProperties": False}
        if name == "InputFile":
            obj = schema("InputFile")
        entry = {"description": description, "schema": obj, "source": URL + "#" + name.lower()}
        if method:
            # Names of actual methods are lowerCamelCase; headings are excluded.
            if re.fullmatch("[a-z]+[A-Z][A-Za-z0-9]*", name) or name == "close":
                entry["effect"] = "read" if name.startswith("get") and name != "getUpdates" else "write"
                methods[name] = entry
        else:
            types[name] = entry
    if unknown:
        raise ValueError("Unknown types: " + repr(sorted(unknown)))
    version = re.search(r"Bot API (\d+\.\d+)", soup.get_text()).group(1)
    return {
        "version": version,
        "source": URL,
        "source_sha256": hashlib.sha256(html.encode()).hexdigest(),
        "methods": methods,
        "types": types,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--html")
    p.add_argument("--output", default="tac/data/registry.json")
    a = p.parse_args()
    html = Path(a.html).read_text() if a.html else urllib.request.urlopen(URL, timeout=30).read().decode()
    registry = build(html)
    Path(a.output).write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n")
    print(
        f"Bot API {registry['version']}: {len(registry['methods'])} methods, {len(registry['types'])} types"
    )
