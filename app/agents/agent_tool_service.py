"""
AgentToolService - Service layer for agent tool management.

This service handles all tool configuration operations with emphasis on:
- Validating tools against global ToolRegistry
- Returning Pydantic schemas instead of ORM models
- Database session dependency injection
- Tenant isolation (all queries filter by tenant_id)
- NEVER executing tools (only managing configuration)

Tool execution is handled by AgentEngine separately.
"""

from typing import List, Optional
from datetime import datetime
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import Agent
from app.models.agent_platform import AgentVersion, AgentTool
from app.agents.schemas import (
    AgentToolResponse,
    ListAgentToolsResponse,
)
from app.tools.tool_registry import ToolRegistry
from app.core.exceptions import NotFoundError, ValidationError, ForbiddenError


class AgentToolService:
    """
    Service for Agent Tool configuration management.
    
    Responsibilities:
    - Assign tools to agent versions
    - Enable/disable tools
    - Configure tools (per-tool settings)
    - Retrieve tool configuration
    - Validate against ToolRegistry
    
    Does NOT handle:
    - Tool execution
    - Tool parameter validation (AgentEngine does this)
    - Memory management
    - Tool discovery (ToolRegistry handles this)
    """
    
    def _validate_version_exists(
        self,
        db: Session,
        tenant_id: str,
        agent_id: str,
        version_id: str,
    ) -> AgentVersion:
        """
        Validate that version exists and belongs to tenant's agent.
        
        Args:
            db: Database session
            tenant_id: Tenant ID
            agent_id: Agent ID
            version_id: Version ID
            
        Returns:
            AgentVersion object if valid
            
        Raises:
            ForbiddenError: If version not found or doesn't belong to agent
        """
        # Query with multi-tenant safety check
        version = db.query(AgentVersion).join(Agent).filter(
            Agent.tenant_id == tenant_id,
            Agent.id == agent_id,
            AgentVersion.id == version_id,
            AgentVersion.agent_id == agent_id,
        ).first()
        
        if not version:
            raise ForbiddenError("Version not found or does not belong to this tenant")
        
        return version
    
    def _tool_exists_in_registry(self, tool_name: str) -> bool:
        """
        Check if tool exists in global ToolRegistry.
        
        Args:
            tool_name: Tool name to check
            
        Returns:
            True if tool exists, False otherwise
        """
        return ToolRegistry.get_tool(tool_name) is not None
    
    async def add_tool_to_version(
        self,
        db: Session,
        tenant_id: str,
        agent_id: str,
        version_id: str,
        tool_name: str,
        tool_config: Optional[dict] = None,
    ) -> AgentToolResponse:
        """
        Assign a tool to an agent version.
        
        Validates that tool exists in global ToolRegistry before assignment.
        Tools are created in ENABLED state by default.
        
        Args:
            db: Database session (injected)
            tenant_id: Tenant ID
            agent_id: Agent ID
            version_id: Version ID
            tool_name: Name of tool from ToolRegistry
            tool_config: Optional tool-specific configuration
        
        Returns:
            AgentToolResponse: Newly assigned tool
            
        Raises:
            ForbiddenError: If version not accessible
            ValidationError: If tool not found in ToolRegistry or already assigned
            
        Write operation: Explicit commit and refresh.
        """
        # Validate version exists
        version = self._validate_version_exists(db, tenant_id, agent_id, version_id)
        
        # Validate tool_name is provided
        if not tool_name or not tool_name.strip():
            raise ValidationError("Tool name cannot be empty")
        
        tool_name = tool_name.strip()
        
        # CRITICAL: Validate tool exists in ToolRegistry
        if not self._tool_exists_in_registry(tool_name):
            raise ValidationError(
                f"Tool '{tool_name}' not found in ToolRegistry. "
                f"Available tools: {', '.join(ToolRegistry.list_tools())}"
            )
        
        # Check if tool already assigned to this version
        existing = db.query(AgentTool).filter(
            AgentTool.agent_version_id == version_id,
            AgentTool.tool_name == tool_name,
        ).first()
        
        if existing:
            raise ValidationError(
                f"Tool '{tool_name}' is already assigned to this version"
            )
        
        # Create new tool assignment (enabled by default)
        agent_tool = AgentTool(
            id=str(uuid.uuid4()),
            agent_version_id=version_id,
            tool_name=tool_name,
            enabled=True,  # New tools are enabled by default
            tool_config=tool_config or {},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        # Write operation: explicit commit and refresh
        db.add(agent_tool)
        db.commit()
        db.refresh(agent_tool)
        
        # Return Pydantic schema, not ORM model
        return AgentToolResponse.from_orm(agent_tool)
    
    async def remove_tool_from_version(
        self,
        db: Session,
        tenant_id: str,
        agent_id: str,
        version_id: str,
        tool_name: str,
    ) -> None:
        """
        Remove (unassign) a tool from an agent version.
        
        Hard delete of the tool assignment. Tool is completely removed,
        not disabled. To temporarily disable without removing, use enable_tool().
        
        Args:
            db: Database session (injected)
            tenant_id: Tenant ID
            agent_id: Agent ID
            version_id: Version ID
            tool_name: Tool name to remove
        
        Raises:
            ForbiddenError: If version not accessible
            NotFoundError: If tool not assigned to version
            
        Write operation: Explicit commit.
        """
        # Validate version exists
        self._validate_version_exists(db, tenant_id, agent_id, version_id)
        
        # Find and delete tool assignment
        tool = db.query(AgentTool).filter(
            AgentTool.agent_version_id == version_id,
            AgentTool.tool_name == tool_name,
        ).first()
        
        if not tool:
            raise NotFoundError(
                f"Tool '{tool_name}' is not assigned to this version"
            )
        
        # Hard delete (no soft delete for tool assignments)
        db.delete(tool)
        
        # Write operation: explicit commit (no refresh needed since we deleted)
        db.commit()
    
    async def enable_tool(
        self,
        db: Session,
        tenant_id: str,
        agent_id: str,
        version_id: str,
        tool_name: str,
        enabled: bool = True,
    ) -> AgentToolResponse:
        """
        Enable or disable a tool for an agent version.
        
        Allows temporarily disabling a tool without removing it.
        Use when a tool is causing issues but might be re-enabled later.
        
        Args:
            db: Database session (injected)
            tenant_id: Tenant ID
            agent_id: Agent ID
            version_id: Version ID
            tool_name: Tool to enable/disable
            enabled: True to enable, False to disable
        
        Returns:
            AgentToolResponse: Updated tool status
            
        Raises:
            ForbiddenError: If version not accessible
            NotFoundError: If tool not assigned to version
            
        Write operation: Explicit commit and refresh.
        """
        # Validate version exists
        self._validate_version_exists(db, tenant_id, agent_id, version_id)
        
        # Find tool assignment
        tool = db.query(AgentTool).filter(
            AgentTool.agent_version_id == version_id,
            AgentTool.tool_name == tool_name,
        ).first()
        
        if not tool:
            raise NotFoundError(
                f"Tool '{tool_name}' is not assigned to this version"
            )
        
        # Update enabled status
        tool.enabled = enabled
        tool.updated_at = datetime.utcnow()
        
        # Write operation: explicit commit and refresh
        db.commit()
        db.refresh(tool)
        
        # Return Pydantic schema
        return AgentToolResponse.from_orm(tool)
    
    async def update_tool_config(
        self,
        db: Session,
        tenant_id: str,
        agent_id: str,
        version_id: str,
        tool_name: str,
        tool_config: dict,
    ) -> AgentToolResponse:
        """
        Update configuration for a tool assignment.
        
        Updates tool-specific configuration without validating parameters.
        The AgentEngine is responsible for validating configuration during execution.
        
        Args:
            db: Database session (injected)
            tenant_id: Tenant ID
            agent_id: Agent ID
            version_id: Version ID
            tool_name: Tool to configure
            tool_config: Updated configuration dict
        
        Returns:
            AgentToolResponse: Updated tool configuration
            
        Raises:
            ForbiddenError: If version not accessible
            NotFoundError: If tool not assigned to version
            
        Write operation: Explicit commit and refresh.
        """
        # Validate version exists
        self._validate_version_exists(db, tenant_id, agent_id, version_id)
        
        # Find tool assignment
        tool = db.query(AgentTool).filter(
            AgentTool.agent_version_id == version_id,
            AgentTool.tool_name == tool_name,
        ).first()
        
        if not tool:
            raise NotFoundError(
                f"Tool '{tool_name}' is not assigned to this version"
            )
        
        # Update configuration (can be empty dict)
        tool.tool_config = tool_config or {}
        tool.updated_at = datetime.utcnow()
        
        # Write operation: explicit commit and refresh
        db.commit()
        db.refresh(tool)
        
        # Return Pydantic schema
        return AgentToolResponse.from_orm(tool)
    
    async def get_tools_for_version(
        self,
        db: Session,
        tenant_id: str,
        agent_id: str,
        version_id: str,
        enabled_only: bool = False,
    ) -> ListAgentToolsResponse:
        """
        Get all tools assigned to an agent version.
        
        Optionally filter to show only enabled tools.
        Used by AgentEngine to load tools for execution.
        
        Args:
            db: Database session (injected)
            tenant_id: Tenant ID
            agent_id: Agent ID
            version_id: Version ID
            enabled_only: If True, only return enabled tools
        
        Returns:
            ListAgentToolsResponse: All tools (or enabled tools only)
            
        Raises:
            ForbiddenError: If version not accessible
            
        Read operation: No commit.
        """
        # Validate version exists
        self._validate_version_exists(db, tenant_id, agent_id, version_id)
        
        # Query tools for version
        query = db.query(AgentTool).filter(
            AgentTool.agent_version_id == version_id
        )
        
        # Optionally filter by enabled status
        if enabled_only:
            query = query.filter(AgentTool.enabled == True)
        
        # Order by creation order
        tools = query.order_by(AgentTool.created_at).all()
        
        # Count enabled tools
        enabled_count = db.query(AgentTool).filter(
            AgentTool.agent_version_id == version_id,
            AgentTool.enabled == True,
        ).count()
        
        # Read operation: NO commit
        # Return Pydantic schema
        return ListAgentToolsResponse(
            items=[AgentToolResponse.from_orm(t) for t in tools],
            total=len(tools),
            enabled_count=enabled_count,
        )
    
    async def get_tool_config(
        self,
        db: Session,
        tenant_id: str,
        agent_id: str,
        version_id: str,
        tool_name: str,
    ) -> AgentToolResponse:
        """
        Get configuration for a specific tool in a version.
        
        Used by AgentEngine to load tool-specific settings during execution.
        
        Args:
            db: Database session (injected)
            tenant_id: Tenant ID
            agent_id: Agent ID
            version_id: Version ID
            tool_name: Tool to retrieve
        
        Returns:
            AgentToolResponse: Tool configuration details
            
        Raises:
            ForbiddenError: If version not accessible
            NotFoundError: If tool not assigned to version
            
        Read operation: No commit.
        """
        # Validate version exists
        self._validate_version_exists(db, tenant_id, agent_id, version_id)
        
        # Get tool configuration
        tool = db.query(AgentTool).filter(
            AgentTool.agent_version_id == version_id,
            AgentTool.tool_name == tool_name,
        ).first()
        
        if not tool:
            raise NotFoundError(
                f"Tool '{tool_name}' is not configured for this version"
            )
        
        # Read operation: NO commit
        # Return Pydantic schema
        return AgentToolResponse.from_orm(tool)
