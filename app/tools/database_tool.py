"""Safe database tool for agent read-only SQL access."""

from __future__ import annotations

import asyncio
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.database import SessionLocal
from app.tools.base_tool import BaseTool, ToolOutput


class DatabaseTool(BaseTool):
    """Executes validated read-only SQL queries with strict safeguards."""

    _READ_PREFIX_RE = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)
    _FORBIDDEN_SQL_RE = re.compile(
        r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|MERGE|GRANT|REVOKE|CREATE|REPLACE|ATTACH|DETACH|PRAGMA|VACUUM|CALL|EXEC|COPY)\b",
        re.IGNORECASE,
    )
    _PARAM_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    def __init__(self, query_timeout_seconds: int = 5, max_rows: int = 200) -> None:
        super().__init__(
            name="database_query_safe",
            description="Execute secure read-only SQL queries using validated parameters",
        )
        self.query_timeout_seconds = query_timeout_seconds
        self.max_rows = max_rows

    def get_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Read-only SQL query (SELECT/WITH only)",
                },
                "params": {
                    "type": "object",
                    "description": "Named SQL parameters for prepared statements",
                    "additionalProperties": {
                        "type": ["string", "number", "boolean", "null"],
                    },
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of rows returned",
                    "minimum": 1,
                    "maximum": 200,
                },
            },
            "required": ["query"],
        }

    async def execute(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        limit: int = 100,
        **_: Any,
    ) -> ToolOutput:
        if not query or not query.strip():
            return ToolOutput(success=False, result=None, error="query is required")

        validation_error = self._validate_query(query)
        if validation_error:
            return ToolOutput(success=False, result=None, error=validation_error)

        safe_params, params_error = self._validate_params(params or {})
        if params_error:
            return ToolOutput(success=False, result=None, error=params_error)

        row_limit = max(1, min(int(limit), self.max_rows))

        try:
            result_payload = await asyncio.wait_for(
                asyncio.to_thread(self._run_query, query, safe_params, row_limit),
                timeout=self.query_timeout_seconds,
            )
            return ToolOutput(success=True, result=result_payload)
        except asyncio.TimeoutError:
            return ToolOutput(
                success=False,
                result=None,
                error=f"query timeout after {self.query_timeout_seconds}s",
            )
        except SQLAlchemyError as exc:
            return ToolOutput(success=False, result=None, error=f"database error: {str(exc)}")
        except Exception as exc:  # pragma: no cover - defensive path
            return ToolOutput(success=False, result=None, error=f"tool error: {str(exc)}")

    def _validate_query(self, query: str) -> str | None:
        candidate = query.strip()
        if ";" in candidate:
            return "multiple SQL statements are not allowed"
        if not self._READ_PREFIX_RE.match(candidate):
            return "only SELECT/WITH read-only queries are allowed"
        if self._FORBIDDEN_SQL_RE.search(candidate):
            return "query contains forbidden SQL operation"
        return None

    def _validate_params(self, params: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        safe_params: dict[str, Any] = {}
        for key, value in params.items():
            if not isinstance(key, str) or not self._PARAM_KEY_RE.match(key):
                return {}, f"invalid parameter name: {key!r}"
            if not isinstance(value, (str, int, float, bool, type(None))):
                return {}, f"invalid parameter value for '{key}'"
            safe_params[key] = value
        return safe_params, None

    def _run_query(self, query: str, params: dict[str, Any], row_limit: int) -> dict[str, Any]:
        db = SessionLocal()
        try:
            # PostgreSQL statement timeout for server-side enforcement.
            if db.bind is not None and db.bind.dialect.name == "postgresql":
                timeout_ms = int(self.query_timeout_seconds * 1000)
                db.execute(text("SET LOCAL statement_timeout = :timeout"), {"timeout": timeout_ms})

            statement = text(query)
            result = db.execute(statement, params)
            rows = result.fetchmany(row_limit)
            columns = list(result.keys())
            data = [dict(zip(columns, row)) for row in rows]

            return {
                "rows": data,
                "row_count": len(data),
                "limit": row_limit,
                "truncated": len(data) >= row_limit,
            }
        finally:
            db.close()
