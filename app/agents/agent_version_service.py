"""
AgentVersionService - Service layer for agent version management.

This service handles all version-related operations with emphasis on:
- Semantic versioning (1.0, 1.1, 2.0)
- Active version management (only one active per agent)
- Version history and rollback capability
- Returning Pydantic schemas instead of ORM models
- Database session dependency injection
- Tenant isolation (all queries filter by tenant_id)

Version Numbering Logic:
- Major.Minor format: "1.0", "1.1", "2.0", etc.
- Initial version is "1.0"
- Minor increment: 1.0 → 1.1 → 1.2 (for configuration changes)
- Major increment: 1.x → 2.0 (for breaking changes, user-triggered)
"""

from typing import List, Optional
from datetime import datetime
import uuid
import re

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import Agent, Tenant, User
from app.models.agent_platform import AgentVersion
from app.agents.schemas import (
    AgentVersionResponse,
    CreateVersionRequest,
    ListVersionsResponse,
)
from app.core.exceptions import NotFoundError, ValidationError, ForbiddenError


class AgentVersionService:
    """
    Service for Agent Version management.
    
    Responsibilities:
    - Create new versions (auto-increment)
    - Retrieve versions
    - Activate/deactivate versions
    - Rollback to previous versions
    - Semantic version management
    - Enforce single active version per agent
    
    Does NOT handle:
    - Agent creation/deletion (handled by AgentService)
    - Tool management (handled by AgentToolService)
    - Prompt management (handled by AgentPromptService)
    - Agent execution
    """
    
    def _increment_version(self, current_version: str, is_major: bool = False) -> str:
        """
        Increment version number using semantic versioning.
        
        Args:
            current_version: Current version string (e.g., "1.0", "1.1")
            is_major: If True, increment major version (1.x -> 2.0)
                     If False, increment minor version (1.0 -> 1.1)
        
        Returns:
            New version string
            
        Raises:
            ValidationError: If version format is invalid
        """
        # Validate version format
        if not re.match(r'^\d+\.\d+$', current_version):
            raise ValidationError(f"Invalid version format: {current_version}. Expected 'X.Y'")
        
        major, minor = map(int, current_version.split('.'))
        
        if is_major:
            return f"{major + 1}.0"
        else:
            return f"{major}.{minor + 1}"
    
    def _validate_agent_exists(
        self,
        db: Session,
        tenant_id: str,
        agent_id: str,
    ) -> Agent:
        """
        Validate that agent exists and belongs to tenant.
        
        Args:
            db: Database session
            tenant_id: Tenant ID
            agent_id: Agent ID
            
        Returns:
            Agent object if valid
            
        Raises:
            NotFoundError: If agent not found
            ForbiddenError: If agent does not belong to tenant
        """
        # Query with tenant_id filter for security
        agent = db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.tenant_id == tenant_id,
        ).first()
        
        if not agent:
            raise ForbiddenError("Agent not found or does not belong to this tenant")
        
        return agent
    
    async def create_version(
        self,
        db: Session,
        tenant_id: str,
        agent_id: str,
        created_by: str,
        system_prompt: str,
        configuration: Optional[dict] = None,
        is_major: bool = False,
    ) -> AgentVersionResponse:
        """
        Create a new version for an agent.
        
        Automatically increments version number based on semantic versioning.
        New version is created as INACTIVE; use activate_version() to set as active.
        
        For first version ever: creates "1.0"
        For subsequent versions: increments minor (1.0→1.1) unless is_major=True
        
        Args:
            db: Database session (injected)
            tenant_id: Tenant ID
            agent_id: Agent ID
            created_by: User ID who created this version
            system_prompt: New system prompt
            configuration: Optional LLM configuration dict
            is_major: If True, increment major version (1.x -> 2.0)
        
        Returns:
            AgentVersionResponse: Newly created version
            
        Raises:
            ForbiddenError: If agent not found or not accessible
            ValidationError: If parameters invalid
            
        Write operation: Explicit commit and refresh.
        """
        # Validate agent exists and belongs to tenant
        agent = self._validate_agent_exists(db, tenant_id, agent_id)
        
        # Validate system_prompt
        if not system_prompt or not system_prompt.strip():
            raise ValidationError("System prompt cannot be empty")
        
        if len(system_prompt) > 5000:
            raise ValidationError("System prompt cannot exceed 5000 characters")
        
        # Get latest version to determine next version number
        latest_version = db.query(AgentVersion).filter(
            AgentVersion.agent_id == agent_id
        ).order_by(
            desc(AgentVersion.created_at)
        ).first()
        
        # Determine next version
        if latest_version:
            next_version = self._increment_version(
                latest_version.version,
                is_major=is_major
            )
        else:
            # First version
            next_version = "1.0"
        
        # Create new version (as inactive)
        version = AgentVersion(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            version=next_version,
            is_active=False,  # New versions start inactive
            system_prompt=system_prompt.strip(),
            configuration=configuration or {},
            created_by=created_by,
            created_at=datetime.utcnow(),
        )
        
        # Write operation: explicit commit and refresh
        db.add(version)
        db.commit()
        db.refresh(version)
        
        # Return Pydantic schema, not ORM model
        return AgentVersionResponse.from_orm(version)
    
    async def get_versions(
        self,
        db: Session,
        tenant_id: str,
        agent_id: str,
    ) -> ListVersionsResponse:
        """
        Get all versions for an agent.
        
        Returns versions ordered by created_at DESC (newest first).
        
        Args:
            db: Database session (injected)
            tenant_id: Tenant ID
            agent_id: Agent ID
        
        Returns:
            ListVersionsResponse: All versions ordered by created_at DESC
            
        Raises:
            ForbiddenError: If agent not found or not accessible
            
        Read operation: No commit.
        """
        # Validate agent exists (security check)
        self._validate_agent_exists(db, tenant_id, agent_id)
        
        # Query versions ordered by created_at DESC (newest first)
        versions = db.query(AgentVersion).filter(
            AgentVersion.agent_id == agent_id
        ).order_by(
            desc(AgentVersion.created_at)
        ).all()
        
        # Read operation: NO commit
        # Return Pydantic schema
        return ListVersionsResponse(
            items=[AgentVersionResponse.from_orm(v) for v in versions],
            total=len(versions),
        )
    
    async def get_latest_version(
        self,
        db: Session,
        tenant_id: str,
        agent_id: str,
    ) -> AgentVersionResponse:
        """
        Get the active version of an agent.
        
        Returns the ACTIVE version (is_active=True), not the newest by date.
        This is crucial for agent execution - you always execute the active version.
        
        Args:
            db: Database session (injected)
            tenant_id: Tenant ID
            agent_id: Agent ID
        
        Returns:
            AgentVersionResponse: The active version
            
        Raises:
            ForbiddenError: If agent not found or not accessible
            NotFoundError: If no active version exists
            
        Read operation: No commit.
        """
        # Validate agent exists (security check)
        self._validate_agent_exists(db, tenant_id, agent_id)
        
        # Query for the single active version
        version = db.query(AgentVersion).filter(
            AgentVersion.agent_id == agent_id,
            AgentVersion.is_active == True,
        ).first()
        
        if not version:
            raise NotFoundError("No active version found for this agent")
        
        # Read operation: NO commit
        # Return Pydantic schema
        return AgentVersionResponse.from_orm(version)
    
    async def activate_version(
        self,
        db: Session,
        tenant_id: str,
        agent_id: str,
        version_id: str,
    ) -> AgentVersionResponse:
        """
        Activate a specific version for an agent.
        
        Deactivates the current active version and activates the specified version.
        First activates the new version, then deactivates others to ensure consistency.
        
        Also updates Agent.default_version_id to point to new active version.
        
        Args:
            db: Database session (injected)
            tenant_id: Tenant ID
            agent_id: Agent ID
            version_id: Version ID to activate
        
        Returns:
            AgentVersionResponse: The newly activated version
            
        Raises:
            ForbiddenError: If agent not found or version doesn't belong to agent
            NotFoundError: If version not found
            
        Write operation: Explicit commit and refresh.
        """
        # Validate agent exists
        agent = self._validate_agent_exists(db, tenant_id, agent_id)
        
        # Verify version exists and belongs to agent
        version = db.query(AgentVersion).filter(
            AgentVersion.id == version_id,
            AgentVersion.agent_id == agent_id,
        ).first()
        
        if not version:
            raise NotFoundError("Version not found or does not belong to this agent")
        
        # Deactivate all other versions for this agent
        db.query(AgentVersion).filter(
            AgentVersion.agent_id == agent_id,
            AgentVersion.id != version_id,
        ).update({AgentVersion.is_active: False})
        
        # Activate the specified version
        version.is_active = True
        
        # Update agent's default_version_id
        agent.default_version_id = version_id
        
        # Write operation: explicit commit and refresh
        db.commit()
        db.refresh(version)
        db.refresh(agent)
        
        # Return Pydantic schema
        return AgentVersionResponse.from_orm(version)
    
    async def get_version_by_id(
        self,
        db: Session,
        tenant_id: str,
        agent_id: str,
        version_id: str,
    ) -> AgentVersionResponse:
        """
        Get a specific version by ID.
        
        Args:
            db: Database session (injected)
            tenant_id: Tenant ID
            agent_id: Agent ID
            version_id: Version ID to retrieve
        
        Returns:
            AgentVersionResponse: The requested version
            
        Raises:
            ForbiddenError: If agent not accessible
            NotFoundError: If version not found
            
        Read operation: No commit.
        """
        # Validate agent exists (security check)
        self._validate_agent_exists(db, tenant_id, agent_id)
        
        # Query for specific version
        version = db.query(AgentVersion).filter(
            AgentVersion.id == version_id,
            AgentVersion.agent_id == agent_id,
        ).first()
        
        if not version:
            raise NotFoundError("Version not found")
        
        # Read operation: NO commit
        # Return Pydantic schema
        return AgentVersionResponse.from_orm(version)
    
    async def rollback_version(
        self,
        db: Session,
        tenant_id: str,
        agent_id: str,
        version_number: str,
    ) -> AgentVersionResponse:
        """
        Rollback to a specific version by version number (e.g., "1.0").
        
        This is a convenience method that finds the version by number and activates it.
        Useful for UI: "Rollback to 1.0" instead of remembering version IDs.
        
        Args:
            db: Database session (injected)
            tenant_id: Tenant ID
            agent_id: Agent ID
            version_number: Version number to rollback to (e.g., "1.0", "1.1")
        
        Returns:
            AgentVersionResponse: The activated version
            
        Raises:
            ForbiddenError: If agent not accessible
            NotFoundError: If version number not found
            
        Write operation: Explicit commit and refresh.
        """
        # Validate agent exists
        self._validate_agent_exists(db, tenant_id, agent_id)
        
        # Find version by version number
        version = db.query(AgentVersion).filter(
            AgentVersion.agent_id == agent_id,
            AgentVersion.version == version_number,
        ).first()
        
        if not version:
            raise NotFoundError(f"Version {version_number} not found")
        
        # Use activate_version to perform the rollback
        return await self.activate_version(db, tenant_id, agent_id, version.id)
