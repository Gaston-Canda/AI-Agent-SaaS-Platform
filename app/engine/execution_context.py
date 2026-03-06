"""Execution context for agent runs."""
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel


class ExecutionContextStep(BaseModel):
    """A step in agent execution."""
    step_number: int
    action: str  # "load_config", "build_prompt", "call_llm", "execute_tool", "update_memory", "complete"
    timestamp: datetime
    details: Dict[str, Any]
    duration_ms: Optional[int] = None
    success: bool = True
    error: Optional[str] = None


class ExecutionContext:
    """
    Context for a single agent execution.
    
    Tracks:
    - Agent configuration
    - Current step
    - Messages sent to LLM
    - Tools executed
    - Memory state
    """

    def __init__(
        self,
        agent_id: str,
        execution_id: str,
        user_id: str,
        tenant_id: str
    ):
        """Initialize execution context."""
        self.agent_id = agent_id
        self.execution_id = execution_id
        self.user_id = user_id
        self.tenant_id = tenant_id
        
        self.start_time = datetime.now()
        self.steps: List[ExecutionContextStep] = []
        
        # LLM interaction tracking
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_cost_usd = 0.0
        self.llm_latency_ms = 0
        self.tool_latency_ms = 0
        
        # Tool execution tracking
        self.tools_executed: List[Dict[str, Any]] = []
        
        # Current state
        self.current_step = 0
        self.agent_config: Optional[Dict[str, Any]] = None
        self.llm_provider: Optional[str] = None
        self.allowed_tools: List[str] = []
        
        # Results
        self.final_response: Optional[str] = None
        self.status: str = "pending"  # pending, running, completed, failed

    def record_step(
        self,
        action: str,
        details: Dict[str, Any],
        duration_ms: int = 0,
        success: bool = True,
        error: Optional[str] = None
    ) -> None:
        """
        Record a step in execution.
        
        Args:
            action: Step action (load_config, build_prompt, etc.)
            details: Details about the step
            duration_ms: How long the step took
            success: Whether step succeeded
            error: Error message if failed
        """
        self.current_step += 1
        
        step = ExecutionContextStep(
            step_number=self.current_step,
            action=action,
            timestamp=datetime.now(),
            details=details,
            duration_ms=duration_ms,
            success=success,
            error=error
        )
        
        self.steps.append(step)

    def record_llm_call(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
        response_preview: str = "",
        latency_ms: int = 0,
    ) -> None:
        """Record an LLM API call."""
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_cost_usd += cost_usd
        self.llm_latency_ms += latency_ms
        
        self.record_step(
            action="call_llm",
            details={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cost_usd": cost_usd,
                "response_preview": response_preview[:200],
                "latency_ms": latency_ms,
            }
        )

    def record_tool_execution(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        success: bool,
        result: Optional[Any] = None,
        error: Optional[str] = None,
        duration_ms: int = 0
    ) -> None:
        """Record tool execution."""
        self.tools_executed.append({
            "tool_name": tool_name,
            "success": success,
            "duration_ms": duration_ms,
            "timestamp": datetime.now().isoformat()
        })
        self.tool_latency_ms += duration_ms
        
        self.record_step(
            action="execute_tool",
            details={
                "tool_name": tool_name,
                "tool_input": tool_input,
                "result_preview": str(result)[:100] if result else None
            },
            duration_ms=duration_ms,
            success=success,
            error=error
        )

    def get_execution_time_ms(self) -> int:
        """Get total execution time in milliseconds."""
        elapsed = datetime.now() - self.start_time
        return int(elapsed.total_seconds() * 1000)

    def get_cost_estimate(self) -> Dict[str, float]:
        """Get cost breakdown."""
        return {
            "llm_calls": self.total_cost_usd,
            "total": self.total_cost_usd
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        return {
            "agent_id": self.agent_id,
            "execution_id": self.execution_id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "status": self.status,
            "start_time": self.start_time.isoformat(),
            "duration_ms": self.get_execution_time_ms(),
            "steps": [
                {
                    "step_number": s.step_number,
                    "action": s.action,
                    "timestamp": s.timestamp.isoformat(),
                    "details": s.details,
                    "duration_ms": s.duration_ms,
                    "success": s.success,
                    "error": s.error
                }
                for s in self.steps
            ],
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_cost_usd": self.total_cost_usd,
            "llm_latency_ms": self.llm_latency_ms,
            "tool_latency_ms": self.tool_latency_ms,
            "tools_executed": self.tools_executed,
            "final_response": self.final_response
        }
