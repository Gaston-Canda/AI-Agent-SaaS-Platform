"""Tool Executor - executes tools requested by LLM."""
import asyncio
import time
from typing import Optional
from pydantic import BaseModel
from app.tools.base_tool import ToolOutput
from app.tools.tool_registry import ToolRegistry
from app.tools.tool_safety import ToolSafetyManager
from app.monitoring.logging import StructuredLogger
from app.core.tenant_guard import enforce_tenant_match
from app.monitoring.audit_logger import AuditLogger


logger = StructuredLogger(__name__)


class ToolExecutionError(Exception):
    """Error during tool execution."""
    pass


class ToolExecutionResult(BaseModel):
    """Rich tool execution result with observability fields."""
    success: bool
    output: object = None
    error: Optional[str] = None
    execution_time_ms: int = 0

    @property
    def result(self) -> object:
        """Backward-compatible alias for old ToolOutput contract."""
        return self.output


class ToolExecutor:
    """
    Executes tools that agents request.
    
    The AgentEngine asks LLM what to do. If LLM says "execute tool X with params Y",
    the ToolExecutor handles the actual execution.
    """

    def __init__(self, allowed_tools: list[str]):
        """
        Initialize executor with allowed tools.
        
        Args:
            allowed_tools: List of tool names this executor can use
        """
        # Validate all tools exist
        exist, missing = ToolRegistry.validate_tools_exist(allowed_tools)
        if not exist:
            raise ValueError(f"Tools not found: {missing}")
        
        self.allowed_tools = set(allowed_tools)
        self.safety = ToolSafetyManager()

    async def execute_tool(
        self,
        tool_name: str,
        tool_input: dict,
        execution_id: str | None = None,
        step_id: int | None = None,
        tenant_id: str | None = None,
        timeout_seconds: int = 30,
        max_retries: int = 2,
    ) -> ToolExecutionResult:
        """
        Execute a single tool.
        
        Args:
            tool_name: Name of tool to execute
            tool_input: Parameters for the tool
            execution_id: For logging/tracking
            step_id: For logging/tracking
            
        Returns:
            ToolOutput with result or error
            
        Raises:
            ToolExecutionError: If tool execution fails
        """
        # Check if tool is allowed
        allowed, whitelist_error = self.safety.validate_tool_allowed(tool_name, self.allowed_tools)
        if not allowed:
            error_msg = whitelist_error or f"Tool '{tool_name}' not allowed. Allowed: {self.allowed_tools}"
            logger.log_error(
                error_msg,
                {"execution_id": execution_id, "step_id": step_id, "tool": tool_name}
            )
            return ToolExecutionResult(success=False, output=None, error=error_msg, execution_time_ms=0)

        calls_allowed, calls_error = self.safety.check_and_increment_calls(execution_id)
        if not calls_allowed:
            logger.log_error(
                calls_error or "tool_safety_violation",
                {"execution_id": execution_id, "step_id": step_id, "tool": tool_name},
            )
            return ToolExecutionResult(success=False, output=None, error=calls_error, execution_time_ms=0)
        
        # Get tool from registry
        tool = ToolRegistry.get_tool(tool_name)
        if not tool:
            error_msg = f"Tool '{tool_name}' not found in registry"
            return ToolExecutionResult(success=False, output=None, error=error_msg, execution_time_ms=0)

        if tenant_id and isinstance(tool_input, dict) and "tenant_id" in tool_input:
            try:
                enforce_tenant_match(str(tool_input.get("tenant_id")), tenant_id, "tool_input")
            except Exception as exc:
                return ToolExecutionResult(success=False, output=None, error=str(exc), execution_time_ms=0)

        last_error: str | None = None
        effective_timeout = max(1, min(timeout_seconds, self.safety.policy.timeout_seconds))
        effective_retries = min(max_retries, self.safety.policy.max_retries)
        for attempt in range(1, effective_retries + 2):
            started = time.perf_counter()
            try:
                logger.log_execution(
                    f"Tool execution started: {tool_name}",
                    {
                        "execution_id": execution_id,
                        "step_id": step_id,
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                        "attempt": attempt,
                    },
                )
                AuditLogger.log_event(
                    db=None,
                    action="tool_execution_started",
                    tenant_id=tenant_id,
                    user_id=None,
                    metadata={"execution_id": execution_id, "tool_name": tool_name, "attempt": attempt},
                )

                raw_result = await asyncio.wait_for(
                    tool.execute(**tool_input),
                    timeout=effective_timeout,
                )
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                result = ToolExecutionResult(
                    success=raw_result.success,
                    output=raw_result.result,
                    error=raw_result.error,
                    execution_time_ms=elapsed_ms,
                )
                logger.log_execution(
                    f"Tool execution completed: {tool_name}",
                    {
                        "execution_id": execution_id,
                        "step_id": step_id,
                        "tool_name": tool_name,
                        "success": result.success,
                        "execution_time_ms": result.execution_time_ms,
                        "error": result.error,
                    },
                )
                AuditLogger.log_event(
                    db=None,
                    action="tool_execution_completed",
                    tenant_id=tenant_id,
                    user_id=None,
                    metadata={
                        "execution_id": execution_id,
                        "tool_name": tool_name,
                        "success": result.success,
                        "execution_time_ms": result.execution_time_ms,
                    },
                )
                return result
            except asyncio.TimeoutError:
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                last_error = f"Tool execution timeout after {effective_timeout}s"
                logger.log_error(
                    "Tool timeout",
                    {
                        "execution_id": execution_id,
                        "step_id": step_id,
                        "tool_name": tool_name,
                        "execution_time_ms": elapsed_ms,
                        "attempt": attempt,
                    },
                )
                AuditLogger.log_event(
                    db=None,
                    action="tool_execution_timeout",
                    tenant_id=tenant_id,
                    user_id=None,
                    metadata={"execution_id": execution_id, "tool_name": tool_name, "attempt": attempt},
                )
            except Exception as exc:
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                last_error = f"Tool execution error: {str(exc)}"
                logger.log_error(
                    "Tool execution error",
                    {
                        "execution_id": execution_id,
                        "step_id": step_id,
                        "tool_name": tool_name,
                        "execution_time_ms": elapsed_ms,
                        "attempt": attempt,
                        "error": str(exc),
                    },
                )
                AuditLogger.log_event(
                    db=None,
                    action="tool_execution_error",
                    tenant_id=tenant_id,
                    user_id=None,
                    metadata={"execution_id": execution_id, "tool_name": tool_name, "attempt": attempt, "error": str(exc)},
                )

        return ToolExecutionResult(
            success=False,
            output=None,
            error=last_error or "Tool execution failed",
            execution_time_ms=0,
        )

    async def execute_tool_sequence(
        self,
        tool_calls: list[dict],
        execution_id: str = None,
        tenant_id: str | None = None,
    ) -> list[ToolExecutionResult]:
        """
        Execute a sequence of tool calls.
        
        Useful when LLM wants to execute multiple tools in sequence.
        
        Args:
            tool_calls: List of {"tool_name": str, "tool_input": dict, ...}
            execution_id: For logging
            
        Returns:
            List of ToolOutput results
        """
        results = []
        for i, tool_call in enumerate(tool_calls):
            tool_name = tool_call.get("tool_name")
            tool_input = tool_call.get("tool_input", {})
            
            result = await self.execute_tool(
                tool_name=tool_name,
                tool_input=tool_input,
                execution_id=execution_id,
                step_id=i,
                tenant_id=tenant_id,
            )
            results.append(result)
        
        return results

    def get_available_tools_for_llm(self) -> list[dict]:
        """Get allowed tools in format for LLM tool calling."""
        return ToolRegistry.get_tools_for_llm(list(self.allowed_tools))

    def can_execute_tool(self, tool_name: str) -> bool:
        """Check if an executor can execute a specific tool."""
        return tool_name in self.allowed_tools
