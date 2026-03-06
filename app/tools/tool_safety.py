"""Tool safety policies and limits."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class ToolSafetyPolicy:
    """Execution safety policy for tools."""

    timeout_seconds: int = settings.DEFAULT_TOOL_TIMEOUT_SECONDS
    max_retries: int = settings.MAX_TOOL_RETRIES
    max_calls_per_execution: int = settings.MAX_TOOL_CALLS_PER_EXECUTION


class ToolSafetyManager:
    """Tracks and validates tool execution safety constraints."""

    def __init__(self, policy: ToolSafetyPolicy | None = None) -> None:
        self.policy = policy or ToolSafetyPolicy()
        self._execution_calls: dict[str, int] = {}

    def validate_tool_allowed(self, tool_name: str, allowed_tools: set[str]) -> tuple[bool, str | None]:
        if tool_name not in allowed_tools:
            return False, f"Tool '{tool_name}' is not in allowed whitelist"
        return True, None

    def check_and_increment_calls(self, execution_id: str | None) -> tuple[bool, str | None]:
        key = execution_id or "global"
        used = self._execution_calls.get(key, 0)
        if used >= self.policy.max_calls_per_execution:
            return False, f"Tool call limit exceeded ({self.policy.max_calls_per_execution})"

        self._execution_calls[key] = used + 1
        return True, None
