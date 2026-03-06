"""Shared testing fakes for Phase 3 tests."""

from dataclasses import dataclass
from typing import Any, Optional

from app.llm.base_provider import LLMResponse
from app.tools.base_tool import BaseTool, ToolOutput


class FakeLLMProvider:
    """Deterministic fake provider with queued responses."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self._index = 0

    async def call(self, *args: Any, **kwargs: Any) -> LLMResponse:
        if self._index >= len(self._responses):
            return LLMResponse(content="No more fake responses", tool_calls=None, usage=None)
        response = self._responses[self._index]
        self._index += 1
        return response


class EchoTool(BaseTool):
    """Simple tool for integration tests."""

    def __init__(self) -> None:
        super().__init__(name="echo_tool", description="Return input text")

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
            },
            "required": ["text"],
        }

    async def execute(self, **kwargs: Any) -> ToolOutput:
        return ToolOutput(success=True, result=kwargs.get("text"), error=None)


class FakeMemoryManager:
    """In-memory memory manager replacement for worker tests."""

    def __init__(self, memory_id: str) -> None:
        self.memory_id = memory_id
        self.messages: list[tuple[str, str]] = []

    async def get_context_for_llm(self, max_tokens: int = 2000) -> str:
        _ = max_tokens
        return ""

    async def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        _ = kwargs
        self.messages.append((role, content))


@dataclass
class FakeStep:
    """Lightweight execution step structure for worker tests."""

    step_number: int
    action: str
    details: dict
    duration_ms: int = 0
    success: bool = True
    error: Optional[str] = None


class FakeExecutionContext:
    """ExecutionContext-like object used by worker task tests."""

    def __init__(self) -> None:
        self.steps: list[FakeStep] = []
        self.prompt_tokens = 11
        self.completion_tokens = 7
        self.total_cost_usd = 0.0
        self.tools_executed: list[dict] = []

