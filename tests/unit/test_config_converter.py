"""
Unit tests for ConfigConverter functions.

Tests Phase 3 AgentConfig ↔ Dict conversion logic.
"""

import pytest
from app.engine.config_converter import agent_config_to_dict, dict_to_agent_config_partial
from app.agents.schemas import AgentConfig


class TestAgentConfigToDict:
    """Test conversion from AgentConfig (Pydantic) to Dict."""
    
    def test_basic_conversion(self, sample_agent_config: AgentConfig):
        """AgentConfig → Dict conversion preserves all fields."""
        result = agent_config_to_dict(sample_agent_config)
        
        # Basic fields
        assert isinstance(result, dict)
        assert result["agent_id"] == "test_agent_config"
        assert result["system_prompt"] == "You are a helpful assistant."
    
    def test_llm_config_extraction(self, sample_agent_config: AgentConfig):
        """LLM config properly extracted to dict format."""
        result = agent_config_to_dict(sample_agent_config)
        
        assert result["llm_provider"] == "openai"
        assert result["llm_model"] == "gpt-4-turbo-preview"
        assert result["temperature"] == 0.7
        assert result["max_tokens"] == 2048
        assert result["top_p"] == 0.95
        assert result["frequency_penalty"] == 0.0
        assert result["presence_penalty"] == 0.0
    
    def test_tools_filtering(self, sample_agent_config: AgentConfig):
        """Only enabled tools included in result."""
        result = agent_config_to_dict(sample_agent_config)
        
        tools = result["tools"]
        assert len(tools) == 2  # Only 2 tools enabled (tool_3 is disabled)
        
        # Check enabled tools
        enabled_names = [t["name"] for t in tools]
        assert "generate_report" in enabled_names
        assert "send_notification" in enabled_names
        assert "archive_data" not in enabled_names
    
    def test_tool_config_preservation(self, sample_agent_config: AgentConfig):
        """Tool-specific configs preserved in conversion."""
        result = agent_config_to_dict(sample_agent_config)
        
        tools = {t["name"]: t for t in result["tools"]}
        
        # Check tool configs
        assert tools["generate_report"]["config"]["detailed"] is True
        assert tools["generate_report"]["config"]["format"] == "markdown"
        assert tools["send_notification"]["config"]["channel"] == "email"
    
    def test_memory_config_extraction(self, sample_agent_config: AgentConfig):
        """Memory config properly extracted."""
        result = agent_config_to_dict(sample_agent_config)
        
        memory = result.get("memory", {})
        assert memory["type"] == "conversation"
        assert memory["max_history"] == 10
        assert memory["enable_vector"] is True
    
    def test_conversion_output_type(self, sample_agent_config: AgentConfig):
        """Output is plain dict, not Pydantic model."""
        result = agent_config_to_dict(sample_agent_config)
        
        assert isinstance(result, dict)
        assert not hasattr(result, "model_dump")  # Pydantic methods not present
    
    def test_conversion_is_idempotent(self, sample_agent_config: AgentConfig):
        """Converting twice produces same result."""
        result1 = agent_config_to_dict(sample_agent_config)
        result2 = agent_config_to_dict(sample_agent_config)
        
        # Both dicts should be equal
        assert result1 == result2


class TestDictToAgentConfigPartial:
    """Test dict completion function for backward compatibility."""
    
    def test_empty_dict_gets_defaults(self):
        """Empty dict filled with safe defaults."""
        incomplete = {}
        result = dict_to_agent_config_partial(incomplete)
        
        # Required fields should be present
        assert "system_prompt" in result
        assert "llm_provider" in result
        assert "llm_model" in result
        assert "temperature" in result
        assert "max_tokens" in result
    
    def test_partial_dict_preservation(self):
        """Existing values preserved, missing filled."""
        incomplete = {
            "system_prompt": "Custom prompt",
            "temperature": 0.5,
        }
        result = dict_to_agent_config_partial(incomplete)
        
        # Original values preserved
        assert result["system_prompt"] == "Custom prompt"
        assert result["temperature"] == 0.5
        
        # Missing values filled
        assert "llm_provider" in result
        assert "llm_model" in result
    
    def test_tools_default_to_empty_list(self):
        """Tools default to empty list if not provided."""
        incomplete = {"system_prompt": "Test"}
        result = dict_to_agent_config_partial(incomplete)
        
        assert "tools" in result
        assert isinstance(result["tools"], list)
    
    def test_memory_config_default(self):
        """Memory config filled with defaults."""
        incomplete = {}
        result = dict_to_agent_config_partial(incomplete)
        
        assert "memory" in result
        assert result["memory"]["type"] == "conversation"
        assert result["memory"]["max_history"] >= 0


class TestRoundTripConversion:
    """Test converting AgentConfig → Dict → AgentConfig."""
    
    def test_round_trip_preserves_data(self, sample_agent_config: AgentConfig):
        """Round-trip conversion preserves critical data."""
        # Convert to dict
        dict_form = agent_config_to_dict(sample_agent_config)
        
        # Verify critical fields survived
        assert dict_form["agent_id"] == sample_agent_config.agent_id
        assert dict_form["system_prompt"] == sample_agent_config.system_prompt
        assert dict_form["llm_provider"] == sample_agent_config.llm_config.provider
        assert dict_form["llm_model"] == sample_agent_config.llm_config.model
        
        # Verify tool count correct  (accounting for disabled tools)
        enabled_tools_count = sum(1 for t in sample_agent_config.tools if t.enabled)
        assert len(dict_form["tools"]) == enabled_tools_count


class TestErrorHandling:
    """Test error handling in converters."""
    
    def test_agent_config_to_dict_with_none_fields(self):
        """Handles None fields gracefully."""
        config = AgentConfig(
            agent_id="test",
            version_number="1.0.0",
            system_prompt=None,
            prompts=None,
            llm_config=None,
            tools=[],
            memory_config=None,
        )
        
        # Should not raise, but handle gracefully
        result = agent_config_to_dict(config)
        assert isinstance(result, dict)
    
    def test_dict_to_agent_config_with_extra_fields(self):
        """Ignores unknown fields in input dict."""
        incomplete = {
            "system_prompt": "Test",
            "unknown_field_xyz": "This should be ignored",
            "another_unknown": 12345,
        }
        
        result = dict_to_agent_config_partial(incomplete)
        
        # Should not raise, result should be valid
        assert isinstance(result, dict)
        assert result["system_prompt"] == "Test"


class TestConversionPerformance:
    """Test conversion performance."""
    
    def test_agent_config_to_dict_performance(self, sample_agent_config: AgentConfig):
        """Conversion completes quickly."""
        import time
        
        start = time.perf_counter()
        for _ in range(100):
            agent_config_to_dict(sample_agent_config)
        elapsed = time.perf_counter() - start
        
        # 100 conversions should complete in < 100ms
        assert elapsed < 0.1, f"Conversion too slow: {elapsed}s for 100 iterations"
    
    def test_dict_to_agent_config_partial_performance(self, sample_dict_config: dict):
        """Dict completion is fast."""
        import time
        
        start = time.perf_counter()
        for _ in range(100):
            dict_to_agent_config_partial(sample_dict_config)
        elapsed = time.perf_counter() - start
        
        # 100 completions should be < 50ms
        assert elapsed < 0.05, f"Completion too slow: {elapsed}s for 100 iterations"
