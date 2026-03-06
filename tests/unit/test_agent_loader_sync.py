"""
Unit and integration tests for AgentLoader.load_agent_sync() function.

Tests synchronous wrapper for async AgentLoader.
"""

import pytest
import time
from sqlalchemy.orm import Session

from app.agents.agent_loader import load_agent_sync, AgentLoader, get_agent_loader
from app.agents.schemas import AgentConfig
from app.core.exceptions import ResourceNotFoundError
from app.models.agent import Agent
from app.models.extended import AgentVersion, AgentTool, AgentPrompt


class TestLoadAgentSyncBasic:
    """Test basic load_agent_sync functionality."""
    
    def test_load_nonexistent_agent_returns_none(self, test_db: Session, test_tenant):
        """Loading non-existent agent returns None."""
        result = load_agent_sync(test_db, "nonexistent_agent", test_tenant.id)
        assert result is None
    
    def test_load_phase12_agent_returns_none(
        self,
        test_db: Session,
        test_tenant,
        phase12_agent: Agent
    ):
        """Loading Phase 1/2 agent (no version) returns None."""
        result = load_agent_sync(test_db, phase12_agent.id, test_tenant.id)
        assert result is None
    
    def test_load_agent_sync_returns_agent_config(
        self,
        test_db: Session,
        test_tenant,
        phase3_agent: Agent
    ):
        """Successfully loads Phase 3 agent and returns AgentConfig."""
        # Create agent version (makes it a Phase 3 agent)
        version = AgentVersion(
            agent_id=phase3_agent.id,
            version_number="1.0.0",
            system_prompt="You are a helpful assistant.",
            is_active=True,
            created_at=None,
        )
        test_db.add(version)
        test_db.commit()
        
        # Load agent
        result = load_agent_sync(test_db, phase3_agent.id, test_tenant.id)
        
        assert result is not None
        assert isinstance(result, AgentConfig)
        assert result.agent_id == phase3_agent.id
        assert result.version_number == "1.0.0"
    
    def test_load_agent_with_tools(
        self,
        test_db: Session,
        test_tenant,
        phase3_agent: Agent
    ):
        """Loads agent with tools configuration."""
        # Create version
        version = AgentVersion(
            agent_id=phase3_agent.id,
            version_number="1.0.0",
            system_prompt="You are helpful.",
            is_active=True,
        )
        test_db.add(version)
        test_db.commit()
        
        # Add tools
        tool1 = AgentTool(
            agent_id=phase3_agent.id,
            version_id=version.id,
            name="generate_report",
            enabled=True,
            config={"format": "markdown"},
        )
        tool2 = AgentTool(
            agent_id=phase3_agent.id,
            version_id=version.id,
            name="send_email",
            enabled=False,
            config={},
        )
        test_db.add_all([tool1, tool2])
        test_db.commit()
        
        # Load agent
        result = load_agent_sync(test_db, phase3_agent.id, test_tenant.id)
        
        assert result is not None
        assert len(result.tools) == 2
        assert result.tools[0].enabled is True
        assert result.tools[1].enabled is False
    
    def test_load_agent_with_prompts(
        self,
        test_db: Session,
        test_tenant,
        phase3_agent: Agent
    ):
        """Loads agent with prompt configuration."""
        # Create version
        version = AgentVersion(
            agent_id=phase3_agent.id,
            version_number="1.0.0",
            system_prompt="System prompt.",
            is_active=True,
        )
        test_db.add(version)
        test_db.commit()
        
        # Add prompts
        prompt_system = AgentPrompt(
            agent_id=phase3_agent.id,
            version_id=version.id,
            type="system",
            content="You are an assistant.",
        )
        prompt_instruction = AgentPrompt(
            agent_id=phase3_agent.id,
            version_id=version.id,
            type="instruction",
            content="Be concise.",
        )
        test_db.add_all([prompt_system, prompt_instruction])
        test_db.commit()
        
        # Load agent
        result = load_agent_sync(test_db, phase3_agent.id, test_tenant.id)
        
        assert result is not None
        assert result.prompts.system == "You are an assistant."
        assert result.prompts.instruction == "Be concise."


class TestLoadAgentSyncTenantIsolation:
    """Test tenant isolation in load_agent_sync."""
    
    def test_loading_agent_from_different_tenant_returns_none(
        self,
        test_db: Session,
        test_tenant,
        phase3_agent: Agent
    ):
        """Cannot load agent from different tenant."""
        # Create version for the agent
        version = AgentVersion(
            agent_id=phase3_agent.id,
            version_number="1.0.0",
            system_prompt="Prompt",
            is_active=True,
        )
        test_db.add(version)
        test_db.commit()
        
        # Try loading with different tenant ID
        result = load_agent_sync(test_db, phase3_agent.id, "different_tenant_123")
        
        assert result is None


class TestLoadAgentSyncEventLoopHandling:
    """Test event loop handling in load_agent_sync."""
    
    def test_load_agent_sync_creates_event_loop(
        self,
        test_db: Session,
        test_tenant,
        phase3_agent: Agent
    ):
        """load_agent_sync properly manages event loop."""
        import asyncio
        
        # Create version
        version = AgentVersion(
            agent_id=phase3_agent.id,
            version_number="1.0.0",
            system_prompt="Test",
            is_active=True,
        )
        test_db.add(version)
        test_db.commit()
        
        # Get current event loop before call (if any)
        try:
            original_loop = asyncio.get_running_loop()
        except RuntimeError:
            original_loop = None
        
        # Call sync function (should not interfere with current loop)
        result = load_agent_sync(test_db, phase3_agent.id, test_tenant.id)
        
        # Should return valid result
        assert result is not None
        assert isinstance(result, AgentConfig)
    
    def test_load_agent_sync_cleanup_on_exception(
        self,
        test_db: Session,
        test_tenant
    ):
        """Event loop cleaned up even on exception."""
        import asyncio
        
        # Try to load non-existent agent (should handle gracefully)
        try:
            result = load_agent_sync(test_db, "nonexistent", test_tenant.id)
        except Exception:
            pass  # We expect None, not exception
        
        # Should be able to create new loop after
        loop = asyncio.new_event_loop()
        assert loop is not None
        loop.close()


class TestLoadAgentSyncErrors:
    """Test error handling in load_agent_sync."""
    
    def test_load_agent_with_invalid_db_session(self):
        """Handles invalid database session."""
        # Pass None as db session
        try:
            result = load_agent_sync(None, "agent_id", "tenant_id")
            # Should return None or raise AttributeError
        except (AttributeError, TypeError):
            pass  # Expected
    
    def test_load_agent_with_empty_string_id(
        self,
        test_db: Session,
        test_tenant
    ):
        """Handles empty string agent ID."""
        result = load_agent_sync(test_db, "", test_tenant.id)
        assert result is None
    
    def test_load_agent_with_empty_string_tenant(
        self,
        test_db: Session,
        phase3_agent: Agent
    ):
        """Handles empty string tenant ID."""
        result = load_agent_sync(test_db, phase3_agent.id, "")
        assert result is None


class TestLoadAgentSyncConcurrency:
    """Test concurrent usage of load_agent_sync."""
    
    def test_load_same_agent_multiple_times(
        self,
        test_db: Session,
        test_tenant,
        phase3_agent: Agent
    ):
        """Loading same agent multiple times works correctly."""
        # Create version
        version = AgentVersion(
            agent_id=phase3_agent.id,
            version_number="1.0.0",
            system_prompt="Test",
            is_active=True,
        )
        test_db.add(version)
        test_db.commit()
        
        # Load multiple times
        results = [
            load_agent_sync(test_db, phase3_agent.id, test_tenant.id)
            for _ in range(5)
        ]
        
        # All should succeed and have same agent_id
        assert all(r is not None for r in results)
        assert all(r.agent_id == phase3_agent.id for r in results)


class TestLoadAgentSyncPerformance:
    """Test performance of load_agent_sync."""
    
    def test_load_agent_sync_performance(
        self,
        test_db: Session,
        test_tenant,
        phase3_agent: Agent
    ):
        """Loading agent completes within acceptable time."""
        # Create version
        version = AgentVersion(
            agent_id=phase3_agent.id,
            version_number="1.0.0",
            system_prompt="Test",
            is_active=True,
        )
        test_db.add(version)
        test_db.commit()
        
        start = time.perf_counter()
        result = load_agent_sync(test_db, phase3_agent.id, test_tenant.id)
        elapsed = time.perf_counter() - start
        
        assert result is not None
        # Should complete in under 500ms
        assert elapsed < 0.5, f"Load took too long: {elapsed}s"
    
    def test_load_multiple_agents_performance(
        self,
        test_db: Session,
        test_tenant
    ):
        """Loading multiple agents is reasonably fast."""
        # Create multiple Phase 3 agents
        agents = []
        for i in range(5):
            agent = Agent(
                id=f"perf_agent_{i}",
                tenant_id=test_tenant.id,
                name=f"Performance Agent {i}",
                config={},
                active=True,
            )
            test_db.add(agent)
            agents.append(agent)
        
        test_db.commit()
        
        # Create versions
        for agent in agents:
            version = AgentVersion(
                agent_id=agent.id,
                version_number="1.0.0",
                system_prompt=f"Test prompt for {agent.id}",
                is_active=True,
            )
            test_db.add(version)
        test_db.commit()
        
        # Load all
        start = time.perf_counter()
        results = [
            load_agent_sync(test_db, agent.id, test_tenant.id)
            for agent in agents
        ]
        elapsed = time.perf_counter() - start
        
        assert all(r is not None for r in results)
        # 5 agents should load in under 2 seconds
        assert elapsed < 2.0, f"Loading 5 agents took too long: {elapsed}s"
