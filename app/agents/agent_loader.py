"""
Agent Loader Service - Orchestrates loading complete agent configurations from database.

This module bridges configuration stored in the database with the AgentEngine runtime.
It ensures all required components (versions, prompts, tools, LLM config) are loaded
and validated before being passed to the execution engine.

Responsibilities:
1. Load agent record with validation
2. Load active version
3. Load prompts per version
4. Load enabled tools per version
5. Assemble complete AgentConfig for execution
"""

import asyncio
import inspect
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.agent import Agent
from app.models.agent_platform import AgentVersion, AgentPrompt, AgentTool
from app.core.exceptions import (
    ResourceNotFoundError,
    ValidationError,
    ConflictError,
    PermissionDeniedError,
)
from app.tools.tool_registry import ToolRegistry  # Global tool registry
from app.agents.schemas import (
    AgentConfig,
    AgentLLMConfig,
    AgentToolConfigItem,
    AgentPromptConfigItem,
    AgentMemoryConfig,
)


class AgentLoader:
    """
    Orchestrator for loading complete agent configurations.
    
    The AgentLoader acts as the single point of truth for assembling all agent
    configuration from multiple database tables into a single AgentConfig object
    that can be passed directly to AgentEngine.
    
    Usage:
        loader = AgentLoader()
        agent_config = await loader.load_agent(db, agent_id, tenant_id)
        # agent_config is ready for AgentEngine.execute()
    """
    
    async def _execute(self, db: Any, stmt: Any) -> Any:
        """Execute SQL statement for sync or async SQLAlchemy sessions."""
        result = db.execute(stmt)
        if inspect.isawaitable(result):
            return await result
        return result

    async def load_agent(
        self,
        db: Any,
        agent_id: str,
        tenant_id: str,
    ) -> AgentConfig:
        """
        Load complete agent configuration from database.
        
        This is the main entry point for loading agents. It orchestrates loading
        all components (version, prompts, tools, LLM config) and validates them
        before returning the final AgentConfig object.
        
        Args:
            db: Async database session
            agent_id: ID of agent to load
            tenant_id: Tenant ID for multi-tenancy validation
            
        Returns:
            AgentConfig: Complete runtime configuration
            
        Raises:
            ResourceNotFoundError: Agent not found
            PermissionDeniedError: Agent belongs to different tenant
            ValidationError: Missing required configuration
            
        Example:
            config = await loader.load_agent(db, "agent_123", "tenant_456")
            agent = AgentEngine(config)
            result = await agent.execute("user query")
        """
        # Step 1: Load and validate agent record
        agent = await self._load_agent_record(db, agent_id, tenant_id)
        
        # Step 2: Load active version
        version = await self._load_agent_version(db, agent.id, tenant_id)
        
        # Step 3: Load prompts for version
        prompts = await self._load_agent_prompts(db, version.id)
        
        # Step 4: Load enabled tools for version
        tools = await self._load_agent_tools(db, version.id)
        
        # Step 5: Assemble final configuration
        agent_config = await self._assemble_agent_config(
            agent=agent,
            version=version,
            prompts=prompts,
            tools=tools,
        )
        
        return agent_config
    
    async def _load_agent_record(
        self,
        db: Any,
        agent_id: str,
        tenant_id: str,
    ) -> Agent:
        """
        Load and validate agent record from database.
        
        Ensures:
        1. Agent exists
        2. Agent belongs to the specified tenant
        3. Agent is not archived
        
        Args:
            db: Async database session
            agent_id: Agent ID
            tenant_id: Tenant ID for security check
            
        Returns:
            Agent: Agent record
            
        Raises:
            ResourceNotFoundError: Agent not found
            PermissionDeniedError: Agent belongs to different tenant
        """
        # Query with tenant safety
        stmt = select(Agent).where(
            Agent.id == agent_id,
            Agent.tenant_id == tenant_id,
        )
        result = await self._execute(db, stmt)
        agent = result.scalars().first()
        
        if not agent:
            raise ResourceNotFoundError(
                f"Agent {agent_id} not found for tenant {tenant_id}",
            )
        
        if str(agent.status) in ("archived", "AgentStatus.ARCHIVED"):
            raise ValidationError(
                f"Agent {agent_id} is archived and cannot be loaded",
            )
        
        return agent
    
    async def _load_agent_version(
        self,
        db: Any,
        agent_id: str,
        tenant_id: str,  # For future multi-tenant propagation
    ) -> AgentVersion:
        """
        Load active version for agent.
        
        Ensures exactly one active version exists. Versions track semantic
        versioning (1.0, 1.1, 2.0, etc) and can be rolled back.
        
        Args:
            db: Async database session
            agent_id: Agent ID
            tenant_id: Tenant ID
            
        Returns:
            AgentVersion: Active version record
            
        Raises:
            ValidationError: No active version found or multiple active versions
        """
        # Query active version
        stmt = select(AgentVersion).where(
            AgentVersion.agent_id == agent_id,
            AgentVersion.is_active == True,
        )
        result = await self._execute(db, stmt)
        versions = result.scalars().all()
        
        if not versions:
            raise ValidationError(
                f"No active version found for agent {agent_id}. "
                "Create and activate a version first.",
            )
        
        if len(versions) > 1:
            raise ConflictError(
                f"Multiple active versions found for agent {agent_id}. "
                "Database consistency error.",
            )
        
        return versions[0]
    
    async def _load_agent_prompts(
        self,
        db: Any,
        version_id: str,
    ) -> AgentPromptConfigItem:
        """
        Load all prompts for version and assemble into prompt config.
        
        Loads prompts by type (system, instruction, context, fallback).
        - System prompt is REQUIRED
        - Others are OPTIONAL (AgentEngine provides defaults if missing)
        
        Args:
            db: Async database session
            version_id: Agent version ID
            
        Returns:
            AgentPromptConfigItem: Complete prompt configuration
            
        Raises:
            ValidationError: System prompt missing
        """
        # Query all prompts for version
        stmt = select(AgentPrompt).where(
            AgentPrompt.agent_version_id == version_id,
        )
        result = await self._execute(db, stmt)
        prompts_list = result.scalars().all()
        
        # Organize by type
        prompts_by_type = {}
        for prompt in prompts_list:
            prompt_type = prompt.prompt_type.value if hasattr(prompt.prompt_type, "value") else str(prompt.prompt_type)
            prompts_by_type[prompt_type] = prompt.prompt_content
        
        # Validate system prompt exists
        if "system" not in prompts_by_type:
            raise ValidationError(
                f"System prompt is required for version {version_id}. "
                "Create a system prompt before using this version.",
            )
        
        # Build config object with optional defaults
        return AgentPromptConfigItem(
            system=prompts_by_type["system"],
            instruction=prompts_by_type.get("instruction"),
            context=prompts_by_type.get("context"),
            fallback=prompts_by_type.get("fallback"),
        )
    
    async def _load_agent_tools(
        self,
        db: Any,
        version_id: str,
    ) -> list[AgentToolConfigItem]:
        """
        Load enabled tools for version with validation.
        
        Ensures:
        1. Each tool exists in global ToolRegistry (validates after deployment)
        2. Only enabled tools are returned
        3. Per-tool configuration is included
        
        Args:
            db: Async database session
            version_id: Agent version ID
            
        Returns:
            list[AgentToolConfigItem]: List of enabled tool configurations
            
        Raises:
            ValidationError: Tool exists in DB but not in ToolRegistry
        """
        # Query enabled tools for version
        stmt = select(AgentTool).where(
            AgentTool.agent_version_id == version_id,
            AgentTool.enabled == True,
        )
        result = await self._execute(db, stmt)
        tools_db = result.scalars().all()
        
        # Validate each tool against ToolRegistry
        tools_configs = []
        
        for tool_db in tools_db:
            # Cross-check against registry
            if not ToolRegistry.get_tool(tool_db.tool_name):
                raise ValidationError(
                    f"Tool '{tool_db.tool_name}' in version {version_id} is not in ToolRegistry. "
                    "Tool may have been removed from system.",
                )
            
            # Build config item with DB config
            tool_config = AgentToolConfigItem(
                name=tool_db.tool_name,
                enabled=True,
                config=tool_db.tool_config or {},
            )
            tools_configs.append(tool_config)
        
        return tools_configs
    
    async def _assemble_agent_config(
        self,
        agent: Agent,
        version: AgentVersion,
        prompts: AgentPromptConfigItem,
        tools: list[AgentToolConfigItem],
    ) -> AgentConfig:
        """
        Assemble complete AgentConfig from loaded components.
        
        This method:
        1. Extracts LLM config from version.configuration JSON
        2. Extracts memory config from version.configuration JSON
        3. Assembles final system prompt from templates
        4. Combines all into single AgentConfig object
        
        Args:
            agent: Agent record
            version: AgentVersion record
            prompts: AgentPromptConfigItem with all prompts
            tools: List[AgentToolConfigItem] with tool configs
            
        Returns:
            AgentConfig: Complete ready-to-use configuration
            
        Raises:
            ValidationError: Missing required LLM config
        """
        # Parse configuration JSON from version
        version_config = version.configuration or {}
        
        # Extract and validate LLM config
        llm_config_data = version_config.get("llm_config")
        if not llm_config_data:
            raise ValidationError(
                f"LLM configuration missing in version {version.id}. "
                "Add 'llm_config' to version configuration.",
            )
        
        llm_config = AgentLLMConfig(**llm_config_data)
        
        # Extract memory config (with defaults if missing)
        memory_config_data = version_config.get("memory_config", {})
        memory_config = AgentMemoryConfig(**memory_config_data)
        
        # Assemble final system prompt from templates
        # Format: [SYSTEM]\n{system}\n\n[INSTRUCTIONS]\n{instruction}\n\n...
        system_prompt_parts = [f"[SYSTEM]\n{prompts.system}"]
        
        if prompts.instruction:
            system_prompt_parts.append(f"[INSTRUCTIONS]\n{prompts.instruction}")
        
        if prompts.context:
            system_prompt_parts.append(f"[CONTEXT]\n{prompts.context}")
        
        final_system_prompt = "\n\n".join(system_prompt_parts)
        
        # Assemble final AgentConfig
        agent_config = AgentConfig(
            agent_id=agent.id,
            version_number=version.version,
            system_prompt=final_system_prompt,
            prompts=prompts,
            llm_config=llm_config,
            tools=tools,
            memory_config=memory_config,
        )
        
        return agent_config


# Singleton instance for use across application
_loader_instance: Optional[AgentLoader] = None


def get_agent_loader() -> AgentLoader:
    """
    Get singleton instance of AgentLoader.
    
    Usage in routes:
        loader = get_agent_loader()
        config = await loader.load_agent(db, agent_id, tenant_id)
    
    Returns:
        AgentLoader: Singleton instance
    """
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = AgentLoader()
    return _loader_instance


def load_agent_sync(
    db,  # AsyncSession or Session (sqlalchemy)
    agent_id: str,
    tenant_id: str,
) -> Optional[AgentConfig]:
    """
    Load agent configuration from sync context (like Celery workers).
    
    This is a wrapper around the async load_agent() method that can be called
    from synchronous code (Celery tasks, sync routes, etc).
    
    For use in Celery workers:
        # In sync Celery task
        config = load_agent_sync(db, agent_id, tenant_id)
        if config:
            result = await engine.execute(agent_config=config, ...)
    
    Args:
        db: Database session (AsyncSession)
        agent_id: Agent ID to load
        tenant_id: Tenant ID for security
        
    Returns:
        AgentConfig if exists and valid, None if not Phase 3 agent
        
    Raises:
        ResourceNotFoundError: Agent not found
        PermissionDeniedError: Cross-tenant access attempt
        ValidationError: Config validation failed
        ConflictError: Data inconsistency
    """
    try:
        # Attempt to run async code from sync context using asyncio
        # This works in Celery workers and other thread pool executors
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loader = get_agent_loader()
            config = loop.run_until_complete(
                loader.load_agent(db, agent_id, tenant_id)
            )
            return config
        finally:
            loop.close()
    except ResourceNotFoundError:
        # Re-raise these specific exceptions
        raise
    except PermissionDeniedError:
        raise
    except ValidationError:
        raise
    except ConflictError:
        raise
    except Exception as e:
        # If any other error occurs, return None (not a Phase 3 agent)
        return None
