"""Integration smoke tests for Phase 3 execution pipeline."""

import asyncio

from app.agents.schemas import (
    AgentConfig,
    AgentLLMConfig,
    AgentMemoryConfig,
    AgentPromptConfigItem,
)
from app.engine.agent_engine import AgentEngine
from app.engine.config_converter import agent_config_to_dict, dict_to_agent_config_partial
from app.llm.base_provider import LLMResponse
from app.tools.tool_registry import ToolRegistry

from tests.phase3.helpers import EchoTool, FakeLLMProvider


def test_pipeline_phase3_config_converter_to_engine(monkeypatch) -> None:
    """Phase 3 config should pass converter and execute in engine."""
    provider = FakeLLMProvider(
        responses=[
            LLMResponse(
                content="Pipeline response",
                tool_calls=None,
                usage={"prompt_tokens": 6, "completion_tokens": 5},
            )
        ]
    )
    monkeypatch.setattr(
        "app.engine.agent_engine.ProviderRegistry.get_provider",
        lambda *args, **kwargs: provider,
    )

    phase3_config = AgentConfig(
        agent_id="agent-int-phase3-1",
        version_number="1.0.0",
        system_prompt="You are a pipeline test assistant.",
        prompts=AgentPromptConfigItem(system="You are a pipeline test assistant."),
        llm_config=AgentLLMConfig(
            provider="openai",
            model="fake-model",
            temperature=0.1,
            max_tokens=200,
        ),
        tools=[],
        memory_config=AgentMemoryConfig(type="conversation", max_history=5, enable_vector=False),
    )

    legacy_like_config = agent_config_to_dict(phase3_config)
    completed_config = dict_to_agent_config_partial(legacy_like_config)

    engine = AgentEngine()
    result = asyncio.run(
        engine.execute(
            agent_config=completed_config,
            user_input="Run pipeline",
            execution_id="exec-int-pipeline-1",
            agent_id="agent-int-phase3-1",
            user_id="user-int-1",
            tenant_id="tenant-int-1",
            memory_manager=None,
        )
    )

    assert result["success"] is True
    assert result["response"] == "Pipeline response"


def test_pipeline_with_tool_execution_loop(monkeypatch) -> None:
    """Engine should execute a tool loop and return final LLM response."""
    ToolRegistry.clear()
    ToolRegistry.register(EchoTool())

    provider = FakeLLMProvider(
        responses=[
            LLMResponse(
                content="Calling tool",
                tool_calls=[{"tool_name": "echo_tool", "tool_input": {"text": "ping"}}],
                usage={"prompt_tokens": 10, "completion_tokens": 4},
            ),
            LLMResponse(
                content="Tool execution completed",
                tool_calls=None,
                usage={"prompt_tokens": 5, "completion_tokens": 5},
            ),
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
                "name": "Tool Loop Agent",
                "system_prompt": "Use tools when needed.",
                "llm_provider": "openai",
                "llm_model": "fake-model",
                "temperature": 0.0,
                "max_tokens": 200,
                "tools": ["echo_tool"],
            },
            user_input="Use tool",
            execution_id="exec-int-tool-loop-1",
            agent_id="agent-int-tool-1",
            user_id="user-int-1",
            tenant_id="tenant-int-1",
            memory_manager=None,
        )
    )

    assert result["success"] is True
    assert result["response"] == "Tool execution completed"
    assert len(result["execution_context"].tools_executed) == 1
