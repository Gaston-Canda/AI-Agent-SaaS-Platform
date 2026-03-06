"""API integration test for direct agent execution endpoint."""

import uuid
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.dependencies import get_current_user, check_execution_quota
from app.db.database import Base, get_db
from app.llm.base_provider import LLMResponse
from app.models.agent import Agent, AgentExecution
from app.models.agent_platform import AgentVersion, AgentPrompt, AgentTool, PromptType
from app.models.extended import ExecutionLog
from app.models.user import Tenant, User
from app.routers.agents import router as agents_router
from app.tools.tool_registry import ToolRegistry

from tests.phase3.helpers import EchoTool, FakeLLMProvider


def test_execute_endpoint_runs_and_persists(monkeypatch) -> None:
    """POST /api/agents/{agent_id}/execute executes and stores logs."""
    engine = create_engine("sqlite:///test_execute_endpoint.db", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    tenant_suffix = str(uuid.uuid4())[:8]
    tenant = Tenant(id=str(uuid.uuid4()), name=f"API Tenant {tenant_suffix}", slug=f"api-tenant-{tenant_suffix}")
    user = User(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        email="api@test.com",
        username="api_user",
        hashed_password="hashed",
    )
    agent = Agent(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        created_by=user.id,
        name="API Execution Agent",
        description="Agent for execute endpoint test",
        agent_type="chat",
        config={},
        is_active=True,
    )
    db.add_all([tenant, user, agent])
    db.commit()
    user_id = user.id
    tenant_id = tenant.id

    version = AgentVersion(
        id=str(uuid.uuid4()),
        agent_id=agent.id,
        version="1.0",
        is_active=True,
        system_prompt="System",
        configuration={
            "llm_config": {
                "provider": "openai",
                "model": "fake-model",
                "temperature": 0.0,
                "max_tokens": 128,
            }
        },
        created_by=user.id,
    )
    db.add(version)
    db.commit()

    db.add_all(
        [
            AgentPrompt(
                id=str(uuid.uuid4()),
                agent_version_id=version.id,
                prompt_type=PromptType.SYSTEM,
                prompt_content="You are a test assistant.",
            ),
            AgentTool(
                id=str(uuid.uuid4()),
                agent_version_id=version.id,
                tool_name="echo_tool",
                enabled=True,
                tool_config={},
            ),
        ]
    )
    db.commit()

    ToolRegistry.register(EchoTool())
    provider = FakeLLMProvider(
        responses=[
            LLMResponse(
                content="Calling tool",
                tool_calls=[{"tool_name": "echo_tool", "tool_input": {"text": "api-loop"}}],
                usage={"prompt_tokens": 4, "completion_tokens": 2},
            ),
            LLMResponse(
                content="API final response",
                tool_calls=None,
                usage={"prompt_tokens": 3, "completion_tokens": 5},
            ),
        ]
    )
    monkeypatch.setattr(
        "app.engine.agent_engine.ProviderRegistry.get_provider",
        lambda *args, **kwargs: provider,
    )

    app = FastAPI()
    app.include_router(agents_router)

    def _override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    async def _override_current_user():
        return SimpleNamespace(id=user_id, tenant_id=tenant_id)

    async def _override_quota():
        return True

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_current_user
    app.dependency_overrides[check_execution_quota] = _override_quota

    client = TestClient(app)
    response = client.post(f"/api/agents/{agent.id}/execute", json={"message": "Hello agent"})

    assert response.status_code == 200
    body = response.json()
    assert body["response"] == "API final response"
    assert body["execution_id"]
    assert body["tokens_used"] > 0
    assert body["execution_time_ms"] >= 0
    assert body["tools_executed"] == ["echo_tool"]

    verify_db = SessionLocal()
    stored_execution = verify_db.query(AgentExecution).filter(AgentExecution.id == body["execution_id"]).first()
    stored_logs = verify_db.query(ExecutionLog).filter(ExecutionLog.execution_id == body["execution_id"]).all()
    verify_db.close()

    assert stored_execution is not None
    assert stored_execution.status == "completed"
    assert len(stored_logs) > 0
