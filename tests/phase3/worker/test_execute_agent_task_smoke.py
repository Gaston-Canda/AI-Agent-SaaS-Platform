"""Worker execution smoke tests for execute_agent Celery task."""

import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.agent import Agent, AgentExecution
from app.models.extended import AgentUsage
from app.models.user import Tenant, User
from app.workers import tasks

from tests.phase3.helpers import FakeExecutionContext, FakeMemoryManager


class FakeAgentEngine:
    """Deterministic fake AgentEngine for worker tests."""

    async def execute(self, **kwargs):
        _ = kwargs
        return {
            "success": True,
            "response": "Worker fake response",
            "execution_context": FakeExecutionContext(),
            "error": None,
        }


def _build_test_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_execute_agent_task_completes_and_tracks_usage(monkeypatch) -> None:
    """execute_agent should mark execution as completed and persist usage."""
    test_session_factory = _build_test_db()
    setup_session = test_session_factory()

    tenant = Tenant(id=str(uuid.uuid4()), name="Test Tenant", slug="test-tenant")
    user = User(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        email="worker@test.com",
        username="worker_user",
        hashed_password="hashed",
    )
    agent = Agent(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        created_by=user.id,
        name="Worker Agent",
        agent_type="chat",
        config={
            "system_prompt": "You are a worker test assistant.",
            "llm_provider": "openai",
            "llm_model": "fake-model",
            "temperature": 0.0,
            "max_tokens": 100,
            "tools": [],
        },
        is_active=True,
    )
    execution = AgentExecution(
        id=str(uuid.uuid4()),
        agent_id=agent.id,
        input_data={"message": "hello worker"},
        status="pending",
    )
    execution_id = execution.id
    agent_id = agent.id
    tenant_id = tenant.id
    user_id = user.id
    setup_session.add_all([tenant, user, agent, execution])
    setup_session.commit()
    setup_session.close()

    monkeypatch.setattr(tasks, "SessionLocal", test_session_factory)
    monkeypatch.setattr(tasks, "MemoryManager", FakeMemoryManager)
    monkeypatch.setattr(tasks, "AgentEngine", FakeAgentEngine)
    monkeypatch.setattr(tasks, "load_agent_sync", lambda db, agent_id, tenant_id: None)

    result = tasks.execute_agent.run(
        execution_id=execution_id,
        agent_id=agent_id,
        tenant_id=tenant_id,
        user_id=user_id,
        input_data={"message": "hello worker"},
    )

    verify_session = test_session_factory()
    updated_execution = verify_session.query(AgentExecution).filter(AgentExecution.id == execution_id).first()
    usage_records = verify_session.query(AgentUsage).filter(AgentUsage.execution_id == execution_id).all()
    verify_session.close()

    assert result["success"] is True
    assert updated_execution is not None
    assert updated_execution.status in ("completed", "COMPLETED")
    assert len(usage_records) == 1
