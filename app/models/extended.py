"""
Extended models for production SaaS platform.
Includes roles, usage tracking, and execution details.
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, JSON, Text, Enum as SQLEnum, Index, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

from app.db.database import Base
from app.models.agent_platform import AgentVersion, AgentTool, AgentPrompt  # Backward-compat imports


class UserRole(str, enum.Enum):
    """User roles for RBAC."""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class ExecutionStatus(str, enum.Enum):
    """Execution status states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TenantUser(Base):
    """Enhanced user-tenant relationship with roles."""
    __tablename__ = "tenant_users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.MEMBER, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User")
    tenant = relationship("Tenant")
    
    __table_args__ = (
        Index("idx_tenant_user_ids", "user_id", "tenant_id"),
        Index("idx_tenant_id", "tenant_id"),
    )


class ExecutionLog(Base):
    """Detailed logs for agent execution steps."""
    __tablename__ = "execution_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    execution_id = Column(String(36), ForeignKey("agent_executions.id"), nullable=False)
    step = Column(Integer, nullable=False)  # Sequential step number
    action = Column(String(100), nullable=False)  # e.g., "prompt_sent", "tool_call", "response_received"
    details = Column(JSON, nullable=False)  # Step details
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Phase 3: Token tracking for cost calculation
    prompt_tokens = Column(Integer, default=0, nullable=False)
    completion_tokens = Column(Integer, default=0, nullable=False)
    cost_usd = Column(Float, default=0.0, nullable=False)
    llm_provider = Column(String(50), nullable=True)  # "openai", "anthropic"
    tokens_used = Column(Integer, default=0, nullable=False)
    llm_latency_ms = Column(Integer, default=0, nullable=False)
    tool_latency_ms = Column(Integer, default=0, nullable=False)
    total_execution_time_ms = Column(Integer, default=0, nullable=False)
    
    __table_args__ = (
        Index("idx_execution_logs_execution_id", "execution_id"),
        Index("idx_execution_logs_timestamp", "timestamp"),
        Index("idx_execution_logs_cost", "execution_id", "cost_usd"),
    )


class AgentUsage(Base):
    """Track usage metrics for billing and monitoring."""
    __tablename__ = "agent_usage"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=False)
    execution_id = Column(String(36), ForeignKey("agent_executions.id"), nullable=False)
    
    # Usage metrics
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    execution_time_ms = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)  # Calculated cost
    
    # Metadata
    model_used = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_usage_tenant_id", "tenant_id"),
        Index("idx_usage_agent_id", "agent_id"),
        Index("idx_usage_created_at", "created_at"),
    )


class TenantSubscription(Base):
    """Subscription plans and limits for tenants."""
    __tablename__ = "tenant_subscriptions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, unique=True)
    plan_id = Column(String(36), ForeignKey("subscription_plans.id"), nullable=True)
    
    # Plan information
    plan_name = Column(String(50), default="free")  # free, starter, professional, enterprise
    status = Column(String(30), nullable=False, default="active")
    
    # Rate limits
    executions_per_minute = Column(Integer, default=10)
    executions_per_day = Column(Integer, default=1000)
    concurrent_executions = Column(Integer, default=5)

    # Token limits
    tokens_per_month = Column(Integer, default=100000)  # 0 = unlimited
    max_executions_month = Column(Integer, default=1000)
    max_agents = Column(Integer, default=3)
    max_tool_calls = Column(Integer, default=500)

    # Features
    custom_models = Column(Boolean, default=False)
    advanced_tools = Column(Boolean, default=False)
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    cancel_at_period_end = Column(Boolean, default=False)
    trial_start = Column(DateTime, nullable=True)
    trial_end = Column(DateTime, nullable=True)
    trial_active = Column(Boolean, default=True)
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    plan = relationship("SubscriptionPlan")
    
    __table_args__ = (
        Index("idx_subscription_tenant_id", "tenant_id"),
    )


class AgentMemory(Base):
    """Long-term semantic memory entries for agents."""
    __tablename__ = "agent_memories"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=False, default=[])
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_agent_memories_tenant_agent", "tenant_id", "agent_id"),
        Index("idx_agent_memories_created_at", "created_at"),
    )


class AuditLog(Base):
    """Security and compliance audit event log."""
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    action = Column(String(120), nullable=False)
    event_metadata = Column("metadata", JSON, nullable=False, default={})

    __table_args__ = (
        Index("idx_audit_logs_tenant_timestamp", "tenant_id", "timestamp"),
        Index("idx_audit_logs_user_timestamp", "user_id", "timestamp"),
        Index("idx_audit_logs_action_timestamp", "action", "timestamp"),
    )
