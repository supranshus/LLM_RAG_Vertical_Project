import logging
import re
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import request_id_var, user_var

logger = logging.getLogger("app.request")
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


class RequestContextMiddleware:
    """Assigns a request id, returns it as X-Request-ID, and logs one line per request.

    Pure ASGI (not BaseHTTPMiddleware) so context variables set while handling the
    request, such as the signed-in user, are still visible when the line is logged.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin-1")
        request_id = incoming if _SAFE_REQUEST_ID.match(incoming) else uuid.uuid4().hex[:12]
        request_id_var.set(request_id)
        user_var.set("-")
        status = 500
        start = time.perf_counter()

        async def send_with_request_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.info("%s %s -> %s (%.0f ms)", scope["method"], scope["path"], status, elapsed_ms)
