"""
Agent Platform models for Phase 3.

This module contains models for the agent configuration system:
- AgentVersion: Version history and configuration
- AgentTool: Tool management per agent
- AgentPrompt: Prompt templates and configuration

These models enable users to create, configure, and manage custom agents
without writing code.
"""

from sqlalchemy import (
    Column, String, Text, DateTime, ForeignKey, Index, JSON, Boolean, 
    Integer, Float, Enum as SQLEnum, ForeignKeyConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

from app.db.database import Base


class PromptType(str, enum.Enum):
    """Types of prompts in an agent."""
    SYSTEM = "system"
    INSTRUCTION = "instruction"
    CONTEXT = "context"
    FALLBACK = "fallback"


class AgentStatus(str, enum.Enum):
    """Status of an agent."""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class AgentVersion(Base):
    """
    Version history for agents.
    
    Each agent can have multiple versions. When configuration changes,
    a new version is created. This enables:
    - Version rollback
    - A/B testing of configurations
    - Full audit trail
    - Agent evolution tracking
    """
    __tablename__ = "agent_versions"
    
    # Primary Key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Foreign Keys
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=False)
    
    # Version Info
    version = Column(String(20), nullable=False)  # e.g., "1.0", "1.1", "2.0"
    is_active = Column(Boolean, default=False, nullable=False)  # Current active version
    
    # Configuration
    system_prompt = Column(Text, nullable=False)
    configuration = Column(JSON, default={})  # {
    #   "llm_provider": "openai",
    #   "llm_model": "gpt-4-turbo-preview",
    #   "temperature": 0.7,
    #   "max_tokens": 2048,
    #   "top_p": 1.0,
    #   "frequency_penalty": 0.0,
    #   "presence_penalty": 0.0,
    #   "memory_config": {
    #       "enable_conversation": true,
    #       "history_limit": 10
    #   }
    # }
    
    # Metadata
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    agent = relationship("Agent", back_populates="versions", foreign_keys=[agent_id])
    creator = relationship("User")
    tools = relationship("AgentTool", back_populates="version", cascade="all, delete-orphan")
    prompts = relationship("AgentPrompt", back_populates="version", cascade="all, delete-orphan")
    executions = relationship("AgentExecution", back_populates="version")
    
    __table_args__ = (
        Index("idx_agent_version_agent_id", "agent_id"),
        Index("idx_agent_version_is_active", "agent_id", "is_active"),
        Index("idx_agent_version_created_at", "created_at"),
    )
    
    def __repr__(self) -> str:
        return f"<AgentVersion(agent_id={self.agent_id}, version={self.version}, active={self.is_active})>"


class AgentTool(Base):
    """
    Tool configuration per agent version.
    
    Links agents to tools with configuration per tool.
    Enables:
    - Tool enable/disable per agent
    - Tool configuration (timeout, limits, etc)
    - Security (only allowed tools per agent)
    - Tool audit trail (which versions use which tools)
    """
    __tablename__ = "agent_tools"
    
    # Primary Key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Foreign Keys
    agent_version_id = Column(String(36), ForeignKey("agent_versions.id"), nullable=False)
    
    # Tool Configuration
    tool_name = Column(String(100), nullable=False)  # e.g., "http_request", "calculator", "database_query"
    enabled = Column(Boolean, default=True, nullable=False)
    tool_config = Column(JSON, default={})  # Tool-specific configuration, e.g., {
    #   "http_request": {
    #       "timeout_seconds": 30,
    #       "max_size_mb": 5,
    #       "allowed_domains": ["api.example.com"]
    #   },
    #   "database_query": {
    #       "max_rows": 100,
    #       "readonly": true
    #   }
    # }
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    version = relationship("AgentVersion", back_populates="tools")
    
    __table_args__ = (
        Index("idx_agent_tool_version_id", "agent_version_id"),
        Index("idx_agent_tool_name", "agent_version_id", "tool_name"),
        Index("idx_agent_tool_enabled", "agent_version_id", "enabled"),
    )
    
    def __repr__(self) -> str:
        return f"<AgentTool(version_id={self.agent_version_id}, name={self.tool_name}, enabled={self.enabled})>"


class AgentPrompt(Base):
    """
    Prompt templates per agent version.
    
    Stores different types of prompts:
    - system: Base system prompt
    - instruction: Behavior instructions
    - context: Background context
    - fallback: Fallback response
    
    Enables:
    - Modular prompt management
    - Easy prompt updates
    - Dynamic prompt assembly
    - Prompt A/B testing
    """
    __tablename__ = "agent_prompts"
    
    # Primary Key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Foreign Keys
    agent_version_id = Column(String(36), ForeignKey("agent_versions.id"), nullable=False)
    
    # Prompt Configuration
    prompt_type = Column(SQLEnum(PromptType), nullable=False)
    prompt_content = Column(Text, nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    version = relationship("AgentVersion", back_populates="prompts")
    
    __table_args__ = (
        Index("idx_agent_prompt_version_id", "agent_version_id"),
        Index("idx_agent_prompt_type", "agent_version_id", "prompt_type"),
    )
    
    def __repr__(self) -> str:
        return f"<AgentPrompt(version_id={self.agent_version_id}, type={self.prompt_type})>"


# Extensions to existing models for Phase 3

def extend_agent_model():
    """
    This documents the extensions needed to the Agent model.
    
    In the existing Agent model, add:
    
    # New columns
    default_version_id = Column(String(36), ForeignKey("agent_versions.id"), nullable=True)
    status = Column(SQLEnum(AgentStatus), default=AgentStatus.DRAFT, nullable=False)
    
    # New relationships
    versions = relationship(
        "AgentVersion",
        back_populates="agent",
        cascade="all, delete-orphan",
        primaryjoin="Agent.id == AgentVersion.agent_id"
    )
    default_version = relationship(
        "AgentVersion",
        foreign_keys=[default_version_id],
        viewonly=True
    )
    """
    pass


def extend_agent_execution_model():
    """
    This documents the extensions needed to the AgentExecution model.
    
    In the existing AgentExecution model, add:
    
    # New columns
    agent_version_id = Column(String(36), ForeignKey("agent_versions.id"), nullable=True)
    llm_provider = Column(String(50), nullable=True)  # "openai", "anthropic", etc
    tools_called = Column(JSON, default=[])  # [{"name": "http_request", "success": true, "duration_ms": 234}]
    
    # New relationships
    version = relationship("AgentVersion", back_populates="executions")
    """
    pass


def extend_execution_log_model():
    """
    This documents the extensions needed to the ExecutionLog model.
    
    In the existing ExecutionLog model, add:
    
    # New columns for token tracking
    prompt_tokens = Column(Integer, default=0, nullable=False)
    completion_tokens = Column(Integer, default=0, nullable=False)
    cost_usd = Column(Float, default=0.0, nullable=False)
    llm_provider = Column(String(50), nullable=True)  # "openai", "anthropic"
    
    # Add index for cost tracking
    Index("idx_execution_log_cost", "execution_id", "cost_usd")
    """
    pass
