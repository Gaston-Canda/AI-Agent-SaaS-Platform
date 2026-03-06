"""
Extended schemas for production features.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class UserRoleEnum(str, Enum):
    """User roles."""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class ExecutionLogResponse(BaseModel):
    """Response model for execution log."""
    id: str
    execution_id: str
    step: int
    action: str
    details: Dict[str, Any]
    timestamp: datetime
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    llm_provider: Optional[str] = None
    tokens_used: int = 0
    llm_latency_ms: int = 0
    tool_latency_ms: int = 0
    total_execution_time_ms: int = 0
    
    model_config = ConfigDict(from_attributes=True)


class ExecutionDetailResponse(BaseModel):
    """Enhanced execution response with logs and metrics."""
    id: str
    agent_id: str
    status: str
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    logs: List[ExecutionLogResponse] = []
    
    model_config = ConfigDict(from_attributes=True)


class AgentUsageResponse(BaseModel):
    """Agent usage metrics."""
    id: str
    tenant_id: str
    agent_id: str
    execution_id: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    execution_time_ms: int
    cost_usd: float
    model_used: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class TenantSubscriptionResponse(BaseModel):
    """Tenant subscription details."""
    id: str
    tenant_id: str
    plan_name: str
    executions_per_minute: int
    executions_per_day: int
    concurrent_executions: int
    tokens_per_month: int
    custom_models: bool
    advanced_tools: bool
    
    model_config = ConfigDict(from_attributes=True)


class TenantUserResponse(BaseModel):
    """Tenant user with role."""
    id: str
    user_id: str
    tenant_id: str
    role: UserRoleEnum
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class UsageStatsResponse(BaseModel):
    """Usage statistics for a time period."""
    period_start: datetime
    period_end: datetime
    total_executions: int
    successful_executions: int
    failed_executions: int
    total_tokens: int
    total_execution_time_ms: int
    estimated_cost_usd: float
