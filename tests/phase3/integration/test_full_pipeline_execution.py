"""Real Phase 3 pipeline execution test."""

import asyncio
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.agent_loader import load_agent_sync
from app.engine.agent_engine import AgentEngine
from app.engine.config_converter import agent_config_to_dict
from app.llm.base_provider import LLMResponse
from app.models.agent import Agent
from app.models.agent_platform import AgentVersion, AgentPrompt, AgentTool, PromptType
from app.models.user import Tenant, User
from app.db.database import Base
from app.tools.tool_registry import ToolRegistry

from tests.phase3.helpers import EchoTool, FakeLLMProvider


def test_full_pipeline_loader_converter_engine_tool_loop(monkeypatch) -> None:
    """Validate full pipeline from AgentLoader to execution context logs."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    tenant = Tenant(id=str(uuid.uuid4()), name="Pipeline Tenant", slug="pipeline-tenant")
    user = User(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        email="pipeline@test.com",
        username="pipeline_user",
        hashed_password="hashed",
    )
    agent = Agent(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        created_by=user.id,
        name="Pipeline Agent",
        description="Phase 3 pipeline test",
        agent_type="chat",
        config={},
        is_active=True,
    )
    db.add_all([tenant, user, agent])
    db.commit()

    version = AgentVersion(
        id=str(uuid.uuid4()),
        agent_id=agent.id,
        version="1.0",
        is_active=True,
        system_prompt="System prompt placeholder",
        configuration={
            "llm_config": {
                "provider": "openai",
                "model": "fake-model",
                "temperature": 0.0,
                "max_tokens": 128,
            },
            "memory_config": {
                "type": "conversation",
                "max_history": 5,
                "enable_vector": False,
            },
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
            AgentPrompt(
                id=str(uuid.uuid4()),
                agent_version_id=version.id,
                prompt_type=PromptType.INSTRUCTION,
                prompt_content="Use tools when useful.",
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
                content="Calling echo tool",
                tool_calls=[{"tool_name": "echo_tool", "tool_input": {"text": "hello-tool"}}],
                usage={"prompt_tokens": 9, "completion_tokens": 3},
            ),
            LLMResponse(
                content="Final response after tool",
                tool_calls=None,
                usage={"prompt_tokens": 5, "completion_tokens": 6},
            ),
        ]
    )
    monkeypatch.setattr(
        "app.engine.agent_engine.ProviderRegistry.get_provider",
        lambda *args, **kwargs: provider,
    )

    loaded_config = load_agent_sync(db, agent.id, tenant.id)
    assert loaded_config is not None

    runtime_config = agent_config_to_dict(loaded_config)
    result = asyncio.run(
        AgentEngine().execute(
            agent_config=runtime_config,
            user_input="Run full pipeline",
            execution_id="exec-full-pipeline-1",
            agent_id=agent.id,
            user_id=user.id,
            tenant_id=tenant.id,
            memory_manager=None,
        )
    )
    db.close()

    assert result["success"] is True
    assert result["response"] == "Final response after tool"
    assert len(result["execution_context"].tools_executed) == 1
    assert len(result["execution_context"].steps) > 0
    assert any(step.action == "execute_tool" for step in result["execution_context"].steps)

