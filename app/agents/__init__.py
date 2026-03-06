"""
Agents module - Service layer for agent management.

This module implements the Service Layer for agent configuration and management.
Services are decoupled from the database and return Pydantic schemas instead of ORM models.
"""

from app.agents.agent_service import AgentService
from app.agents.agent_version_service import AgentVersionService
from app.agents.agent_tool_service import AgentToolService
from app.agents.agent_prompt_service import AgentPromptService
from app.agents.agent_loader import AgentLoader, get_agent_loader, load_agent_sync
from app.agents.schemas import (
    AgentResponse,
    CreateAgentRequest,
    UpdateAgentRequest,
    ListAgentsResponse,
    AgentVersionResponse,
    CreateVersionRequest,
    ListVersionsResponse,
    AgentToolResponse,
    AddToolRequest,
    UpdateToolConfigRequest,
    ListAgentToolsResponse,
    AgentPromptResponse,
    CreatePromptRequest,
    UpdatePromptRequest,
    ListAgentPromptsResponse,
    AgentLLMConfig,
    AgentToolConfigItem,
    AgentPromptConfigItem,
    AgentMemoryConfig,
    AgentConfig,
)

__all__ = [
    "AgentService",
    "AgentVersionService",
    "AgentToolService",
    "AgentPromptService",
    "AgentLoader",
    "get_agent_loader",
    "AgentResponse",
    "CreateAgentRequest",
    "UpdateAgentRequest",
    "ListAgentsResponse",
    "AgentVersionResponse",
    "CreateVersionRequest",
    "ListVersionsResponse",
    "AgentToolResponse",
    "AddToolRequest",
    "UpdateToolConfigRequest",
    "ListAgentToolsResponse",
    "AgentPromptResponse",
    "CreatePromptRequest",
    "UpdatePromptRequest",
    "ListAgentPromptsResponse",
    "AgentLLMConfig",
    "AgentToolConfigItem",
    "AgentPromptConfigItem",
    "AgentMemoryConfig",
    "AgentConfig",
]
