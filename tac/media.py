import hashlib
import io
import subprocess
import sys
from pathlib import Path
from PIL import Image
from .config import settings
from .db import Asset, uid, Emoji
from .telegram import Telegram


def store(db, data, name, mime):
    if len(data) > settings().upload_limit_mb * 1024 * 1024:
        raise ValueError("Upload too large")
    aid = uid()
    settings().storage_dir.mkdir(parents=True, exist_ok=True)
    (settings().storage_dir / aid).write_bytes(data)
    a = Asset(
        id=aid, name=Path(name).name[:200], mime=mime, size=len(data), sha256=hashlib.sha256(data).hexdigest()
    )
    db.add(a)
    db.flush()
    return a


def index_pack(db, result):
    if result.get("sticker_type") != "custom_emoji":
        return
    for sticker in result.get("stickers", []):
        eid = sticker.get("custom_emoji_id")
        if not eid:
            continue
        e = db.get(Emoji, eid)
        if not e:
            e = Emoji(id=eid, labels={})
            db.add(e)
        e.pack = result["name"]
        e.alt = sticker.get("emoji", "")
        e.file_id = sticker["file_id"]
        e.format = "tgs" if sticker.get("is_animated") else "webm" if sticker.get("is_video") else "webp"


def preview(db, e):
    if e.preview_id:
        return e
    api = Telegram()
    try:
        file = api.call("getFile", {"file_id": e.file_id})
        data = api.download(file["file_path"])
        original = store(
            db,
            data,
            e.id + "." + e.format,
            {"tgs": "application/gzip", "webm": "video/webm", "webp": "image/webp"}[e.format],
        )
        original.actor = "catalog"
        e.asset_id = original.id
        path = settings().storage_dir / original.id
        out = settings().storage_dir / (original.id + ".png")
        if e.format == "webp":
            with Image.open(io.BytesIO(data)) as im:
                im.thumbnail((256, 256))
                im.convert("RGBA").save(out, "PNG")
        elif e.format == "webm":
            subprocess.run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-v",
                    "error",
                    "-i",
                    str(path),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=256:256:force_original_aspect_ratio=decrease",
                    str(out),
                ],
                check=True,
                timeout=20,
                capture_output=True,
            )
        else:
            subprocess.run(
                [sys.executable, "-m", "tac.render_tgs", str(path), str(out)],
                check=True,
                timeout=20,
                capture_output=True,
            )
        rendered = store(db, out.read_bytes(), e.id + ".png", "image/png")
        rendered.actor = "catalog"
        e.preview_id = rendered.id
        out.unlink(missing_ok=True)
        e.error = None
    except Exception as exc:
        e.error = type(exc).__name__ + ": preview unavailable"
    return e
