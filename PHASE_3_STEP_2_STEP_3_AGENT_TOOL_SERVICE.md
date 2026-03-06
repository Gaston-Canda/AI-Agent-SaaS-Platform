# Phase 3 Step 2.3: AgentToolService Implementation

## Overview

**AgentToolService** manages tool configuration per agent version. It is NOT a tool executor—it only manages which tools are assigned to each agent version and how they're configured.

The critical design principle: **Validate against ToolRegistry, but never execute tools.**

## Architecture

### Service Location
```
app/agents/
├── __init__.py                    # Exports all services and schemas
├── schemas.py                     # Pydantic models
├── agent_service.py               # CRUD for agents
├── agent_version_service.py       # Version management
└── agent_tool_service.py          # Tool configuration (NEW)
```

### ToolRegistry Integration

The global **ToolRegistry** contains all available tools in the system:

```python
from app.tools.tool_registry import ToolRegistry

# ToolRegistry is a class registry with static methods
ToolRegistry.list_tools()           # ["google_search", "calculator", "http_request"]
ToolRegistry.get_tool("google_search")  # Returns BaseTool instance
```

**AgentToolService** validates and references this registry but never calls tool.execute():

```python
# ✓ Correct: Validate tool exists
if not ToolRegistry.get_tool(tool_name):
    raise ValidationError("Tool not found in registry")

# ✗ Wrong: Never execute tools
# tool.execute(...)  ← This is AgentEngine's job
```

### Dependency Injection Pattern

```python
async def add_tool_to_version(
    self,
    db: Session,           # ← Database session (injected)
    tenant_id: str,        # ← Always filter by tenant_id
    agent_id: str,
    version_id: str,
    tool_name: str,        # ← Validated against ToolRegistry
    tool_config: Optional[dict] = None,
) -> AgentToolResponse:   # ← Returns Pydantic, not ORM
    ...
```

## Data Models

### AgentToolResponse (Pydantic Schema)

Returned by all operations:

```python
class AgentToolResponse(BaseModel):
    id: str                    # Assignment ID (UUID)
    agent_version_id: str      # Version it belongs to
    tool_name: str             # Name of tool
    enabled: bool              # Is tool enabled in this version?
    tool_config: dict          # Tool-specific settings
    created_at: datetime       # When assigned
    updated_at: datetime       # Last config update
```

### AddToolRequest (Pydantic Schema)

Request to add tool:

```python
class AddToolRequest(BaseModel):
    tool_name: str             # Required, must exist in ToolRegistry
    tool_config: dict          # Optional (defaults to {})
```

### UpdateToolConfigRequest (Pydantic Schema)

Request to update tool config:

```python
class UpdateToolConfigRequest(BaseModel):
    tool_config: dict          # New configuration
```

### ListAgentToolsResponse (Pydantic Schema)

List of tools for a version:

```python
class ListAgentToolsResponse(BaseModel):
    items: list[AgentToolResponse]  # All tools
    total: int                      # Total count
    enabled_count: int              # How many are enabled
```

### Database Table

```sql
CREATE TABLE agent_tools (
    id VARCHAR(36) PRIMARY KEY,
    agent_version_id VARCHAR(36) NOT NULL REFERENCES agent_versions(id),
    tool_name VARCHAR(100) NOT NULL,         -- e.g., "google_search"
    enabled BOOLEAN DEFAULT TRUE,             -- Is tool enabled?
    tool_config JSON DEFAULT '{}',            -- {"timeout": 30, "retry": 3}
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes for performance
    INDEX idx_agent_tool_version_id (agent_version_id),
    INDEX idx_agent_tool_name (agent_version_id, tool_name),
    INDEX idx_agent_tool_enabled (agent_version_id, enabled),
);
```

## Method Reference

### 1. add_tool_to_version() - Assign tool to version

```python
async def add_tool_to_version(
    db: Session,
    tenant_id: str,
    agent_id: str,
    version_id: str,
    tool_name: str,
    tool_config: Optional[dict] = None,
) -> AgentToolResponse
```

**Purpose**: Assign a tool to an agent version with optional configuration.

**Validation**:
- Version exists and belongs to tenant
- Tool name is not empty
- **Tool exists in ToolRegistry** ← CRITICAL
- Tool not already assigned to this version

**Behavior**:
- New tools are ENABLED by default
- Stores tool configuration as JSON
- Returns the assignment details

**Example Usage**:

```python
from app.agents import AgentToolService

service = AgentToolService()

# Add google_search tool
tool_response = await service.add_tool_to_version(
    db=db_session,
    tenant_id="tenant_123",
    agent_id="agent_456",
    version_id="version_789",
    tool_name="google_search",
    tool_config={
        "timeout": 30,
        "max_results": 5,
    }
)
# Result: tool_response.enabled == True

# Add another tool without config
await service.add_tool_to_version(
    db=db_session,
    tenant_id="tenant_123",
    agent_id="agent_456",
    version_id="version_789",
    tool_name="calculator",
    tool_config={}
)
```

**ToolRegistry Validation Flow**:

```python
# In add_tool_to_version():

1. Validate version exists
2. Check tool_name is not empty
3. Query ToolRegistry.get_tool(tool_name)  ← Validates tool exists
   
   If tool not found:
       Available = ["google_search", "calculator", "http_request"]
       raise ValidationError(
           "Tool 'wikipedia_search' not found in ToolRegistry. "
           "Available tools: google_search, calculator, http_request"
       )
   
4. Check if tool already assigned to this version
   If yes: raise ValidationError("Tool already assigned")
   
5. Create AgentTool record (enabled=True by default)
6. Commit + refresh
7. Return AgentToolResponse
```

---

### 2. remove_tool_from_version() - Unassign tool

```python
async def remove_tool_from_version(
    db: Session,
    tenant_id: str,
    agent_id: str,
    version_id: str,
    tool_name: str,
) -> None
```

**Purpose**: Permanently remove a tool from a version.

**Behavior**:
- Hard delete (no soft delete for tools)
- Completely removes the assignment
- Does NOT create new version automatically

**Lifecycle**:
- If tool is causing issues: use `enable_tool(enabled=False)` instead
- If tool no longer needed: use `remove_tool_from_version()`
- If need different tools: create new version

**Example Usage**:

```python
# Remove a problematic tool
await service.remove_tool_from_version(
    db=db_session,
    tenant_id="tenant_123",
    agent_id="agent_456",
    version_id="version_789",
    tool_name="buggy_tool",
)

# Tool is now removed from this version
# Other versions still have it (separate assignments)
```

---

### 3. enable_tool() - Toggle tool enabled status

```python
async def enable_tool(
    db: Session,
    tenant_id: str,
    agent_id: str,
    version_id: str,
    tool_name: str,
    enabled: bool = True,
) -> AgentToolResponse
```

**Purpose**: Enable or disable a tool without removing it.

**Behavior**:
- Only changes `enabled` flag
- Does NOT remove the assignment
- Tool can be re-enabled later
- AgentEngine only uses enabled tools

**Workflow Example**:

```
1. add_tool_to_version(..., "google_search", ...)
   enabled=True (default)
   
2. User reports: google_search times out often
   
3. Temporarily disable:
   await service.enable_tool(
       ..., "google_search", enabled=False
   )
   
4. Agent executes without google_search
   
5. Fix deployed, re-enable:
   await service.enable_tool(
       ..., "google_search", enabled=True
   )
   
6. Or permanently remove:
   await service.remove_tool_from_version(...)
```

**Example Usage**:

```python
# Disable a problematic tool temporarily
await service.enable_tool(
    db=db_session,
    tenant_id="tenant_123",
    agent_id="agent_456",
    version_id="version_789",
    tool_name="google_search",
    enabled=False  # Disable
)

# Later, re-enable it
await service.enable_tool(
    db=db_session,
    tenant_id="tenant_123",
    agent_id="agent_456",
    version_id="version_789",
    tool_name="google_search",
    enabled=True  # Enable
)
```

---

### 4. update_tool_config() - Update tool configuration

```python
async def update_tool_config(
    db: Session,
    tenant_id: str,
    agent_id: str,
    version_id: str,
    tool_name: str,
    tool_config: dict,
) -> AgentToolResponse
```

**Purpose**: Update tool-specific configuration.

**Important**: Does NOT validate configuration parameters. AgentEngine is responsible for validation during execution.

**Configuration Examples**:

```python
# google_search tool
{
    "timeout": 30,
    "max_results": 5,
    "language": "en"
}

# http_request tool
{
    "timeout": 60,
    "max_redirects": 5,
    "allowed_domains": ["api.example.com"],
    "rate_limit": 100  # requests per minute
}

# database_query tool
{
    "max_rows": 1000,
    "readonly": True,
    "max_execution_time": 30  # seconds
}
```

**Workflow**:

```python
# Initial config
await service.add_tool_to_version(
    ..., "google_search",
    tool_config={"timeout": 30, "max_results": 5}
)

# Later: Change timeout from 30 to 60 seconds
await service.update_tool_config(
    db=db_session,
    tenant_id="tenant_123",
    agent_id="agent_456",
    version_id="version_789",
    tool_name="google_search",
    tool_config={"timeout": 60, "max_results": 5}  # Updated
)

# Or clear all config
await service.update_tool_config(
    ..., "google_search",
    tool_config={}  # Empty config
)
```

---

### 5. get_tools_for_version() - List tools in version

```python
async def get_tools_for_version(
    db: Session,
    tenant_id: str,
    agent_id: str,
    version_id: str,
    enabled_only: bool = False,
) -> ListAgentToolsResponse
```

**Purpose**: Get all tools assigned to a version.

**Parameters**:
- `enabled_only=False`: Return all tools (enabled and disabled)
- `enabled_only=True`: Return only enabled tools

**Use Cases**:
- UI: Show all tools assigned to version
- AgentEngine: Load only enabled tools for execution
- Debugging: Inspect tool configuration

**Example Usage**:

```python
# Get all tools (including disabled)
all_tools = await service.get_tools_for_version(
    db=db_session,
    tenant_id="tenant_123",
    agent_id="agent_456",
    version_id="version_789",
    enabled_only=False
)

print(f"Total tools: {all_tools.total}")
print(f"Enabled: {all_tools.enabled_count}")
for tool in all_tools.items:
    print(f"  {tool.tool_name}: {tool.enabled}")

# Output:
# Total tools: 3
# Enabled: 2
#   google_search: True
#   calculator: True
#   http_request: False

# Get only enabled tools (for agent execution)
enabled_tools = await service.get_tools_for_version(
    db=db_session,
    tenant_id="tenant_123",
    agent_id="agent_456",
    version_id="version_789",
    enabled_only=True  # Only enabled
)

# Passed to AgentEngine
await engine.execute(
    agent_id=agent_id,
    tools=enabled_tools.items,  # Only enabled
)
```

---

### 6. get_tool_config() - Get specific tool configuration

```python
async def get_tool_config(
    db: Session,
    tenant_id: str,
    agent_id: str,
    version_id: str,
    tool_name: str,
) -> AgentToolResponse
```

**Purpose**: Retrieve configuration for a specific tool.

**Use Cases**:
- UI: Show current config for editing
- AgentEngine: Load tool-specific settings
- Debugging: Inspect exact parameters

**Example Usage**:

```python
# Get current config for a tool
tool_info = await service.get_tool_config(
    db=db_session,
    tenant_id="tenant_123",
    agent_id="agent_456",
    version_id="version_789",
    tool_name="google_search"
)

print(f"Tool: {tool_info.tool_name}")
print(f"Enabled: {tool_info.enabled}")
print(f"Config: {tool_info.tool_config}")
# Output:
# Tool: google_search
# Enabled: True
# Config: {'timeout': 30, 'max_results': 5}
```

---

## Complete Workflow Example

### Scenario: Create Agent with Multiple Tools

```python
from app.agents import (
    AgentService,
    AgentVersionService,
    AgentToolService,
)

agent_svc = AgentService()
version_svc = AgentVersionService()
tool_svc = AgentToolService()

# 1. Create agent
agent = await agent_svc.create_agent(
    db=db,
    tenant_id="tenant_123",
    created_by="user_789",
    name="Research Bot",
    agent_type="chat",
)

# 2. Create first version
version = await version_svc.create_version(
    db=db,
    tenant_id="tenant_123",
    agent_id=agent.id,
    created_by="user_789",
    system_prompt="You are a research assistant.",
)

# 3. Add tools
google = await tool_svc.add_tool_to_version(
    db=db,
    tenant_id="tenant_123",
    agent_id=agent.id,
    version_id=version.id,
    tool_name="google_search",
    tool_config={"timeout": 30, "max_results": 5}
)

calc = await tool_svc.add_tool_to_version(
    db=db,
    tenant_id="tenant_123",
    agent_id=agent.id,
    version_id=version.id,
    tool_name="calculator",
    tool_config={}
)

# 4. Activate version (make it live)
await version_svc.activate_version(
    db=db,
    tenant_id="tenant_123",
    agent_id=agent.id,
    version_id=version.id,
)

# 5. Get all tools for inspection
all_tools = await tool_svc.get_tools_for_version(
    db=db,
    tenant_id="tenant_123",
    agent_id=agent.id,
    version_id=version.id,
)
print(f"Tools: {all_tools.total}, Enabled: {all_tools.enabled_count}")

# 6. User reports google_search is unreliable
await tool_svc.enable_tool(
    db=db,
    tenant_id="tenant_123",
    agent_id=agent.id,
    version_id=version.id,
    tool_name="google_search",
    enabled=False  # Disable temporarily
)

# 7. Now only calculator is enabled
enabled_tools = await tool_svc.get_tools_for_version(
    db=db,
    tenant_id="tenant_123",
    agent_id=agent.id,
    version_id=version.id,
    enabled_only=True
)
print(f"Enabled tools: {[t.tool_name for t in enabled_tools.items]}")
# Output: ['calculator']

# 8. AgentEngine executes with enabled tools only
await engine.execute(
    agent_id=agent.id,
    version_id=version.id,
    tools=[t.tool_name for t in enabled_tools.items],
)

# 9. Fix deployed, re-enable
await tool_svc.enable_tool(
    db=db,
    tenant_id="tenant_123",
    agent_id=agent.id,
    version_id=version.id,
    tool_name="google_search",
    enabled=True
)
```

---

## Security & Multi-Tenancy

### Tenant Isolation

Every query includes tenant_id validation:

```python
# ✓ Correct: Validate tenant owns the version
version = db.query(AgentVersion).join(Agent).filter(
    Agent.tenant_id == tenant_id,  # ← MANDATORY
    Agent.id == agent_id,
    AgentVersion.id == version_id,
).first()

# ✗ Wrong: Missing tenant_id filter
version = db.query(AgentVersion).filter(
    AgentVersion.id == version_id,  # ← Data leak!
).first()
```

### ToolRegistry is Global

```python
# ToolRegistry is shared across ALL tenants
# Any tenant can reference any tool from registry
# But each tenant has separate tool configurations per agent

ToolRegistry.list_tools()  # Global: ["google_search", "calculator", ...]

# Each agent version has separate assignments
Agent A Version 1: [google_search, calculator]        ← Tenant 1
Agent B Version 1: [google_search]                    ← Tenant 2
Agent C Version 1: [calculator, http_request]         ← Tenant 1
```

### No Cross-Tenant Access

```python
# User from tenant_1 cannot:
# - Assign tools to tenant_2 agent
# - Modify tenant_2 tool configurations
# - List tenant_2 tools

# All queries validate:
if agent.tenant_id != tenant_id:
    raise ForbiddenError("...")
```

---

## Restrictions & Constraints

### ✅ PERMITTED

- Add any tool from ToolRegistry to any agent version
- Enable/disable tools multiple times
- Update tool configuration multiple times
- Have different tools across versions
- Have same tool configured differently in different versions
- Remove tools without affecting other versions

### ❌ NOT PERMITTED

- Add tool NOT in ToolRegistry
- Execute tools (AgentEngine only)
- Validate tool parameters (AgentEngine does this)
- Access tools from other tenants
- Modify ToolRegistry from service
- Cross-tenant tool assignments

---

## Integration Points

### With ToolRegistry

```python
# Validate tool exists
if not ToolRegistry.get_tool(tool_name):
    raise ValidationError("Tool not found")

# List available tools in error message
available = ToolRegistry.list_tools()
raise ValidationError(f"Available: {', '.join(available)}")
```

### With AgentVersionService

```python
# Tools belong to versions, not agents
# Before assigning tools, must have a version

version = await version_svc.create_version(...)
tool = await tool_svc.add_tool_to_version(..., version_id=version.id, ...)
```

### With AgentEngine (Phase 4)

```python
# Get enabled tools for execution
tools = await tool_svc.get_tools_for_version(
    ...,
    enabled_only=True,
)

# Each tool has its configuration
for tool in tools.items:
    execute_tool(tool.tool_name, config=tool.tool_config)
```

---

## Database Queries Generated

### Add Tool
```sql
INSERT INTO agent_tools (id, agent_version_id, tool_name, enabled, tool_config, created_at, updated_at)
VALUES ('t123', 'v456', 'google_search', TRUE, '{"timeout": 30}', NOW(), NOW());
```

### Get Tools for Version (Enabled Only)
```sql
SELECT * FROM agent_tools
WHERE agent_version_id = 'v456'
AND enabled = TRUE
ORDER BY created_at;
```

### Update Tool Config
```sql
UPDATE agent_tools
SET tool_config = '{"timeout": 60}', updated_at = NOW()
WHERE agent_version_id = 'v456'
AND tool_name = 'google_search';
```

### Remove Tool
```sql
DELETE FROM agent_tools
WHERE agent_version_id = 'v456'
AND tool_name = 'google_search';
```

---

## Next Steps

1. **AgentPromptService** (Step 2.4)
   - Manage prompt types per version
   - system, instruction, context, fallback prompts
   - One prompt per type per version

2. **AgentLoader** (Step 2.5)
   - Orchestrates all services
   - Returns complete AgentConfig for execution
   - Bridge between services and AgentEngine

3. **API Routers** (Step 3)
   - REST endpoints using AgentToolService
   - Tool assignment, enabling, configuration

4. **Integration** (Step 4)
   - AgentEngine loads enabled tools from service
   - Celery workers use tool configurations
