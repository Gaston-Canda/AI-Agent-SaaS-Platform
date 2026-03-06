"""
AgentService - Service layer for agent CRUD operations.

This service handles all agent-related database operations with emphasis on:
- Returning Pydantic schemas instead of ORM models
- Database session dependency injection
- Tenant isolation (all queries filter by tenant_id)
- Clear separation between CRUD and execution logic

The AgentEngine handles execution logic separately.
"""

from typing import List, Optional
from datetime import datetime
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import Agent, Tenant, User
from app.models.agent_platform import AgentStatus
from app.agents.schemas import AgentResponse, ListAgentsResponse
from app.core.exceptions import NotFoundError, ValidationError, ForbiddenError
from app.services.usage_service import UsageService


class AgentService:
    """
    Service for Agent CRUD operations.
    
    Responsibilities:
    - Create, read, update, delete agents
    - Enforce tenant isolation
    - Return Pydantic schemas
    - Never directly access database session creation
    
    Does NOT handle:
    - Agent execution
    - LLM calls
    - Tool execution
    - Memory management
    """
    
    async def create_agent(
        self,
        db: Session,
        tenant_id: str,
        created_by: str,
        name: str,
        description: Optional[str] = None,
        agent_type: str = "chat",
    ) -> AgentResponse:
        """
        Create a new agent.
        
        Args:
            db: Database session (injected)
            tenant_id: Tenant ID (required for multi-tenancy)
            created_by: User ID who created the agent
            name: Agent name
            description: Agent description (optional)
            agent_type: Type of agent (chat, task, automation)
            
        Returns:
            AgentResponse: Created agent

        Raises:
            ValidationError: If input validation fails
            NotFoundError: If tenant or user not found
            
        Write operation: Uses explicit commit and refresh.
        """
        # Validation: name cannot be empty
        if not name or len(name.strip()) == 0:
            raise ValidationError("Agent name cannot be empty")
        
        # Validation: name length
        if len(name) > 255:
            raise ValidationError("Agent name cannot exceed 255 characters")
        
        # Validation: valid agent_type
        valid_types = ["chat", "task", "automation"]
        if agent_type not in valid_types:
            raise ValidationError(f"Agent type must be one of: {', '.join(valid_types)}")
        
        # Check tenant exists
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise NotFoundError("Tenant not found")
        
        # Check user exists and belongs to tenant
        user = db.query(User).filter(
            User.id == created_by,
            User.tenant_id == tenant_id,
        ).first()
        if not user:
            raise NotFoundError("User not found or does not belong to tenant")

        # Enforce plan agent quota
        quota_status = UsageService.check_agent_quota(db, tenant_id)
        if quota_status.get("agents_exceeded"):
            raise ValidationError("Agent quota exceeded for current subscription plan")
        
        # Create agent
        agent = Agent(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            created_by=created_by,
            name=name.strip(),
            description=description,
            agent_type=agent_type,
            status=AgentStatus.DRAFT,
            is_active=False,
        )
        
        # Write operation: explicit commit and refresh
        db.add(agent)
        db.commit()
        db.refresh(agent)
        
        # Return Pydantic schema, not ORM model
        return AgentResponse.from_orm(agent)
    
    async def get_agent(
        self,
        db: Session,
        tenant_id: str,
        agent_id: str,
    ) -> AgentResponse:
        """
        Get agent by ID.
        
        Args:
            db: Database session (injected)
            tenant_id: Tenant ID (for multi-tenancy)
            agent_id: Agent ID to retrieve
            
        Returns:
            AgentResponse: Agent details
            
        Raises:
            NotFoundError: If agent not found
            
        Read operation: No commit.
        """
        # Query with tenant_id filter (multi-tenant safety)
        agent = db.query(Agent).filter(
            Agent.tenant_id == tenant_id,
            Agent.id == agent_id,
        ).first()
        
        if not agent:
            raise NotFoundError("Agent not found")
        
        # Read operation: NO commit
        # Return Pydantic schema
        return AgentResponse.from_orm(agent)
    
    async def list_agents(
        self,
        db: Session,
        tenant_id: str,
        skip: int = 0,
        limit: int = 50,
        status: Optional[str] = None,
    ) -> ListAgentsResponse:
        """
        List agents for a tenant with pagination.
        
        Args:
            db: Database session (injected)
            tenant_id: Tenant ID (for multi-tenancy)
            skip: Number of records to skip (default 0)
            limit: Number of records to retrieve (default 50, max 100)
            status: Optional filter by status (draft, active, archived)
            
        Returns:
            ListAgentsResponse: Paginated list of agents
            
        Pagination rules:
        - Maximum limit: 100 records
        - Default limit: 50 records
        - Ordered by: created_at DESC (most recent first, uses index)
        
        Read operation: No commit.
        """
        # Pagination: enforce limits
        skip = max(int(skip), 0)  # Minimum 0
        limit = max(int(limit), 1)  # Minimum 1
        limit = min(limit, 100)  # Maximum 100
        
        # Build query with tenant_id filter (multi-tenant safety)
        query = db.query(Agent).filter(Agent.tenant_id == tenant_id)
        
        # Optional status filter
        if status:
            query = query.filter(Agent.status == status)
        
        # Count total before pagination
        total = query.count()
        
        # Apply ordering (by indexed created_at, descending)
        # Descending = most recent first (better UX)
        agents = query.order_by(
            Agent.created_at.desc()
        ).offset(skip).limit(limit).all()
        
        # Read operation: NO commit
        # Return Pydantic schemas
        items = [AgentResponse.from_orm(a) for a in agents]
        
        return ListAgentsResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
        )
    
    async def update_agent(
        self,
        db: Session,
        tenant_id: str,
        agent_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        agent_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> AgentResponse:
        """
        Update an agent.
        
        Args:
            db: Database session (injected)
            tenant_id: Tenant ID (for multi-tenancy)
            agent_id: Agent ID to update
            name: New agent name (optional)
            description: New description (optional)
            agent_type: New agent type (optional)
            status: New status (optional)
            
        Returns:
            AgentResponse: Updated agent
            
        Raises:
            NotFoundError: If agent not found
            ValidationError: If validation fails
            
        Notes:
        - Does NOT update system_prompt or model (use AgentVersionService)
        - Does NOT update configuration (use AgentVersionService)
        - Only updates simple fields
        
        Write operation: explicit commit and refresh.
        """
        # Get agent with tenant_id filter
        agent = db.query(Agent).filter(
            Agent.tenant_id == tenant_id,
            Agent.id == agent_id,
        ).first()
        
        if not agent:
            raise NotFoundError("Agent not found")
        
        # Update fields if provided
        if name is not None:
            if len(name.strip()) == 0:
                raise ValidationError("Agent name cannot be empty")
            if len(name) > 255:
                raise ValidationError("Agent name cannot exceed 255 characters")
            agent.name = name.strip()
        
        if description is not None:
            if len(description) > 1000:
                raise ValidationError("Description cannot exceed 1000 characters")
            agent.description = description
        
        if agent_type is not None:
            valid_types = ["chat", "task", "automation"]
            if agent_type not in valid_types:
                raise ValidationError(f"Agent type must be one of: {', '.join(valid_types)}")
            agent.agent_type = agent_type
        
        if status is not None:
            valid_statuses = ["draft", "active", "archived"]
            if status not in valid_statuses:
                raise ValidationError(f"Status must be one of: {', '.join(valid_statuses)}")
            agent.status = status
        
        # Update timestamp
        agent.updated_at = datetime.utcnow()
        
        # Write operation: explicit commit and refresh
        db.commit()
        db.refresh(agent)
        
        # Return Pydantic schema
        return AgentResponse.from_orm(agent)
    
    async def delete_agent(
        self,
        db: Session,
        tenant_id: str,
        agent_id: str,
    ) -> None:
        """
        Delete (soft delete) an agent.
        
        Args:
            db: Database session (injected)
            tenant_id: Tenant ID (for multi-tenancy)
            agent_id: Agent ID to delete
            
        Raises:
            NotFoundError: If agent not found
            
        Notes:
        - Uses soft delete: sets status to "archived"
        - Data is never permanently deleted
        - Preserves audit trail and historical data
        
        Write operation: explicit commit and refresh.
        """
        # Get agent with tenant_id filter
        agent = db.query(Agent).filter(
            Agent.tenant_id == tenant_id,
            Agent.id == agent_id,
        ).first()
        
        if not agent:
            raise NotFoundError("Agent not found")
        
        # Soft delete: archive instead of delete
        agent.status = AgentStatus.ARCHIVED
        agent.is_active = False
        agent.updated_at = datetime.utcnow()
        
        # Write operation: explicit commit and refresh
        db.commit()
        db.refresh(agent)
    
    async def agent_exists(
        self,
        db: Session,
        tenant_id: str,
        agent_id: str,
    ) -> bool:
        """
        Check if an agent exists.
        
        Args:
            db: Database session (injected)
            tenant_id: Tenant ID (for multi-tenancy)
            agent_id: Agent ID to check
            
        Returns:
            bool: True if agent exists, False otherwise
            
        Read operation: No commit.
        """
        agent = db.query(Agent).filter(
            Agent.tenant_id == tenant_id,
            Agent.id == agent_id,
        ).first()
        
        return agent is not None
