"""Unit tests for AgentEngine input contracts."""

import asyncio

from app.agents.schemas import (
    AgentConfig,
    AgentLLMConfig,
    AgentMemoryConfig,
    AgentPromptConfigItem,
)
from app.engine.agent_engine import AgentEngine
from app.llm.base_provider import LLMResponse

from tests.phase3.helpers import FakeLLMProvider


def test_execute_accepts_legacy_dict_config(monkeypatch) -> None:
    """AgentEngine should execute with Phase 1/2 legacy dict config."""
    provider = FakeLLMProvider(
        responses=[
            LLMResponse(
                content="Legacy config response",
                tool_calls=None,
                usage={"prompt_tokens": 3, "completion_tokens": 4},
            )
        ]
    )
    monkeypatch.setattr(
        "app.engine.agent_engine.ProviderRegistry.get_provider",
        lambda *args, **kwargs: provider,
    )

    engine = AgentEngine()
    result = asyncio.run(
        engine.execute(
            agent_config={
                "name": "Legacy Agent",
                "system_prompt": "You are a test assistant.",
                "llm_provider": "openai",
                "llm_model": "fake-model",
                "tools": [],
                "temperature": 0.0,
                "max_tokens": 128,
            },
            user_input="Hello",
            execution_id="exec-unit-legacy-1",
            agent_id="agent-unit-legacy-1",
            user_id="user-unit-1",
            tenant_id="tenant-unit-1",
            memory_manager=None,
        )
    )

    assert result["success"] is True
    assert result["response"] == "Legacy config response"
    assert result["execution_context"].status == "completed"


def test_execute_accepts_phase3_agent_config(monkeypatch) -> None:
    """AgentEngine should execute with Phase 3 AgentConfig schema."""
    provider = FakeLLMProvider(
        responses=[
            LLMResponse(
                content="Phase 3 config response",
                tool_calls=None,
                usage={"prompt_tokens": 8, "completion_tokens": 6},
            )
        ]
    )
    monkeypatch.setattr(
        "app.engine.agent_engine.ProviderRegistry.get_provider",
        lambda *args, **kwargs: provider,
    )

    phase3_config = AgentConfig(
        agent_id="agent-unit-phase3-1",
        version_number="1.0.0",
        system_prompt="You are a test assistant.",
        prompts=AgentPromptConfigItem(system="You are a test assistant."),
        llm_config=AgentLLMConfig(
            provider="openai",
            model="fake-model",
            temperature=0.0,
            max_tokens=128,
        ),
        tools=[],
        memory_config=AgentMemoryConfig(type="conversation", max_history=5, enable_vector=False),
    )

    engine = AgentEngine()
    result = asyncio.run(
        engine.execute(
            agent_config=phase3_config,
            user_input="Hello",
            execution_id="exec-unit-phase3-1",
            agent_id="agent-unit-phase3-1",
            user_id="user-unit-1",
            tenant_id="tenant-unit-1",
            memory_manager=None,
        )
    )

    assert result["success"] is True
    assert result["response"] == "Phase 3 config response"
    assert result["execution_context"].status == "completed"
