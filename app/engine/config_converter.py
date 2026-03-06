"""
Agent configuration converter - Adapts Phase 3 AgentConfig to AgentEngine format.

This module bridges Phase 3 dynamic configuration (AgentConfig Pydantic schema)
with AgentEngine execution (which expects Dict format).

Conversion Flow:
┌──────────────────────────┐
│  AgentConfig (Pydantic)  │
│  from AgentLoader        │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│  config_to_dict()        │
│  (Converter function)    │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│  Dict[str, Any]          │
│  for AgentEngine         │
└──────────────────────────┘
"""

from typing import Dict, Any, Optional
from app.agents import AgentConfig


def agent_config_to_dict(config: AgentConfig) -> Dict[str, Any]:
    """
    Convert AgentConfig (Pydantic schema) to dict format for AgentEngine.
    
    This adapter ensures compatibility between Phase 3 dynamic configuration
    and the AgentEngine execution engine.
    
    Args:
        config: AgentConfig (Pydantic model from AgentLoader)
        
    Returns:
        Dict[str, Any] with structure expected by AgentEngine.execute()
        
    Example:
        agent_config = await loader.load_agent(db, agent_id, tenant_id)
        engine_config = agent_config_to_dict(agent_config)
        result = await engine.execute(agent_config=engine_config, ...)
    """
    # Extract LLM configuration
    llm_config = config.llm_config
    
    # Extract tool names (only enabled tools)
    tools = [tool.name for tool in config.tools if tool.enabled]
    
    # Build final agent config dict
    engine_config = {
        # Identification
        "agent_id": config.agent_id,
        "version_number": config.version_number,
        
        # Prompts
        "system_prompt": config.system_prompt,  # Already assembled by AgentLoader
        "instruction_prompt": config.prompts.instruction,
        "context_prompt": config.prompts.context,
        "fallback_prompt": config.prompts.fallback,
        
        # LLM Configuration
        "llm_provider": llm_config.provider,
        "llm_model": llm_config.model,
        "temperature": llm_config.temperature,
        "max_tokens": llm_config.max_tokens,
        "top_p": llm_config.top_p,
        "frequency_penalty": llm_config.frequency_penalty or 0.0,
        "presence_penalty": llm_config.presence_penalty or 0.0,
        
        # Tools (enabled only)
        "tools": tools,
        "tool_configs": {
            tool.name: tool.config for tool in config.tools if tool.enabled
        },
        
        # Memory Configuration
        "memory_type": config.memory_config.type,
        "memory_max_history": config.memory_config.max_history,
        "memory_enable_vector": config.memory_config.enable_vector,
        "memory_vector_threshold": config.memory_config.vector_similarity_threshold,
    }
    
    return engine_config


def dict_to_agent_config_partial(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure dict config has all required fields (backward compatibility).
    
    This function is used for Phase 1/2 agents that don't use Phase 3 dynamic
    configuration. It ensures fields have defaults if missing.
    
    Args:
        config_dict: Dictionary with agent configuration
        
    Returns:
        Dict with all required fields populated with defaults if missing
    """
    # Set defaults for any missing fields
    return {
        "agent_id": config_dict.get("agent_id", ""),
        "system_prompt": config_dict.get("system_prompt", "You are helpful assistant."),
        "llm_provider": config_dict.get("llm_provider", "openai"),
        "llm_model": config_dict.get("llm_model", "gpt-4-turbo-preview"),
        "temperature": config_dict.get("temperature", 0.7),
        "max_tokens": config_dict.get("max_tokens", 2048),
        "top_p": config_dict.get("top_p", 1.0),
        "frequency_penalty": config_dict.get("frequency_penalty", 0.0),
        "presence_penalty": config_dict.get("presence_penalty", 0.0),
        "tools": config_dict.get("tools", []),
        "tool_configs": config_dict.get("tool_configs", {}),
        "memory_type": config_dict.get("memory_type", "conversation"),
        "memory_max_history": config_dict.get("memory_max_history", 10),
        "memory_enable_vector": config_dict.get("memory_enable_vector", False),
        "memory_vector_threshold": config_dict.get("memory_vector_threshold", None),
    }
