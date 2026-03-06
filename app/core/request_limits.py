"""Request size limiting middleware."""

from __future__ import annotations

from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Rejects requests with body size above configured maximum."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        max_bytes = settings.MAX_REQUEST_BODY_BYTES
        content_length = request.headers.get("content-length")

        if content_length is not None:
            try:
                if int(content_length) > max_bytes:
                    return Response(status_code=413, content="Request entity too large")
            except ValueError:
                return Response(status_code=400, content="Invalid content-length header")

        if content_length is None and request.method.upper() in {"POST", "PUT", "PATCH"}:
            body = await request.body()
            if len(body) > max_bytes:
                return Response(status_code=413, content="Request entity too large")

            async def receive() -> dict:
                return {"type": "http.request", "body": body, "more_body": False}

            request._receive = receive  # type: ignore[attr-defined]

        return await call_next(request)
