"""
DEPRECATED: This module has been replaced by a complete agent framework.

This file is maintained for backward compatibility only.
Please use the production-ready implementation in agent_engine.py instead.

The new architecture includes:
- Tool Registry: Dynamic tool management (app/tools/)
- LLM Providers: Multi-provider support (app/llm/)
- Memory System: Persistent conversation memory (app/memory/)
- Execution Context: Detailed execution tracking
- Real Agentic Loop: LLM → Tool → LLM iterations

Migration Guide:
    # OLD (this file):
    from app.engine.engine import AgentEngine
    engine = AgentEngine(config)
    result = await engine.execute(user_input, context)
    
    # NEW (use this instead):
    from app.engine import AgentEngine
    engine = AgentEngine()
    result = await engine.execute(
        agent_config=config,
        user_input=user_input,
        execution_id=exec_id,
        agent_id=agent_id,
        user_id=user_id,
        tenant_id=tenant_id,
        memory_manager=memory_mgr  # Optional
    )

See app/engine/agent_engine.py for the production implementation.
See AGENT_FRAMEWORK.md for complete documentation.
"""

# For backward compatibility, import from the new location
from app.engine.agent_engine import AgentEngine

__all__ = ["AgentEngine"]
