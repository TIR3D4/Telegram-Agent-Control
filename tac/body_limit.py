"""Count streamed bytes before multipart/JSON parsing; Content-Length is not trusted."""

from starlette.responses import JSONResponse


class PayloadTooLarge(Exception):
    pass


class BodyLimit:
    def __init__(self, app, maximum):
        self.app, self.maximum = app, maximum

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        limit = self.maximum if scope["path"] == "/v1/assets" else 2 * 1024 * 1024
        length = dict(scope.get("headers", [])).get(b"content-length", b"0")
        if length.isdigit() and int(length) > limit:
            return await JSONResponse({"detail": "Request body exceeds configured limit"}, status_code=413)(
                scope, receive, send
            )
        size, started = 0, False

        async def limited_receive():
            nonlocal size
            message = await receive()
            size += len(message.get("body", b""))
            if size > limit:
                raise PayloadTooLarge()
            return message

        async def tracked_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except PayloadTooLarge:
            if not started:
                await JSONResponse({"detail": "Request body exceeds configured limit"}, status_code=413)(
                    scope, receive, send
                )
