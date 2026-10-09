import json
import logging
import sys
from datetime import datetime, timezone
from .security import redact
from .config import settings


class Formatter(logging.Formatter):
    def format(self, r):
        data = {
            "time": datetime.now(timezone.utc).isoformat(),
            "level": r.levelname,
            "logger": r.name,
            "event": r.getMessage(),
        }
        for k in (
            "request_id",
            "trace_id",
            "actor",
            "tool",
            "operation_id",
            "status",
            "duration_ms",
            "method",
            "path",
            "error_type",
        ):
            if hasattr(r, k):
                data[k] = getattr(r, k)
        return json.dumps(redact(data), ensure_ascii=False)


def setup():
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(Formatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings().log_level)
    # HTTP libraries would otherwise print Bot API URLs containing credentials.
    for name in ("httpx", "httpx2", "httpcore", "httpcore2", "uvicorn.access"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
