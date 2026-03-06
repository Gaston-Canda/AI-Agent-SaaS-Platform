# Phase 3 Step 4: AgentEngine Integration & Execution Pipeline

**Status**: ✅ COMPLETE  
**Date Completed**: 2024  
**Lines of Code**: 450+ (new/modified across 5 files)  
**Components**: 5 (config_converter, AgentEngine, AgentLoader, agents init, workers)

## Overview

Phase 3 Step 4 integrates the dynamic agent configuration system (Phase 3) with the AgentEngine execution engine while maintaining full backward compatibility with Phase 1/2 hardcoded agent configurations.

### Key Achievement

**Execution Pipeline Unified**: AgentEngine now seamlessly accepts both:

- **Phase 3** (Recommended): Pydantic AgentConfig from dynamic database loading
- **Phase 1/2** (Legacy): Dict-based static configuration

### Architecture Pattern: Adapter + Fallback

```
User Request
    ↓
Celery Worker (execute_agent task)
    ↓
Phase 3 AgentLoader ──→ AgentConfig (Pydantic)
    ↓
ConfigConverter ──→ Standardized Dict
    ↓
AgentEngine.execute() ──→ Unified execution
    ↓
Result Storage
```

If Phase 3 unavailable:

```
User Request
    ↓
Celery Worker (execute_agent task)
    ↓
Fall back to Phase 1/2 Agent.config ──→ Dict
    ↓
AgentEngine.execute() ──→ Unified execution
    ↓
Result Storage
```

---

## 1. Configuration Converter Module

**File**: `app/engine/config_converter.py` (NEW)  
**Purpose**: Bridge Pydantic AgentConfig ↔ Dict formats  
**Lines**: 100+

### Function: agent_config_to_dict()

```python
def agent_config_to_dict(config: AgentConfig) -> Dict[str, Any]:
    """
    Convert Phase 3 AgentConfig (Pydantic) to Phase 1/2 Dict format.

    Enables AgentEngine to accept Pydantic models transparently.

    Args:
        config: AgentConfig instance with complete agent setup

    Returns:
        Dict with keys: agent_id, system_prompt, llm_provider, llm_model,
                       temperature, max_tokens, top_p, frequency_penalty,
                       presence_penalty, tools, memory
    """
```

**Conversion Details**:

- Extracts LLM config (provider, model, temperature, max_tokens, penalties)
- Maps Phase 3 AgentToolConfigItem[] → enabled tools only
- Includes per-tool configuration dict
- Extracts and merges prompt configs into system_prompt
- Includes memory configuration

**Example Input** (AgentConfig object):

```python
AgentConfig(
    agent_id="agent_123",
    version_number="1.2.0",
    system_prompt="You are a helpful assistant.",
    llm_config=AgentLLMConfig(
        provider="openai",
        model="gpt-4-turbo-preview",
        temperature=0.7,
        max_tokens=2048,
        top_p=0.95,
        presence_penalty=0.0,
    ),
    tools=[
        AgentToolConfigItem(
            tool_id="tool_1",
            name="generate_report",
            enabled=True,
            config={"detailed": True}
        ),
        AgentToolConfigItem(
            tool_id="tool_2",
            name="send_email",
            enabled=False,
            config={}
        )
    ],
    memory_config=AgentMemoryConfig(
        type="conversation",
        max_history=10,
        enable_vector_memory=True
    )
)
```

**Example Output** (Dict):

```python
{
    "agent_id": "agent_123",
    "system_prompt": "You are a helpful assistant.",
    "llm_provider": "openai",
    "llm_model": "gpt-4-turbo-preview",
    "temperature": 0.7,
    "max_tokens": 2048,
    "top_p": 0.95,
    "frequency_penalty": 0.0,
    "presence_penalty": 0.0,
    "tools": [
        {
            "name": "generate_report",
            "enabled": True,
            "config": {"detailed": True}
        }
    ],
    "memory": {
        "type": "conversation",
        "max_history": 10,
        "enable_vector": True
    }
}
```

### Function: dict_to_agent_config_partial()

```python
def dict_to_agent_config_partial(config_dict: Dict) -> Dict[str, Any]:
    """
    Ensure all Phase 1/2 Dict config fields are present.

    Fills missing fields with safe defaults for backward compatibility.
    Used when Agent.config dict is incomplete.

    Args:
        config_dict: Incomplete Phase 1/2 config dict

    Returns:
        Complete config dict with all required fields
    """
```

**Purpose**: Guarantee Phase 1/2 configs have all keys needed by AgentEngine

---

## 2. AgentEngine Updates

**File**: `app/engine/agent_engine.py` (MODIFIED)  
**Changes**: Type hints, docstring, auto-conversion logic

### Updated execute() Signature

```python
async def execute(
    self,
    agent_config: Union[Dict[str, Any], "AgentConfig"],  # ← Now accepts both
    user_input: str,
    execution_id: str,
    agent_id: str,
    user_id: str,
    tenant_id: str,
    memory_manager: Optional[MemoryManager] = None,
    max_tool_loops: int = 5,
    **kwargs
) -> Dict[str, Any]:
```

**Key Change**: Type hint changed from `Dict[str, Any]` to `Union[Dict[str, Any], "AgentConfig"]`

### Auto-Conversion Logic

At method start:

```python
# If AgentConfig provided, convert to Dict
if not isinstance(agent_config, dict):
    from app.engine.config_converter import agent_config_to_dict
    agent_config = agent_config_to_dict(agent_config)

# Rest of execute() uses agent_config as Dict (unchanged)
```

**Transparency**: Rest of AgentEngine code unchanged—no breaking modifications

---

## 3. AgentLoader Sync Wrapper

**File**: `app/agents/agent_loader.py` (MODIFIED)  
**Addition**: load_agent_sync() function (70+ lines)

### Function: load_agent_sync()

```python
def load_agent_sync(
    db: Session,
    agent_id: str,
    tenant_id: str
) -> Optional[AgentConfig]:
    """
    Synchronously call async AgentLoader for use in sync contexts (Celery workers).

    Creates new event loop to run async code from sync code.
    Properly handles cleanup even on exception.

    Args:
        db: SQLAlchemy Session
        agent_id: Agent ID
        tenant_id: Tenant ID

    Returns:
        AgentConfig if found and valid, None if not Phase 3 agent

    Raises:
        ValidationError: If agent config invalid
        ResourceNotFoundError: If agent not found
        PermissionDeniedError: If tenant access denied
        ConflictError: If versioning conflict
    """
```

**Implementation**:

1. Create new event loop
2. Set it as current loop
3. Run async load_agent() to completion
4. Return result
5. Always close loop in finally block

**Why Needed**:

- AgentLoader.load_agent() is async
- Celery workers are sync
- Need bridge between sync↔async contexts

---

## 4. Worker Task Integration

**File**: `app/workers/tasks.py` (MODIFIED)  
**New Logic**: Phase 3 + Phase 1/2 dual execution path  
**Lines Modified**: 50+

### Module Docstring

Updated to document both configurations:

```python
"""
Celery worker tasks for executing agents.

Supports both agent configuration models:
- Phase 3 (Recommended): Dynamic from AgentLoader
- Phase 1/2 (Legacy): Static from Agent.config
"""
```

### execute_agent() Function Updates

#### New Imports

```python
from app.agents import load_agent_sync
from app.core.exceptions import (
    ValidationError,
    ResourceNotFoundError,
    PermissionDeniedError,
    ConflictError
)
```

#### Phase 3: Dynamic Configuration Loading

```python
# Try to load via AgentLoader (Phase 3)
agent_config = None
try:
    logger.log_execution(
        "Attempting Phase 3 dynamic configuration load",
        {"execution_id": execution_id, "agent_id": agent_id}
    )

    agent_config = load_agent_sync(db, agent_id, tenant_id)

    if agent_config:
        logger.log_execution(
            "Phase 3 configuration loaded successfully",
            {
                "execution_id": execution_id,
                "version": agent_config.version_number,
                "tools_count": len(agent_config.tools)
            }
        )
except (ValidationError, ResourceNotFoundError, ...) as e:
    logger.log_execution(
        f"Phase 3 load failed, falling back to Phase 1/2: {str(e)}",
        {"execution_id": execution_id, "agent_id": agent_id}
    )
    agent_config = None
except Exception as e:
    logger.log_error(f"Unexpected error: {str(e)}", ...)
    agent_config = None
```

**Logging**: Each attempt is logged for audit trail and debugging

#### Phase 1/2: Fallback Configuration

```python
# If Phase 3 unavailable, use Phase 1/2
if not agent_config:
    logger.log_execution(
        "Using Phase 1/2 configuration",
        {"execution_id": execution_id, "agent_id": agent_id}
    )

    agent_config = {
        "agent_id": agent.id,
        "system_prompt": agent.config.get("system_prompt", "You are a helpful assistant."),
        "llm_provider": agent.config.get("llm_provider", "openai"),
        "llm_model": agent.config.get("llm_model", "gpt-4-turbo-preview"),
        "temperature": agent.config.get("temperature", 0.7),
        "max_tokens": agent.config.get("max_tokens", 2048),
        "tools": agent.config.get("tools", []),
    }
```

**Fallback Strategy**: Build Dict from Agent.config if Phase 3 unavailable

#### AgentEngine Execution (Unified)

```python
# Initialize memory manager
memory_manager = MemoryManager(memory_id=execution_id)

# Initialize engine
engine = AgentEngine()

# Run async execution
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

try:
    result = loop.run_until_complete(
        engine.execute(
            agent_config=agent_config,  # ← Accepts both Dict and AgentConfig
            user_input=input_data.get("message", ""),
            execution_id=execution_id,
            agent_id=agent_id,
            user_id=user_id,
            tenant_id=tenant_id,
            memory_manager=memory_manager,
            max_tool_loops=5,
        )
    )
finally:
    loop.close()
```

**Key Point**: Same engine.execute() call handles both config types transparently

#### Result Storage (Unified)

Both config paths store results identically:

```python
if result["success"]:
    execution.status = ExecutionStatus.COMPLETED
    execution.output_data = {
        "response": result["response"],
        "success": True,
    }
    execution.execution_time_ms = execution_time_ms
    execution.completed_at = datetime.utcnow()

    # Store execution logs
    ctx = result["execution_context"]
    for step in ctx.steps:
        log = ExecutionLog(...)
        db.add(log)

    # Track usage
    usage = AgentUsage(
        tenant_id=tenant_id,
        agent_id=agent_id,
        execution_id=execution_id,
        input_tokens=ctx.prompt_tokens,
        output_tokens=ctx.completion_tokens,
        model_used=agent_config.get("llm_model"),
        cost_usd=ctx.total_cost_usd,
    )
    db.add(usage)
else:
    execution.status = ExecutionStatus.FAILED
    execution.error_message = result.get("error", "Unknown error")
    # ...
```

---

## 5. Agent Exports Update

**File**: `app/agents/__init__.py` (MODIFIED)

### Added Export

```python
from app.agents.agent_loader import (
    AgentLoader,
    get_agent_loader,
    load_agent_sync,  # ← NEW
)
```

**Purpose**: Makes `load_agent_sync` available for import in workers module

---

## Execution Flow Diagram

### Phase 3 Configuration Path (Recommended)

```
User Request
    ↓
Celery Worker (execute_agent)
    ├─ Load Agent from DB
    ├─ Try AgentLoader.load_agent_sync(db, agent_id, tenant_id)
    │  ├─ Query AgentVersion (active version)
    │  ├─ Query AgentPrompt, AgentTool configurations
    │  └─ Return AgentConfig (Pydantic model)
    ├─ ConfigConverter: AgentConfig → Dict
    ├─ MemoryManager setup
    ├─ AgentEngine.execute(agent_config, ...)
    │  └─ isinstance(AgentConfig) → auto-convert to Dict
    ├─ Execution loop (tools, streaming, etc)
    ├─ Store ExecutionLog, AgentUsage
    └─ Return result
```

### Phase 1/2 Fallback Path

```
User Request
    ↓
Celery Worker (execute_agent)
    ├─ Load Agent from DB
    ├─ Try AgentLoader.load_agent_sync()
    │  └─ Exception or returns None
    ├─ Build agent_config Dict from Agent.config
    │  └─ Dict keys: system_prompt, llm_provider, llm_model, tools, etc
    ├─ MemoryManager setup
    ├─ AgentEngine.execute(agent_config, ...)
    │  └─ Already Dict, no conversion needed
    ├─ Execution loop (tools, streaming, etc)
    ├─ Store ExecutionLog, AgentUsage
    └─ Return result
```

---

## Backward Compatibility Guarantees

### 1. Zero Breaking Changes

- Existing Phase 1/2 agents continue working without modification
- Agent.config dict format unchanged
- AgentEngine API backwards compatible (accepts Dict as before)

### 2. Graceful Degradation

If Phase 3 config invalid:

1. Exception caught with specific error type
2. Logged with full context
3. Automatically falls back to Phase 1/2
4. Execution continues normally

### 3. Coexistence

Both agent types can coexist in same database:

- Phase 3 agents: Have AgentVersion record
- Phase 1/2 agents: No AgentVersion, use static Agent.config
- Worker detects automatically and routes correctly

### 4. No Migration Required

Existing agents work as-is:

```python
# Phase 1/2 Agent (existing, no changes needed)
agent = Agent(
    id="agent_legacy",
    name="Legacy Agent",
    tenant_id="tenant123",
    config={  # Static dict
        "system_prompt": "...",
        "llm_provider": "openai",
        "llm_model": "gpt-4",
        "tools": [...]
    }
)

# Phase 3 Agent (new, coexists peacefully)
agent = Agent(
    id="agent_v3",
    name="Dynamic Agent",
    tenant_id="tenant123",
    config={...}  # Optional placeholder
)
# Real config loaded from AgentVersion table
```

---

## Error Handling

### Phase 3 Load Failures

```python
try:
    agent_config = load_agent_sync(db, agent_id, tenant_id)
except ValidationError as e:
    # Config data invalid
    logger.log_execution(f"Phase 3 validation failed: {e}", ...)
    agent_config = None
except ResourceNotFoundError as e:
    # Agent version not found
    logger.log_execution(f"Agent version not found: {e}", ...)
    agent_config = None
except PermissionDeniedError as e:
    # Tenant access denied
    logger.log_error(f"Permission denied: {e}", ...)
    agent_config = None
except ConflictError as e:
    # Version conflict
    logger.log_error(f"Version conflict: {e}", ...)
    agent_config = None
except Exception as e:
    # Unexpected error
    logger.log_error(f"Unexpected error in Phase 3: {e}", ...)
    agent_config = None
```

All failures → Fallback to Phase 1/2 (no execution failure)

### AgentEngine Execution Failures

```python
if result["success"]:
    # ... store success results
else:
    execution.status = ExecutionStatus.FAILED
    execution.error_message = result.get("error")
    logger.log_error(f"Agent execution failed: {error}", ...)
```

Both config paths handle execution errors identically

---

## Testing Strategy

### Unit Tests

#### 1. ConfigConverter Tests

```python
def test_agent_config_to_dict():
    """AgentConfig → Dict conversion."""
    config = AgentConfig(...)
    result = agent_config_to_dict(config)
    assert isinstance(result, dict)
    assert "llm_model" in result
    assert "tools" in result

def test_dict_to_agent_config_partial():
    """Incomplete dict → filled dict."""
    incomplete = {"system_prompt": "..."}
    result = dict_to_agent_config_partial(incomplete)
    assert "temperature" in result
    assert "max_tokens" in result
```

#### 2. AgentLoader Sync Tests

```python
def test_load_agent_sync_success():
    """load_agent_sync returns AgentConfig."""
    db = SessionLocal()
    config = load_agent_sync(db, "agent1", "tenant1")
    assert isinstance(config, AgentConfig)
    assert config.agent_id == "agent1"

def test_load_agent_sync_fallback():
    """load_agent_sync returns None for Phase 1/2 agent."""
    db = SessionLocal()
    config = load_agent_sync(db, "legacy_agent", "tenant1")
    assert config is None
```

#### 3. AgentEngine Type Tests

```python
@pytest.mark.asyncio
async def test_engine_accepts_dict():
    """AgentEngine.execute() accepts Dict."""
    engine = AgentEngine()
    config = {"llm_model": "gpt-4", ...}
    result = await engine.execute(agent_config=config, ...)
    assert result["success"]

@pytest.mark.asyncio
async def test_engine_accepts_agent_config():
    """AgentEngine.execute() accepts AgentConfig."""
    engine = AgentEngine()
    config = AgentConfig(...)
    result = await engine.execute(agent_config=config, ...)
    assert result["success"]
```

#### 4. Worker Task Tests

```python
def test_execute_agent_phase3():
    """Worker task uses Phase 3 if available."""
    result = execute_agent(id="exec1", ...)
    assert result["success"]
    # Verify Phase 3 was used via logs

def test_execute_agent_fallback():
    """Worker task falls back to Phase 1/2."""
    result = execute_agent(id="exec1", ...)
    assert result["success"]
    # Verify fallback path used via logs
```

### Integration Tests

#### 1. Full Execution Cycle (Phase 3)

```python
@pytest.mark.asyncio
async def test_phase3_execution_end_to_end():
    """Full execution: Agent creation → Config loading → Execution."""
    # Create Phase 3 agent with versions and tools
    agent = create_test_phase3_agent(db)

    # Enqueue execution
    result = execute_agent(
        execution_id="exec1",
        agent_id=agent.id,
        tenant_id="tenant1",
        user_id="user1",
        input_data={"message": "Hello"}
    )

    # Verify result stored
    execution = db.query(AgentExecution).filter_by(id="exec1").first()
    assert execution.status == ExecutionStatus.COMPLETED
    assert execution.output_data["success"]
```

#### 2. Full Execution Cycle (Phase 1/2)

```python
@pytest.mark.asyncio
async def test_phase12_execution_end_to_end():
    """Full execution: Legacy agent → Fallback path → Execution."""
    # Create Phase 1/2 agent (static config)
    agent = create_test_legacy_agent(db)

    # Enqueue execution
    result = execute_agent(
        execution_id="exec2",
        agent_id=agent.id,
        tenant_id="tenant1",
        user_id="user1",
        input_data={"message": "Hello"}
    )

    # Verify result stored
    execution = db.query(AgentExecution).filter_by(id="exec2").first()
    assert execution.status == ExecutionStatus.COMPLETED
```

#### 3. Coexistence Test

```python
@pytest.mark.asyncio
async def test_phase3_and_phase12_coexist():
    """Both agent types execute correctly in same worker."""
    phase3_agent = create_test_phase3_agent(db)
    phase12_agent = create_test_legacy_agent(db)

    # Execute both
    result3 = execute_agent(
        execution_id="exec3",
        agent_id=phase3_agent.id,
        tenant_id="tenant1",
        user_id="user1",
        input_data={"message": "Test"}
    )

    result12 = execute_agent(
        execution_id="exec4",
        agent_id=phase12_agent.id,
        tenant_id="tenant1",
        user_id="user1",
        input_data={"message": "Test"}
    )

    assert result3["success"]
    assert result12["success"]
```

#### 4. Fallback on Error Test

```python
@pytest.mark.asyncio
async def test_fallback_on_phase3_error():
    """Fallback triggered on Phase 3 validation error."""
    # Create agent with invalid Phase 3 config
    agent = create_test_agent_with_invalid_version(db)

    # Execute should not fail, should use fallback
    result = execute_agent(
        execution_id="exec5",
        agent_id=agent.id,
        tenant_id="tenant1",
        user_id="user1",
        input_data={"message": "Test"}
    )

    assert result["success"]
    # Verify fallback path used via execution logs
```

### Performance Tests

#### 1. Config Load Performance

```python
def test_load_agent_sync_performance():
    """Phase 3 config load < 100ms."""
    db = SessionLocal()

    start = time.time()
    config = load_agent_sync(db, "agent1", "tenant1")
    elapsed = time.time() - start

    assert elapsed < 0.1  # 100ms target
```

#### 2. Conversion Performance

```python
def test_conversion_performance():
    """AgentConfig → Dict conversion < 10ms."""
    config = AgentConfig(...)

    start = time.time()
    result = agent_config_to_dict(config)
    elapsed = time.time() - start

    assert elapsed < 0.01  # 10ms target
```

#### 3. Execution Throughput

```python
@pytest.mark.asyncio
async def test_execution_throughput():
    """10 concurrent executions complete without blocking."""
    tasks = [
        execute_agent(
            execution_id=f"exec{i}",
            agent_id="agent1",
            tenant_id="tenant1",
            user_id="user1",
            input_data={"message": f"Test {i}"}
        )
        for i in range(10)
    ]

    results = await asyncio.gather(*tasks)
    assert all(r["success"] for r in results)
```

---

## Monitoring & Logging

### Execution Logging

Each execution logs:

1. Config load attempt (Phase 3)
2. Config load result (success/failure/fallback)
3. Execution start
4. Tool calls
5. Execution completion
6. Resource usage (tokens, time, cost)

### Log Examples

**Phase 3 Success**:

```log
[INFO] Attempting Phase 3 dynamic configuration load
       execution_id=exec123 agent_id=agent1
[INFO] Phase 3 configuration loaded successfully
       execution_id=exec123 version=1.2.0 tools_count=3
[INFO] Agent execution completed
       execution_id=exec123 duration_ms=2450 tokens_used=1250
```

**Phase 3 → Fallback**:

```log
[INFO] Attempting Phase 3 dynamic configuration load
       execution_id=exec456 agent_id=agent2
[INFO] Phase 3 load failed, falling back to Phase 1/2: ResourceNotFoundError
       execution_id=exec456 agent_id=agent2
[INFO] Using Phase 1/2 configuration
       execution_id=exec456 agent_id=agent2
[INFO] Agent execution completed
       execution_id=exec456 duration_ms=1950
```

### Monitoring Metrics

Track per agent:

- `phase3_load_success_rate`: % of Phase 3 configs loaded successfully
- `phase3_fallback_rate`: % of Phase 3 attempts that fell back
- `avg_config_load_time_ms`: Time to load config
- `avg_execution_time_ms`: Total execution time (config + engine)
- `config_conversion_time_ms`: PYDANTIC → DICT conversion time

---

## Summary

### What's New

1. **ConfigConverter**: Pydantic ↔ Dict bridge (100+ lines)
2. **AgentEngine Update**: Accepts Union[Dict, AgentConfig] (20 lines)
3. **AgentLoader Sync**: Event loop wrapper for sync contexts (70 lines)
4. **Worker Integration**: Phase 3 + Phase 1/2 dual-path execution (60+ lines)
5. **Exports**: Updated agent module to export load_agent_sync (2 lines)

### What's Better

- ✅ Dynamic agent configuration now executes seamlessly
- ✅ Phase 1/2 agents still work without modification
- ✅ No breaking changes to existing APIs
- ✅ Automatic fallback on any error (execution never fails due to config)
- ✅ Complete audit trail via structured logging
- ✅ Transparent type handling (Pydantic ↔ Dict)

### What's Next

- End-to-end testing via Phase 3 Step 5
- Performance optimization (config caching, batch loading)
- Phase 3 Step 6: Multi-agent orchestration
