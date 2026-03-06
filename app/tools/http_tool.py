"""Safe HTTP tool for agent outbound API calls."""

from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

from app.tools.base_tool import BaseTool, ToolOutput


class HTTPTool(BaseTool):
    """Performs validated outbound HTTP calls with network safeguards."""

    _ALLOWED_METHODS = {"GET", "POST"}
    _ALLOWED_HEADER_PREFIXES = ("accept", "content-type", "x-")

    def __init__(self, timeout_seconds: int = 10, max_response_bytes: int = 100_000) -> None:
        super().__init__(
            name="http_api",
            description="Call external HTTP APIs safely using GET or POST",
        )
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes

    def get_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "External HTTP/HTTPS URL"},
                "method": {"type": "string", "enum": ["GET", "POST"]},
                "headers": {
                    "type": "object",
                    "description": "Safe outbound request headers",
                    "additionalProperties": {"type": "string"},
                },
                "json": {
                    "type": "object",
                    "description": "JSON payload for POST requests",
                    "additionalProperties": True,
                },
            },
            "required": ["url"],
        }

    async def execute(
        self,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        **_: Any,
    ) -> ToolOutput:
        validation_error = self._validate_request(url=url, method=method, headers=headers or {})
        if validation_error:
            return ToolOutput(success=False, result=None, error=validation_error)

        request_method = method.upper()
        safe_headers = self._sanitize_headers(headers or {})

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True) as client:
                response = await client.request(
                    method=request_method,
                    url=url,
                    headers=safe_headers,
                    json=json if request_method == "POST" else None,
                )

            raw_content = response.content[: self.max_response_bytes]
            body_text = raw_content.decode("utf-8", errors="replace")

            return ToolOutput(
                success=True,
                result={
                    "status_code": response.status_code,
                    "url": str(response.url),
                    "headers": dict(response.headers),
                    "body": body_text,
                    "truncated": len(response.content) > self.max_response_bytes,
                },
            )
        except httpx.TimeoutException:
            return ToolOutput(success=False, result=None, error=f"request timeout after {self.timeout_seconds}s")
        except httpx.HTTPError as exc:
            return ToolOutput(success=False, result=None, error=f"http error: {str(exc)}")
        except Exception as exc:  # pragma: no cover - defensive path
            return ToolOutput(success=False, result=None, error=f"tool error: {str(exc)}")

    def _validate_request(self, url: str, method: str, headers: dict[str, str]) -> str | None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return "url must use http or https"
        if not parsed.netloc:
            return "url host is required"

        if method.upper() not in self._ALLOWED_METHODS:
            return "method must be GET or POST"

        if self._is_private_target(parsed.hostname):
            return "private/internal network targets are not allowed"

        for key, value in headers.items():
            if not isinstance(key, str) or not isinstance(value, str):
                return "headers must be string key/value pairs"
            if not key.lower().startswith(self._ALLOWED_HEADER_PREFIXES):
                return f"header '{key}' is not allowed"

        return None

    def _sanitize_headers(self, headers: dict[str, str]) -> dict[str, str]:
        return {
            key: value
            for key, value in headers.items()
            if key.lower().startswith(self._ALLOWED_HEADER_PREFIXES)
        }

    def _is_private_target(self, hostname: str | None) -> bool:
        if not hostname:
            return True
        lowered = hostname.lower()
        if lowered in {"localhost", "127.0.0.1", "::1"}:
            return True

        try:
            infos = socket.getaddrinfo(hostname, None)
        except socket.gaierror:
            return True

        for info in infos:
            ip_str = info[4][0]
            ip_addr = ipaddress.ip_address(ip_str)
            if (
                ip_addr.is_private
                or ip_addr.is_loopback
                or ip_addr.is_link_local
                or ip_addr.is_multicast
                or ip_addr.is_reserved
            ):
                return True
        return False
