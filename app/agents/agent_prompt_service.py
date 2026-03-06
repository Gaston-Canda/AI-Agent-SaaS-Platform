"""
AgentPromptService - Service layer for agent prompt management.

This service handles all prompt-related operations with emphasis on:
- Managing different prompt types (system, instruction, context, fallback)
- One prompt per type per version constraint
- Returning Pydantic schemas instead of ORM models
- Database session dependency injection
- Tenant isolation (all queries filter by tenant_id)

Prompt assembly for actual execution is AgentLoader's responsibility.
"""

from typing import List, Optional
from datetime import datetime
import uuid
import enum

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import Agent
from app.models.agent_platform import AgentVersion, AgentPrompt, PromptType
from app.agents.schemas import (
    AgentPromptResponse,
    ListAgentPromptsResponse,
)
from app.core.exceptions import NotFoundError, ValidationError, ForbiddenError, ConflictError


class AgentPromptService:
    """
    Service for Agent Prompt management.
    
    Responsibilities:
    - Create, read, update, delete prompts per version
    - Enforce one prompt per type per version
    - Validate prompt types
    - Store prompt content
    - Tenant isolation
    
    Does NOT handle:
    - Prompt assembly/merging
    - LLM integration
    - Prompt rendering/templating
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
    
    def _validate_prompt_type(self, prompt_type: str) -> PromptType:
        """
        Validate and convert string to PromptType enum.
        
        Args:
            prompt_type: String representation of prompt type
            
        Returns:
            PromptType enum value
            
        Raises:
            ValidationError: If prompt_type is invalid
        """
        # Normalize to uppercase for enum matching
        normalized = prompt_type.upper()
        
        # Check against valid enum values
        valid_types = [t.value for t in PromptType]
        
        if normalized not in [t.upper() for t in valid_types]:
            raise ValidationError(
                f"Invalid prompt_type '{prompt_type}'. "
                f"Valid types: {', '.join(valid_types)}"
            )
        
        # Return the enum value (lowercase)
        return PromptType[normalized]
    
    async def create_prompt(
        self,
        db: Session,
        tenant_id: str,
        agent_id: str,
        version_id: str,
        prompt_type: str,
        prompt_content: str,
        created_by: str,
    ) -> AgentPromptResponse:
        """
        Create a new prompt for an agent version.
        
        Only one prompt per type per version is allowed.
        If a prompt of this type already exists, use update_prompt() instead.
        
        Args:
            db: Database session (injected)
            tenant_id: Tenant ID
            agent_id: Agent ID
            version_id: Version ID
            prompt_type: Type of prompt (system|instruction|context|fallback)
            prompt_content: The prompt text (1-5000 chars)
            created_by: User ID who created this prompt
        
        Returns:
            AgentPromptResponse: Newly created prompt
            
        Raises:
            ForbiddenError: If version not accessible
            ValidationError: If prompt_type invalid or content empty
            ConflictError: If prompt of this type already exists
            
        Write operation: Explicit commit and refresh.
        """
        # Validate version exists
        version = self._validate_version_exists(db, tenant_id, agent_id, version_id)
        
        # Validate and normalize prompt_type
        validated_type = self._validate_prompt_type(prompt_type)
        
        # Validate prompt_content
        if not prompt_content or not prompt_content.strip():
            raise ValidationError("Prompt content cannot be empty")
        
        if len(prompt_content) > 5000:
            raise ValidationError("Prompt content cannot exceed 5000 characters")
        
        # Check if prompt of this type already exists
        existing = db.query(AgentPrompt).filter(
            AgentPrompt.agent_version_id == version_id,
            AgentPrompt.prompt_type == validated_type,
        ).first()
        
        if existing:
            raise ConflictError(
                f"Prompt of type '{validated_type.value}' already exists for this version. "
                f"Use update_prompt() to modify it."
            )
        
        # Create new prompt
        prompt = AgentPrompt(
            id=str(uuid.uuid4()),
            agent_version_id=version_id,
            prompt_type=validated_type,
            prompt_content=prompt_content.strip(),
            created_by=created_by,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        # Write operation: explicit commit and refresh
        db.add(prompt)
        db.commit()
        db.refresh(prompt)
        
        # Return Pydantic schema, not ORM model
        return AgentPromptResponse.from_orm(prompt)
    
    async def update_prompt(
        self,
        db: Session,
        tenant_id: str,
        agent_id: str,
        version_id: str,
        prompt_type: str,
        prompt_content: str,
    ) -> AgentPromptResponse:
        """
        Update content of an existing prompt.
        
        Only the prompt_content is updated. Type cannot be changed.
        To use a different prompt type, delete this one and create a new one.
        
        Args:
            db: Database session (injected)
            tenant_id: Tenant ID
            agent_id: Agent ID
            version_id: Version ID
            prompt_type: Type of prompt to update
            prompt_content: New prompt text
        
        Returns:
            AgentPromptResponse: Updated prompt
            
        Raises:
            ForbiddenError: If version not accessible
            ValidationError: If content invalid
            NotFoundError: If prompt of this type doesn't exist
            
        Write operation: Explicit commit and refresh.
        """
        # Validate version exists
        self._validate_version_exists(db, tenant_id, agent_id, version_id)
        
        # Validate and normalize prompt_type
        validated_type = self._validate_prompt_type(prompt_type)
        
        # Validate prompt_content
        if not prompt_content or not prompt_content.strip():
            raise ValidationError("Prompt content cannot be empty")
        
        if len(prompt_content) > 5000:
            raise ValidationError("Prompt content cannot exceed 5000 characters")
        
        # Find existing prompt
        prompt = db.query(AgentPrompt).filter(
            AgentPrompt.agent_version_id == version_id,
            AgentPrompt.prompt_type == validated_type,
        ).first()
        
        if not prompt:
            raise NotFoundError(
                f"Prompt of type '{validated_type.value}' not found for this version"
            )
        
        # Update content
        prompt.prompt_content = prompt_content.strip()
        prompt.updated_at = datetime.utcnow()
        
        # Write operation: explicit commit and refresh
        db.commit()
        db.refresh(prompt)
        
        # Return Pydantic schema
        return AgentPromptResponse.from_orm(prompt)
    
    async def get_prompt(
        self,
        db: Session,
        tenant_id: str,
        agent_id: str,
        version_id: str,
        prompt_type: str,
    ) -> AgentPromptResponse:
        """
        Get a specific prompt by type from a version.
        
        Args:
            db: Database session (injected)
            tenant_id: Tenant ID
            agent_id: Agent ID
            version_id: Version ID
            prompt_type: Type of prompt to retrieve
        
        Returns:
            AgentPromptResponse: The prompt details
            
        Raises:
            ForbiddenError: If version not accessible
            ValidationError: If prompt_type invalid
            NotFoundError: If prompt of this type doesn't exist
            
        Read operation: No commit.
        """
        # Validate version exists
        self._validate_version_exists(db, tenant_id, agent_id, version_id)
        
        # Validate and normalize prompt_type
        validated_type = self._validate_prompt_type(prompt_type)
        
        # Get prompt
        prompt = db.query(AgentPrompt).filter(
            AgentPrompt.agent_version_id == version_id,
            AgentPrompt.prompt_type == validated_type,
        ).first()
        
        if not prompt:
            raise NotFoundError(
                f"Prompt of type '{validated_type.value}' not found for this version"
            )
        
        # Read operation: NO commit
        # Return Pydantic schema
        return AgentPromptResponse.from_orm(prompt)
    
    async def list_prompts(
        self,
        db: Session,
        tenant_id: str,
        agent_id: str,
        version_id: str,
    ) -> ListAgentPromptsResponse:
        """
        Get all prompts for an agent version.
        
        Returns all prompts regardless of type. Some types may not exist,
        which is valid (they are optional). AgentEngine uses defaults if missing.
        
        Args:
            db: Database session (injected)
            tenant_id: Tenant ID
            agent_id: Agent ID
            version_id: Version ID
        
        Returns:
            ListAgentPromptsResponse: All prompts for this version
            
        Raises:
            ForbiddenError: If version not accessible
            
        Read operation: No commit.
        """
        # Validate version exists
        self._validate_version_exists(db, tenant_id, agent_id, version_id)
        
        # Query all prompts for version, ordered by creation
        prompts = db.query(AgentPrompt).filter(
            AgentPrompt.agent_version_id == version_id
        ).order_by(
            AgentPrompt.created_at
        ).all()
        
        # Read operation: NO commit
        # Return Pydantic schema
        return ListAgentPromptsResponse(
            items=[AgentPromptResponse.from_orm(p) for p in prompts],
            total=len(prompts),
        )
    
    async def delete_prompt(
        self,
        db: Session,
        tenant_id: str,
        agent_id: str,
        version_id: str,
        prompt_type: str,
    ) -> None:
        """
        Delete a prompt from a version.
        
        Hard delete (permanent removal). Some prompt types may be considered
        "required" by AgentEngine, but architecturally all can be deleted.
        AgentEngine will use defaults if prompts are missing.
        
        Args:
            db: Database session (injected)
            tenant_id: Tenant ID
            agent_id: Agent ID
            version_id: Version ID
            prompt_type: Type of prompt to delete
        
        Raises:
            ForbiddenError: If version not accessible
            ValidationError: If prompt_type invalid
            NotFoundError: If prompt of this type doesn't exist
            
        Write operation: Explicit commit.
        """
        # Validate version exists
        self._validate_version_exists(db, tenant_id, agent_id, version_id)
        
        # Validate and normalize prompt_type
        validated_type = self._validate_prompt_type(prompt_type)
        
        # Find and delete prompt
        prompt = db.query(AgentPrompt).filter(
            AgentPrompt.agent_version_id == version_id,
            AgentPrompt.prompt_type == validated_type,
        ).first()
        
        if not prompt:
            raise NotFoundError(
                f"Prompt of type '{validated_type.value}' not found for this version"
            )
        
        # Hard delete (no soft delete for prompts)
        db.delete(prompt)
        
        # Write operation: explicit commit (no refresh needed since we deleted)
        db.commit()
