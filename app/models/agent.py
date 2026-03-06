"""
AI Agent model for the SaaS platform.
"""

from sqlalchemy import (
    Column, String, Text, DateTime, ForeignKey, Index, JSON, Boolean, Integer, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

from app.db.database import Base


class AgentStatus(str, enum.Enum):
    """Status of an agent."""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class Agent(Base):
    """AI Agent model."""
    __tablename__ = "agents"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    agent_type = Column(String(50), nullable=False)  # e.g., "chat", "task", "automation"
    config = Column(JSON, default={})  # Store agent-specific configuration (DEPRECATED - use AgentVersion instead)
    system_prompt = Column(Text)  # DEPRECATED - use AgentVersion instead
    model = Column(String(100), nullable=False, default="gpt-4")  # DEPRECATED - use AgentVersion instead
    is_active = Column(Boolean, default=True)
    version = Column(Integer, default=1)  # DEPRECATED - use AgentVersion instead
    
    # Phase 3: Agent Platform
    status = Column(SQLEnum(AgentStatus), default=AgentStatus.DRAFT, nullable=False)
    default_version_id = Column(String(36), ForeignKey("agent_versions.id"), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="agents")
    creator = relationship("User")
    executions = relationship("AgentExecution", back_populates="agent", cascade="all, delete-orphan")
    versions = relationship(
        "AgentVersion",
        back_populates="agent",
        cascade="all, delete-orphan",
        foreign_keys="AgentVersion.agent_id"
    )
    default_version = relationship(
        "AgentVersion",
        foreign_keys=[default_version_id],
        viewonly=True
    )
    
    __table_args__ = (
        Index("idx_agent_tenant_id", "tenant_id"),
        Index("idx_agent_created_by", "created_by"),
        Index("idx_agent_active", "is_active"),
        Index("idx_agent_status", "status"),
    )


class AgentExecution(Base):
    """Track agent executions for monitoring and logging."""
    __tablename__ = "agent_executions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=False)
    
    # Phase 3: Track version and LLM provider
    agent_version_id = Column(String(36), ForeignKey("agent_versions.id"), nullable=True)
    llm_provider = Column(String(50), nullable=True)  # "openai", "anthropic", etc
    
    input_data = Column(JSON, nullable=False)
    output_data = Column(JSON)
    status = Column(String(50), nullable=False)  # "pending", "running", "completed", "failed"
    error_message = Column(Text)
    execution_time_ms = Column(Integer)
    
    # Phase 3: Track tools called
    tools_called = Column(JSON, default=[])  # [{"name": "http_request", "success": true, "duration_ms": 234}]
    
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    # Relationships
    agent = relationship("Agent", back_populates="executions")
    version = relationship("AgentVersion", back_populates="executions")
    
    __table_args__ = (
        Index("idx_execution_agent_id", "agent_id"),
        Index("idx_execution_status", "status"),
        Index("idx_execution_created_at", "created_at"),
        Index("idx_execution_version_id", "agent_version_id"),
        Index("idx_execution_llm_provider", "llm_provider"),
    )
