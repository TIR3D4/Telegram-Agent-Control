import json
from contextlib import ExitStack
import httpx
from .config import settings
from .db import Asset


class TelegramError(Exception):
    def __init__(self, code, description, retry_after=None):
        self.code = code
        self.description = description
        self.retry_after = retry_after
        super().__init__(description)


class Telegram:
    def __init__(self, client=None):
        self.client = client or httpx.Client(timeout=httpx.Timeout(30, connect=10), follow_redirects=False)

    def call(self, method, payload, attachments=None, db=None):
        token = settings().bot_token.get_secret_value()
        if not token:
            raise TelegramError(401, "Bot token is not configured")
        url = f"{settings().telegram_base}/bot{token}/{method}"
        with ExitStack() as stack:
            if attachments:
                files = {}
                for name, aid in attachments.items():
                    asset = db.get(Asset, aid)
                    if not asset:
                        raise TelegramError(400, "Missing uploaded asset")
                    fp = stack.enter_context(open(settings().storage_dir / aid, "rb"))
                    files[name] = (asset.name, fp, asset.mime)
                data = {
                    k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list, bool)) else str(v)
                    for k, v in payload.items()
                }
                response = self.client.post(url, data=data, files=files)
            else:
                response = self.client.post(url, json=payload)
        try:
            body = response.json()
        except ValueError:
            raise httpx.ReadError("Invalid upstream response") from None
        if not body.get("ok"):
            raise TelegramError(
                body.get("error_code", response.status_code),
                body.get("description", "Telegram rejected request"),
                body.get("parameters", {}).get("retry_after"),
            )
        return body["result"]

    def download(self, file_path):
        # Only a path returned by Telegram; no arbitrary local files or hosts.
        if file_path.startswith("/") or ".." in file_path.split("/") or "://" in file_path:
            raise ValueError("Unsafe Telegram file path")
        url = f"{settings().telegram_base}/file/bot{settings().bot_token.get_secret_value()}/{file_path}"
        data = bytearray()
        with self.client.stream("GET", url) as response:
            response.raise_for_status()
            for part in response.iter_bytes():
                data.extend(part)
                if len(data) > settings().upload_limit_mb * 1024 * 1024:
                    raise ValueError("File exceeds configured limit")
        return bytes(data)
