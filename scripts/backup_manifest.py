#!/usr/bin/env python3
"""Create/verify backup checksums without credentials or unsafe path expansion."""

import hashlib
import json
import re
import subprocess
import sys
import tarfile
from pathlib import Path
from datetime import datetime, timezone

FILES = {"database.dump", "media.tar.gz"}


def checksum(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def verify(directory):
    directory = Path(directory)
    meta = json.loads((directory / "manifest.json").read_text())
    if set(meta["files"]) != FILES or not re.fullmatch(r"[0-9a-f]{40}", meta["commit"]):
        raise ValueError("Invalid backup manifest")
    for name in FILES:
        p = directory / name
        if p.is_symlink() or not p.is_file() or checksum(p) != meta["files"][name]:
            raise ValueError("Backup checksum mismatch: " + name)
    # The media store is flat. Never extract links, devices or traversal entries.
    with tarfile.open(directory / "media.tar.gz", "r:gz") as archive:
        for member in archive:
            if member.name in {".", "./"} and member.isdir():
                continue
            name = member.name.removeprefix("./")
            if name == ".assistant-vault":
                if not member.isfile() or member.size != 44 or member.mode & 0o777 != 0o600:
                    raise ValueError("Unsafe assistant vault entry")
                continue
            if not member.isfile() or not re.fullmatch(r"[0-9a-f]{32}(?:\.[a-z0-9]{1,10})?", name):
                raise ValueError("Unsafe media archive member")
    return meta


def create(directory):
    directory = Path(directory)
    meta = {
        "format": 1,
        "name": directory.name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "files": {name: checksum(directory / name) for name in sorted(FILES)},
    }
    path = directory / "manifest.json"
    path.write_text(json.dumps(meta, indent=2) + "\n")
    path.chmod(0o600)
    return verify(directory)


if __name__ == "__main__":
    action, directory = sys.argv[1:]
    if action == "create":
        create(directory)
    elif action == "verify":
        verify(directory)
    else:
        raise SystemExit("Expected create or verify")
    print("Backup manifest " + action + " succeeded")
