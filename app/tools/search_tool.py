"""Web search tool for agent internet search with structured output."""

from __future__ import annotations

import re
from html import unescape
from typing import Any
from urllib.parse import quote

import httpx

from app.tools.base_tool import BaseTool, ToolOutput


class SearchTool(BaseTool):
    """Runs lightweight web search and returns parsed structured results."""

    _QUERY_PATTERN = re.compile(r"^[\w\s\-.,:!?()]{2,200}$")
    _RESULT_RE = re.compile(
        r'<a[^>]*class="result__a"[^>]*href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )

    def __init__(self, timeout_seconds: int = 8, max_results: int = 5) -> None:
        super().__init__(
            name="web_search",
            description="Search the web and return structured search results",
        )
        self.timeout_seconds = timeout_seconds
        self.max_results = max_results

    def get_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query text",
                    "minLength": 2,
                    "maxLength": 200,
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of search results",
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str, limit: int = 5, **_: Any) -> ToolOutput:
        cleaned_query = (query or "").strip()
        if not self._QUERY_PATTERN.match(cleaned_query):
            return ToolOutput(success=False, result=None, error="invalid search query")

        safe_limit = max(1, min(int(limit), min(self.max_results, 10)))
        url = f"https://duckduckgo.com/html/?q={quote(cleaned_query)}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(url, headers={"Accept": "text/html"})
                response.raise_for_status()

            results = self._parse_results(response.text, safe_limit)
            return ToolOutput(
                success=True,
                result={
                    "query": cleaned_query,
                    "results": results,
                    "count": len(results),
                },
            )
        except httpx.TimeoutException:
            return ToolOutput(success=False, result=None, error=f"search timeout after {self.timeout_seconds}s")
        except httpx.HTTPError as exc:
            return ToolOutput(success=False, result=None, error=f"search request failed: {str(exc)}")
        except Exception as exc:  # pragma: no cover - defensive path
            return ToolOutput(success=False, result=None, error=f"search tool error: {str(exc)}")

    def _parse_results(self, html: str, limit: int) -> list[dict[str, str]]:
        parsed: list[dict[str, str]] = []
        for match in self._RESULT_RE.finditer(html):
            title = self._strip_html(unescape(match.group("title")))
            url = unescape(match.group("url"))
            if not title or not url:
                continue
            parsed.append({"title": title, "url": url})
            if len(parsed) >= limit:
                break
        return parsed

    def _strip_html(self, value: str) -> str:
        return re.sub(r"<[^>]+>", "", value).strip()
