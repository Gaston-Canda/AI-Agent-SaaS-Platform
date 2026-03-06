"""
Agent service for business logic.
"""

from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime

from app.models.agent import Agent, AgentExecution
from app.schemas.agent import AgentCreate, AgentUpdate
from app.services.usage_service import UsageService


class AgentService:
    """Service for agent operations."""
    
    @staticmethod
    def create_agent(
        db: Session,
        agent_data: AgentCreate,
        tenant_id: str,
        created_by: str,
    ) -> Agent:
        """Create a new agent."""
        quota_status = UsageService.check_agent_quota(db, tenant_id)
        if quota_status.get("agents_exceeded"):
            raise ValueError("Agent quota exceeded for current subscription plan")

        agent = Agent(
            tenant_id=tenant_id,
            created_by=created_by,
            name=agent_data.name,
            description=agent_data.description,
            agent_type=agent_data.agent_type,
            system_prompt=agent_data.system_prompt,
            model=agent_data.model,
            config=agent_data.config,
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        return agent
    
    @staticmethod
    def get_agent_by_id(db: Session, agent_id: str, tenant_id: str) -> Optional[Agent]:
        """Get agent by ID, scoped to tenant."""
        return db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.tenant_id == tenant_id,
        ).first()
    
    @staticmethod
    def list_agents(db: Session, tenant_id: str, skip: int = 0, limit: int = 100) -> List[Agent]:
        """List all agents for a tenant."""
        return db.query(Agent).filter(
            Agent.tenant_id == tenant_id,
        ).offset(skip).limit(limit).all()
    
    @staticmethod
    def update_agent(
        db: Session,
        agent: Agent,
        agent_data: AgentUpdate,
    ) -> Agent:
        """Update an agent."""
        update_data = agent_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(agent, field, value)
        
        agent.version += 1
        agent.updated_at = datetime.utcnow()
        db.add(agent)
        db.commit()
        db.refresh(agent)
        return agent
    
    @staticmethod
    def delete_agent(db: Session, agent: Agent) -> None:
        """Delete an agent."""
        db.delete(agent)
        db.commit()
    
    @staticmethod
    def create_execution(
        db: Session,
        agent_id: str,
        input_data: dict,
    ) -> AgentExecution:
        """Create an agent execution record."""
        execution = AgentExecution(
            agent_id=agent_id,
            input_data=input_data,
            status="pending",
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
        return execution
    
    @staticmethod
    def update_execution(
        db: Session,
        execution: AgentExecution,
        status: str,
        output_data: Optional[dict] = None,
        error_message: Optional[str] = None,
        execution_time_ms: Optional[int] = None,
    ) -> AgentExecution:
        """Update an agent execution."""
        execution.status = status
        execution.output_data = output_data
        execution.error_message = error_message
        execution.execution_time_ms = execution_time_ms
        execution.completed_at = datetime.utcnow()
        db.add(execution)
        db.commit()
        db.refresh(execution)
        return execution
