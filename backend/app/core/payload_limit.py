"""Payload Size Limiting ASGI Middleware.

Phase C13.3 — Corrective Pass:
Enforces a strict 64 KB (65,536 bytes) maximum request body limit on public RFQ
endpoints BEFORE the full body is passed to FastAPI's route parser.

Handles:
- Explicit oversized Content-Length headers.
- Missing or omitted Content-Length headers (e.g. chunked transfer encoding).
- Misleading or spoofed Content-Length headers where actual body exceeds limit.
- Returns a consistent HTTP 413 response without crashing or exhausting server resources.
"""

from typing import Final

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings

PAYLOAD_TOO_LARGE_BODY: Final[bytes] = (
    b'{"success":false,"error":{"code":"PAYLOAD_TOO_LARGE","message":"Request payload exceeds maximum permitted size (64 KB)."},"detail":"Request payload exceeds maximum permitted size (64 KB)."}'
)


class PayloadSizeLimitMiddleware:
    """ASGI Middleware enforcing strict byte limits on incoming request streams."""

    def __init__(self, app: ASGIApp, max_bytes: int | None = None) -> None:
        self.app = app
        self.max_bytes = max_bytes if max_bytes is not None else settings.MAX_PAYLOAD_BYTES

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        # Apply payload ceiling to public endpoints (RFQ submission and public routes)
        if not path.startswith("/api/v1/public/rfq"):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))

        # 1. Fast check: declared Content-Length header
        content_length_raw = headers.get(b"content-length")
        if content_length_raw:
            try:
                content_length = int(content_length_raw.decode("latin1"))
                if content_length > self.max_bytes:
                    await self._send_413(send)
                    return
            except ValueError:
                pass

        # 2. Streaming check: buffer chunks up to max_bytes before dispatching to app
        bytes_received = 0
        body_chunks: list[bytes] = []
        more_body = True

        while more_body:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                await self.app(scope, receive, send)
                return

            chunk = message.get("body", b"")
            bytes_received += len(chunk)
            if bytes_received > self.max_bytes:
                await self._send_413(send)
                return

            body_chunks.append(chunk)
            more_body = message.get("more_body", False)

        full_body = b"".join(body_chunks)

        # Replay the safely buffered body to downstream Starlette/FastAPI handlers
        has_sent = False

        async def buffered_receive() -> Message:
            nonlocal has_sent
            if not has_sent:
                has_sent = True
                return {"type": "http.request", "body": full_body, "more_body": False}
            return await receive()

        await self.app(scope, buffered_receive, send)

    async def _send_413(self, send: Send) -> None:
        """Emits an immediate, standardized HTTP 413 response."""
        await send({
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(PAYLOAD_TOO_LARGE_BODY)).encode("ascii")),
            ],
        })
        await send({
            "type": "http.response.body",
            "body": PAYLOAD_TOO_LARGE_BODY,
        })
