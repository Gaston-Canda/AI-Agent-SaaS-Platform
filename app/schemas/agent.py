"""
Pydantic schemas for agent-related endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, Any, Dict
from datetime import datetime


class AgentBase(BaseModel):
    """Base agent schema."""
    name: str = Field(..., min_length=1, max_length=255, pattern=r"^[A-Za-z0-9 _.\-]+$")
    description: Optional[str] = Field(default=None, max_length=2000)
    agent_type: str = Field(
        ...,
        min_length=2,
        max_length=50,
        pattern=r"^[a-zA-Z][a-zA-Z0-9_\-]{1,49}$",
        description="Type of agent: chat, task, automation",
    )
    system_prompt: Optional[str] = Field(default=None, max_length=12000)
    model: str = Field(default="gpt-4", min_length=2, max_length=120)
    config: Dict[str, Any] = Field(default_factory=dict)


class AgentCreate(AgentBase):
    """Schema for creating an agent."""
    pass


class AgentUpdate(BaseModel):
    """Schema for updating an agent."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=255, pattern=r"^[A-Za-z0-9 _.\-]+$")
    description: Optional[str] = Field(default=None, max_length=2000)
    system_prompt: Optional[str] = Field(default=None, max_length=12000)
    model: Optional[str] = Field(default=None, min_length=2, max_length=120)
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class AgentResponse(AgentBase):
    """Schema for agent response."""
    id: str
    tenant_id: str
    created_by: str
    version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AgentExecutionInput(BaseModel):
    """Schema for agent execution input."""
    input_data: Dict[str, Any]


class AgentExecuteRequest(BaseModel):
    """Minimal execution payload for direct API testing."""
    message: str = Field(..., min_length=1, max_length=8000)


class AgentExecutionResponse(BaseModel):
    """Schema for agent execution response."""
    id: str
    agent_id: str
    status: str
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class AgentExecuteResultResponse(BaseModel):
    """Direct execution response with runtime metrics."""
    execution_id: str
    response: str
    tokens_used: int
    execution_time_ms: int
    tools_executed: list[str]
    status: str


class AgentExecuteAsyncResponse(BaseModel):
    """Response for async execution enqueue."""
    execution_id: str
    status: str


class AgentExecutionHistoryItem(BaseModel):
    """Execution history item."""
    id: str
    agent_id: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    execution_time_ms: Optional[int] = None
    llm_provider: Optional[str] = None
    tools_called: Optional[list[dict]] = None

    class Config:
        from_attributes = True
