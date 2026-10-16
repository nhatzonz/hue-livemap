import logging
import re
import time
import uuid

logger = logging.getLogger("hue_livemap.request")

# Chỉ nhận request id an toàn từ client (chống chèn ký tự xuống dòng/giả mạo dòng log)
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


class RequestLogMiddleware:
    """ASGI thuần (nhẹ hơn BaseHTTPMiddleware, không chặn streaming): gắn X-Request-Id và ghi một dòng log
    method, path, status, thời gian — kể cả khi request ném lỗi (ghi 500)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin-1")
        request_id = incoming if _SAFE_REQUEST_ID.match(incoming) else uuid.uuid4().hex[:16]
        started = time.perf_counter()
        status = 500

        async def send_with_id(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message.setdefault("headers", []).append((b"x-request-id", request_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            logger.info(
                "%s %s %s %.1fms rid=%s",
                scope["method"],
                scope["path"],
                status,
                (time.perf_counter() - started) * 1000,
                request_id,
            )
