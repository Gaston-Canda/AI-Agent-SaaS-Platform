"""
Pydantic schemas for agent operations.

These schemas define the request/response contracts for the Agent API.
Services return these schemas instead of ORM models, providing a clean
separation between database and business logic layers.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class AgentResponse(BaseModel):
    """Response schema for an agent."""
    id: str = Field(..., description="Agent ID")
    tenant_id: str = Field(..., description="Tenant ID")
    name: str = Field(..., description="Agent name")
    description: Optional[str] = Field(None, description="Agent description")
    agent_type: str = Field(..., description="Agent type (chat, task, automation)")
    status: str = Field(..., description="Agent status (draft, active, archived)")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        """Pydantic config."""
        orm_mode = True
        schema_extra = {
            "example": {
                "id": "agent_123abc",
                "tenant_id": "tenant_456def",
                "name": "Support Bot",
                "description": "Customer support agent",
                "agent_type": "chat",
                "status": "active",
                "created_at": "2024-03-05T10:00:00",
                "updated_at": "2024-03-05T10:00:00",
            }
        }


class CreateAgentRequest(BaseModel):
    """Request schema for creating an agent."""
    name: str = Field(..., min_length=1, max_length=255, description="Agent name")
    description: Optional[str] = Field(None, max_length=1000, description="Agent description")
    agent_type: str = Field(default="chat", description="Agent type")
    
    class Config:
        schema_extra = {
            "example": {
                "name": "Support Bot",
                "description": "Customer support agent",
                "agent_type": "chat",
            }
        }


class UpdateAgentRequest(BaseModel):
    """Request schema for updating an agent."""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Agent name")
    description: Optional[str] = Field(None, max_length=1000, description="Agent description")
    agent_type: Optional[str] = Field(None, description="Agent type")
    status: Optional[str] = Field(None, description="Agent status")
    
    class Config:
        schema_extra = {
            "example": {
                "name": "Updated Support Bot",
                "description": "Updated description",
            }
        }


class ListAgentsResponse(BaseModel):
    """Response schema for listing agents."""
    items: list[AgentResponse] = Field(..., description="List of agents")
    total: int = Field(..., description="Total count of agents")
    skip: int = Field(..., description="Number of records skipped")
    limit: int = Field(..., description="Number of records returned")
    
    class Config:
        schema_extra = {
            "example": {
                "items": [
                    {
                        "id": "agent_123abc",
                        "tenant_id": "tenant_456def",
                        "name": "Support Bot",
                        "description": "Customer support agent",
                        "agent_type": "chat",
                        "status": "active",
                        "created_at": "2024-03-05T10:00:00",
                        "updated_at": "2024-03-05T10:00:00",
                    }
                ],
                "total": 1,
                "skip": 0,
                "limit": 50,
            }
        }


class AgentVersionResponse(BaseModel):
    """Response schema for an agent version."""
    id: str = Field(..., description="Version ID")
    agent_id: str = Field(..., description="Agent ID")
    version: str = Field(..., description="Version number (e.g., 1.0, 1.1, 2.0)")
    is_active: bool = Field(..., description="Whether this is the active version")
    system_prompt: str = Field(..., description="System prompt for this version")
    configuration: dict = Field(default={}, description="Configuration JSON (llm_provider, model, temperature, etc)")
    created_by: str = Field(..., description="User ID who created this version")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    class Config:
        """Pydantic config."""
        orm_mode = True
        schema_extra = {
            "example": {
                "id": "version_123abc",
                "agent_id": "agent_456def",
                "version": "1.0",
                "is_active": True,
                "system_prompt": "You are a helpful customer support agent.",
                "configuration": {
                    "llm_provider": "openai",
                    "llm_model": "gpt-4-turbo-preview",
                    "temperature": 0.7,
                    "max_tokens": 2048,
                },
                "created_by": "user_789ghi",
                "created_at": "2024-03-05T10:00:00",
            }
        }


class CreateVersionRequest(BaseModel):
    """Request schema for creating a new version."""
    system_prompt: str = Field(..., min_length=1, max_length=5000, description="System prompt")
    configuration: dict = Field(default={}, description="Configuration JSON")
    
    class Config:
        schema_extra = {
            "example": {
                "system_prompt": "You are a helpful customer support agent.",
                "configuration": {
                    "llm_provider": "openai",
                    "llm_model": "gpt-4-turbo-preview",
                    "temperature": 0.7,
                    "max_tokens": 2048,
                }
            }
        }


class ListVersionsResponse(BaseModel):
    """Response schema for listing versions."""
    items: list[AgentVersionResponse] = Field(..., description="List of versions")
    total: int = Field(..., description="Total count of versions")
    
    class Config:
        schema_extra = {
            "example": {
                "items": [
                    {
                        "id": "version_123abc",
                        "agent_id": "agent_456def",
                        "version": "1.1",
                        "is_active": True,
                        "system_prompt": "You are a helpful customer support agent (updated).",
                        "configuration": {},
                        "created_by": "user_789ghi",
                        "created_at": "2024-03-05T11:00:00",
                    },
                    {
                        "id": "version_789ghi",
                        "agent_id": "agent_456def",
                        "version": "1.0",
                        "is_active": False,
                        "system_prompt": "You are a helpful customer support agent.",
                        "configuration": {},
                        "created_by": "user_789ghi",
                        "created_at": "2024-03-05T10:00:00",
                    }
                ],
                "total": 2,
            }
        }


class AgentToolResponse(BaseModel):
    """Response schema for an agent tool assignment."""
    id: str = Field(..., description="Tool assignment ID")
    agent_version_id: str = Field(..., description="Version this tool belongs to")
    tool_name: str = Field(..., description="Name of the tool")
    enabled: bool = Field(..., description="Whether this tool is enabled")
    tool_config: dict = Field(default={}, description="Tool-specific configuration")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        """Pydantic config."""
        orm_mode = True
        schema_extra = {
            "example": {
                "id": "tool_123abc",
                "agent_version_id": "version_456def",
                "tool_name": "google_search",
                "enabled": True,
                "tool_config": {
                    "timeout": 30,
                    "max_results": 5,
                },
                "created_at": "2024-03-05T10:00:00",
                "updated_at": "2024-03-05T10:00:00",
            }
        }


class AddToolRequest(BaseModel):
    """Request schema for adding a tool to a version."""
    tool_name: str = Field(..., min_length=1, max_length=100, description="Tool name (must exist in ToolRegistry)")
    tool_config: dict = Field(default={}, description="Tool-specific configuration")
    
    class Config:
        schema_extra = {
            "example": {
                "tool_name": "google_search",
                "tool_config": {
                    "timeout": 30,
                    "max_results": 5,
                }
            }
        }


class UpdateToolConfigRequest(BaseModel):
    """Request schema for updating tool configuration."""
    tool_config: dict = Field(default={}, description="Updated tool configuration")
    
    class Config:
        schema_extra = {
            "example": {
                "tool_config": {
                    "timeout": 60,
                    "max_results": 10,
                }
            }
        }


class ListAgentToolsResponse(BaseModel):
    """Response schema for listing tools of a version."""
    items: list[AgentToolResponse] = Field(..., description="List of tools")
    total: int = Field(..., description="Total count of tools")
    enabled_count: int = Field(..., description="Count of enabled tools")
    
    class Config:
        schema_extra = {
            "example": {
                "items": [
                    {
                        "id": "tool_123abc",
                        "agent_version_id": "version_456def",
                        "tool_name": "google_search",
                        "enabled": True,
                        "tool_config": {"timeout": 30},
                        "created_at": "2024-03-05T10:00:00",
                        "updated_at": "2024-03-05T10:00:00",
                    },
                    {
                        "id": "tool_789ghi",
                        "agent_version_id": "version_456def",
                        "tool_name": "calculator",
                        "enabled": False,
                        "tool_config": {},
                        "created_at": "2024-03-05T10:05:00",
                        "updated_at": "2024-03-05T10:05:00",
                    }
                ],
                "total": 2,
                "enabled_count": 1,
            }
        }


class AgentPromptResponse(BaseModel):
    """Response schema for an agent prompt."""
    id: str = Field(..., description="Prompt ID")
    agent_version_id: str = Field(..., description="Version this prompt belongs to")
    prompt_type: str = Field(..., description="Type of prompt (system|instruction|context|fallback)")
    prompt_content: str = Field(..., description="The prompt text content")
    created_by: str = Field(..., description="User who created this prompt")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        """Pydantic config."""
        orm_mode = True
        schema_extra = {
            "example": {
                "id": "prompt_123abc",
                "agent_version_id": "version_456def",
                "prompt_type": "system",
                "prompt_content": "You are a helpful customer support agent. Always be polite and professional.",
                "created_by": "user_789ghi",
                "created_at": "2024-03-05T10:00:00",
                "updated_at": "2024-03-05T10:00:00",
            }
        }


class CreatePromptRequest(BaseModel):
    """Request schema for creating a prompt."""
    prompt_type: str = Field(..., min_length=1, max_length=50, description="Prompt type (system|instruction|context|fallback)")
    prompt_content: str = Field(..., min_length=1, max_length=5000, description="Prompt content")
    
    class Config:
        schema_extra = {
            "example": {
                "prompt_type": "system",
                "prompt_content": "You are a helpful customer support agent. Always be polite and professional.",
            }
        }


class UpdatePromptRequest(BaseModel):
    """Request schema for updating a prompt."""
    prompt_content: str = Field(..., min_length=1, max_length=5000, description="Updated prompt content")
    
    class Config:
        schema_extra = {
            "example": {
                "prompt_content": "You are a helpful and experienced customer support agent. Always be polite, professional, and provide accurate information.",
            }
        }


class ListAgentPromptsResponse(BaseModel):
    """Response schema for listing prompts."""
    items: list[AgentPromptResponse] = Field(..., description="List of prompts")
    total: int = Field(..., description="Total count of prompts")
    
    class Config:
        schema_extra = {
            "example": {
                "items": [
                    {
                        "id": "prompt_123abc",
                        "agent_version_id": "version_456def",
                        "prompt_type": "system",
                        "prompt_content": "You are a helpful customer support agent.",
                        "created_by": "user_789ghi",
                        "created_at": "2024-03-05T10:00:00",
                        "updated_at": "2024-03-05T10:00:00",
                    },
                    {
                        "id": "prompt_789ghi",
                        "agent_version_id": "version_456def",
                        "prompt_type": "instruction",
                        "prompt_content": "Be brief and concise. Respond in maximum 2 paragraphs.",
                        "created_by": "user_789ghi",
                        "created_at": "2024-03-05T10:05:00",
                        "updated_at": "2024-03-05T10:05:00",
                    }
                ],
                "total": 2,
            }
        }


class AgentLLMConfig(BaseModel):
    """LLM configuration for agent execution."""
    provider: str = Field(..., description="LLM provider (openai, anthropic, etc)")
    model: str = Field(..., description="Model name (gpt-4, claude-3, etc)")
    temperature: float = Field(default=0.7, description="Temperature (0.0-2.0)")
    max_tokens: Optional[int] = Field(None, description="Max tokens per response")
    top_p: Optional[float] = Field(None, description="Top-p sampling")
    frequency_penalty: Optional[float] = Field(None, description="Frequency penalty")
    presence_penalty: Optional[float] = Field(None, description="Presence penalty")
    
    class Config:
        """Pydantic config."""
        schema_extra = {
            "example": {
                "provider": "openai",
                "model": "gpt-4-turbo-preview",
                "temperature": 0.7,
                "max_tokens": 2048,
                "top_p": 1.0,
            }
        }


class AgentToolConfigItem(BaseModel):
    """Tool configuration for agent execution."""
    name: str = Field(..., description="Tool name")
    enabled: bool = Field(..., description="Is tool enabled?")
    config: dict = Field(default_factory=dict, description="Tool-specific configuration")
    
    class Config:
        """Pydantic config."""
        schema_extra = {
            "example": {
                "name": "google_search",
                "enabled": True,
                "config": {
                    "timeout": 30,
                    "max_results": 5,
                }
            }
        }


class AgentPromptConfigItem(BaseModel):
    """Prompt configuration for agent execution."""
    system: str = Field(..., description="System prompt (required)")
    instruction: Optional[str] = Field(None, description="Instruction prompt (optional)")
    context: Optional[str] = Field(None, description="Context prompt (optional)")
    fallback: Optional[str] = Field(None, description="Fallback response (optional)")
    
    class Config:
        """Pydantic config."""
        schema_extra = {
            "example": {
                "system": "You are a helpful customer support agent.",
                "instruction": "Be brief. Maximum 2 paragraphs per response.",
                "context": "Company was founded in 2020...",
                "fallback": "I apologize, I cannot help with that request.",
            }
        }


class AgentMemoryConfig(BaseModel):
    """Memory configuration for agent execution."""
    type: str = Field(default="conversation", description="Memory type")
    max_history: int = Field(default=10, description="Max conversation history")
    enable_vector: bool = Field(default=False, description="Enable vector memory?")
    vector_similarity_threshold: Optional[float] = Field(None, description="Vector similarity threshold")
    
    class Config:
        """Pydantic config."""
        schema_extra = {
            "example": {
                "type": "conversation",
                "max_history": 10,
                "enable_vector": False,
            }
        }


class AgentConfig(BaseModel):
    """Complete runtime configuration for agent execution."""
    agent_id: str = Field(..., description="Agent ID")
    version_number: str = Field(..., description="Version number (e.g., 1.0, 1.1)")
    system_prompt: str = Field(..., description="Assembled system prompt (final)")
    prompts: AgentPromptConfigItem = Field(..., description="Individual prompts")
    llm_config: AgentLLMConfig = Field(..., description="LLM configuration")
    tools: list[AgentToolConfigItem] = Field(default_factory=list, description="Available tools")
    memory_config: AgentMemoryConfig = Field(default_factory=AgentMemoryConfig, description="Memory configuration")
    
    class Config:
        """Pydantic config."""
        schema_extra = {
            "example": {
                "agent_id": "agent_123abc",
                "version_number": "1.1",
                "system_prompt": "[SYSTEM]\nYou are a helpful customer support agent.\n\n[INSTRUCTIONS]\nBe brief. Maximum 2 paragraphs.",
                "prompts": {
                    "system": "You are a helpful customer support agent.",
                    "instruction": "Be brief. Maximum 2 paragraphs.",
                    "context": "Company founded in 2020...",
                    "fallback": "I apologize...",
                },
                "llm_config": {
                    "provider": "openai",
                    "model": "gpt-4-turbo-preview",
                    "temperature": 0.7,
                    "max_tokens": 2048,
                },
                "tools": [
                    {
                        "name": "google_search",
                        "enabled": True,
                        "config": {"timeout": 30},
                    }
                ],
                "memory_config": {
                    "type": "conversation",
                    "max_history": 10,
                    "enable_vector": False,
                }
            }
        }
