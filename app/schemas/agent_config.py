"""Agent configuration and execution schemas."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AgentToolConfig(BaseModel):
    """Configuration for a tool in an agent."""
    name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.-]+$")
    enabled: bool = True


class AgentLLMConfig(BaseModel):
    """LLM configuration for an agent."""
    provider: str = Field(..., min_length=2, max_length=50, description="LLM provider: openai, anthropic, etc.")
    model: str = Field(..., min_length=2, max_length=120, description="Model name (e.g., gpt-4-turbo-preview)")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(2048, ge=100, le=4096, description="Max tokens to generate")
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0, description="Nucleus sampling")


class AgentMemoryConfig(BaseModel):
    """Memory configuration for an agent."""
    enable_conversation_memory: bool = True
    enable_vector_memory: bool = True
    conversation_history_limit: int = 20
    vector_memory_enabled_for_semantic_search: bool = False


class AgentConfig(BaseModel):
    """Complete agent configuration."""
    name: str = Field(..., min_length=1, max_length=255, description="Agent name")
    system_prompt: str = Field(
        ...,
        min_length=1,
        max_length=12000,
        description="System prompt that defines the agent's behavior"
    )
    description: Optional[str] = Field(None, max_length=2000, description="Agent description")
    llm: AgentLLMConfig = Field(..., description="LLM provider configuration")
    memory: Optional[AgentMemoryConfig] = Field(default_factory=AgentMemoryConfig)
    tools: Optional[List[str]] = Field(default_factory=list, description="List of allowed tool names")
    max_tool_loops: int = Field(5, ge=1, le=20, description="Max iterations for tool calling loop")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")

    def to_dict(self) -> dict:
        """Convert to dict format for engine."""
        return {
            "name": self.name,
            "system_prompt": self.system_prompt,
            "description": self.description,
            "llm_provider": self.llm.provider,
            "llm_model": self.llm.model,
            "temperature": self.llm.temperature,
            "max_tokens": self.llm.max_tokens,
            "tools": self.tools or [],
            "max_tool_loops": self.max_tool_loops,
        }


class AgentExecutionInput(BaseModel):
    """Input for agent execution."""
    message: str = Field(..., min_length=1, max_length=8000, description="User message to agent")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")


class AgentExecutionStep(BaseModel):
    """A step in agent execution."""
    step_number: int
    action: str  # load_config, build_prompt, call_llm, execute_tool, update_memory, complete
    timestamp: str
    details: Dict[str, Any]
    duration_ms: Optional[int] = None
    success: bool = True
    error: Optional[str] = None


class AgentExecutionResultResponse(BaseModel):
    """Response with agent execution result."""
    execution_id: str
    agent_id: str
    status: str  # pending, running, completed, failed
    response: Optional[str] = None
    steps: List[AgentExecutionStep]
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    execution_time_ms: int = 0
    tools_executed: int = 0
    error: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
