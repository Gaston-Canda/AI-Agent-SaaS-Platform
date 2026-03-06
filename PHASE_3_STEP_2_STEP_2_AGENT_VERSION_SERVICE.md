# Phase 3 Step 2.2: AgentVersionService Implementation

## Overview

**AgentVersionService** handles all version-related operations for agents, enabling:
- Semantic versioning (1.0, 1.1, 2.0, etc.)
- Version history and tracking
- Rollback to previous versions
- A/B testing via multiple versions
- Single active version enforcement
- Audit trail of configuration changes

## Architecture

### Service Location
```
app/agents/
├── __init__.py                    # Exports all services and schemas
├── schemas.py                     # Pydantic models (requests/responses)
├── agent_service.py               # AgentService (CRUD for agents)
└── agent_version_service.py       # AgentVersionService (version management)
```

### Dependency Injection Pattern

All methods receive `db: Session` as a parameter:

```python
# Service methods follow DI pattern
async def create_version(
    self,
    db: Session,              # ← Injected database session
    tenant_id: str,           # ← Always filter by tenant_id
    agent_id: str,
    created_by: str,
    system_prompt: str,
    configuration: Optional[dict] = None,
    is_major: bool = False,
) -> AgentVersionResponse:  # ← Returns Pydantic schema, not ORM model
    ...
```

**Why dependency injection?**
- Avoids storing state in service instance
- Enables request-scoped database transactions
- Simplifies testing (inject test database)
- Clear explicit parameter passing

## Data Models

### AgentVersionResponse (Pydantic Schema)

Returned by all `get_*` methods:

```python
class AgentVersionResponse(BaseModel):
    id: str                    # Version ID (UUID)
    agent_id: str             # Parent agent ID
    version: str              # Version number: "1.0", "1.1", "2.0"
    is_active: bool           # Current active version flag
    system_prompt: str        # System prompt for this version
    configuration: dict       # LLM config: provider, model, temperature, etc.
    created_by: str          # User who created this version
    created_at: datetime      # Creation timestamp
```

### CreateVersionRequest (Pydantic Schema)

Request body for creating versions:

```python
class CreateVersionRequest(BaseModel):
    system_prompt: str        # Required: 1-5000 chars
    configuration: dict       # Optional: LLM configuration
```

### ListVersionsResponse (Pydantic Schema)

Returned by `get_versions()`:

```python
class ListVersionsResponse(BaseModel):
    items: list[AgentVersionResponse]  # All versions, newest first
    total: int                         # Total count
```

### Database Table

```sql
CREATE TABLE agent_versions (
    id VARCHAR(36) PRIMARY KEY,
    agent_id VARCHAR(36) NOT NULL REFERENCES agents(id),
    version VARCHAR(20) NOT NULL,        -- e.g., "1.0", "1.1", "2.0"
    is_active BOOLEAN DEFAULT FALSE,     -- Only one active per agent
    system_prompt TEXT NOT NULL,
    configuration JSON DEFAULT '{}',     -- LLM provider, model, temperature, etc.
    created_by VARCHAR(36) NOT NULL REFERENCES users(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes for performance
    INDEX idx_agent_version_agent_id (agent_id),
    INDEX idx_agent_version_is_active (agent_id, is_active),
    INDEX idx_agent_version_created_at (created_at),
);
```

## Method Reference

### 1. create_version() - Create new version

```python
async def create_version(
    db: Session,
    tenant_id: str,
    agent_id: str,
    created_by: str,
    system_prompt: str,
    configuration: Optional[dict] = None,
    is_major: bool = False,
) -> AgentVersionResponse
```

**Purpose**: Create a new version and auto-increment version number using semantic versioning.

**Behavior**:
- Validates agent exists and belongs to tenant
- Validates system_prompt is not empty and ≤5000 chars
- Queries latest version to determine next version number
- Auto-increments version:
  - If no versions exist: creates "1.0"
  - If `is_major=False` (default): increments minor (1.0 → 1.1 → 1.2)
  - If `is_major=True`: increments major (1.x → 2.0)
- Creates version in INACTIVE state (use activate_version to activate)
- Commits to database

**Example Usage**:

```python
from app.agents import AgentVersionService

service = AgentVersionService()

# Create first version (1.0)
v1 = await service.create_version(
    db=db_session,
    tenant_id="tenant_123",
    agent_id="agent_456",
    created_by="user_789",
    system_prompt="You are a helpful AI assistant.",
    configuration={
        "llm_provider": "openai",
        "llm_model": "gpt-4-turbo-preview",
        "temperature": 0.7,
        "max_tokens": 2048,
    }
)
# Result: v1.version == "1.0", v1.is_active == False

# Create second version (1.1) - minor update
v2 = await service.create_version(
    db=db_session,
    tenant_id="tenant_123",
    agent_id="agent_456",
    created_by="user_789",
    system_prompt="You are a helpful AI assistant with improved responses.",
    configuration={"llm_model": "gpt-4-turbo-preview"}
)
# Result: v2.version == "1.1", v2.is_active == False

# Create major version (2.0) - breaking change
v3 = await service.create_version(
    db=db_session,
    tenant_id="tenant_123",
    agent_id="agent_456",
    created_by="user_789",
    system_prompt="Complete rewrite for new capabilities.",
    configuration={...},
    is_major=True  # ← Increment major version
)
# Result: v3.version == "2.0", v3.is_active == False
```

**Lifecycle**:
1. New version created as INACTIVE
2. User tests the version
3. When satisfied, activate with activate_version()

---

### 2. get_versions() - List all versions

```python
async def get_versions(
    db: Session,
    tenant_id: str,
    agent_id: str,
) -> ListVersionsResponse
```

**Purpose**: Retrieve all versions for an agent, ordered by creation date (newest first).

**Behavior**:
- Validates agent exists and belongs to tenant
- Queries all versions for agent
- Orders by created_at DESC (newest first)
- Returns ListVersionsResponse with items and total count
- No database commit

**Example Usage**:

```python
# Get all versions
response = await service.get_versions(
    db=db_session,
    tenant_id="tenant_123",
    agent_id="agent_456",
)

print(f"Total versions: {response.total}")
for version in response.items:
    print(f"  {version.version}: {version.system_prompt[:50]}... (active: {version.is_active})")

# Output example:
# Total versions: 3
#   1.1: You are a helpful AI assistant with improved... (active: True)
#   1.0: You are a helpful AI assistant. (active: False)
```

---

### 3. get_latest_version() - Get active version

```python
async def get_latest_version(
    db: Session,
    tenant_id: str,
    agent_id: str,
) -> AgentVersionResponse
```

**Purpose**: Get the ACTIVE version (the one currently used by the agent).

**Critical Difference**:
- **NOT** the newest version by date
- **IS** the version with `is_active=True`
- This is what the AgentEngine executes

**Behavior**:
- Validates agent exists and belongs to tenant
- Queries for version with is_active=True
- Raises NotFoundError if no active version
- No database commit

**Example Usage**:

```python
# Get what version is currently active
active_version = await service.get_latest_version(
    db=db_session,
    tenant_id="tenant_123",
    agent_id="agent_456",
)

print(f"Running version: {active_version.version}")
print(f"System prompt: {active_version.system_prompt}")
print(f"LLM model: {active_version.configuration.get('llm_model')}")

# This is what AgentEngine will execute
```

---

### 4. activate_version() - Activate a version

```python
async def activate_version(
    db: Session,
    tenant_id: str,
    agent_id: str,
    version_id: str,
) -> AgentVersionResponse
```

**Purpose**: Activate a specific version (deactivate all others).

**Behavior**:
- Validates agent exists and belongs to tenant
- Verifies version exists and belongs to agent
- Deactivates all other versions for this agent (sets is_active=False)
- Activates specified version (sets is_active=True)
- Updates Agent.default_version_id pointer
- Commits to database

**Multi-Version Impact**:
```
Before activation:
  Version 1.0: is_active=False
  Version 1.1: is_active=True  ← Currently active
  Version 1.2: is_active=False

activate_version(agent_id, version_1_0_id):
  Version 1.0: is_active=True  ← Now active
  Version 1.1: is_active=False ← Deactivated
  Version 1.2: is_active=False
```

**Example Usage**:

```python
# Activate version 1.0 (rollback from 1.1)
activated = await service.activate_version(
    db=db_session,
    tenant_id="tenant_123",
    agent_id="agent_456",
    version_id="version_1_0_id",
)

print(f"Activated version: {activated.version}")
# AgentEngine will now execute this version on next request
```

---

### 5. get_version_by_id() - Get specific version

```python
async def get_version_by_id(
    db: Session,
    tenant_id: str,
    agent_id: str,
    version_id: str,
) -> AgentVersionResponse
```

**Purpose**: Retrieve a specific version by ID.

**Behavior**:
- Validates agent exists and belongs to tenant
- Queries for specific version
- Raises NotFoundError if not found
- No database commit

**When to Use**:
- UI needs to display specific version details
- Need to compare two versions
- Preview before activation

**Example Usage**:

```python
# Get version details before activating
version_details = await service.get_version_by_id(
    db=db_session,
    tenant_id="tenant_123",
    agent_id="agent_456",
    version_id="version_1_1_id",
)

print(f"Version {version_details.version} details:")
print(f"  Created: {version_details.created_at}")
print(f"  Active: {version_details.is_active}")
print(f"  Prompt: {version_details.system_prompt}")
```

---

### 6. rollback_version() - Rollback by version number

```python
async def rollback_version(
    db: Session,
    tenant_id: str,
    agent_id: str,
    version_number: str,
) -> AgentVersionResponse
```

**Purpose**: Convenience method to rollback by version number instead of ID.

**Behavior**:
- Validates agent exists and belongs to tenant
- Finds version by version_number (e.g., "1.0")
- Calls activate_version() internally
- Commits to database

**Why Separate Method?**
- UX: Users think in terms of "version 1.0", not UUIDs
- UI can show: "Rollback to 1.0" button
- Backend handles ID lookup

**Example Usage**:

```python
# Rollback to version 1.0 (UI: "Rollback to 1.0" button clicked)
rolled_back = await service.rollback_version(
    db=db_session,
    tenant_id="tenant_123",
    agent_id="agent_456",
    version_number="1.0",
)

print(f"Rolled back to: {rolled_back.version}")
# Equivalent to:
# 1. Find version "1.0"
# 2. activate_version(agent_id, version_1_0_id)
```

---

## Version Numbering

### Semantic Versioning: Major.Minor

```
Format: X.Y
  X = Major version (breaking changes)
  Y = Minor version (backward-compatible changes)

Sequence:
  1.0 → 1.1 → 1.2 → ... → 2.0 → 2.1 → ...
         ↑    ↑           ↑
       minor changes   major change
```

### When to Increment

**Minor Version (1.0 → 1.1)**
- Update system prompt
- Change temperature or other parameters
- Enable/disable a tool
- Logical improvements without breaking changes

```python
# User updates prompt, create new version
v2 = await service.create_version(
    db, tenant_id, agent_id, created_by,
    system_prompt="Updated prompt",
    is_major=False  # Minor increment: 1.0 → 1.1
)
```

**Major Version (1.x → 2.0)**
- Complete rewrite
- Major architectural change
- Breaking changes to expected behavior
- Full feature overhaul

```python
# User does complete redesign
v3 = await service.create_version(
    db, tenant_id, agent_id, created_by,
    system_prompt="Completely new architecture",
    is_major=True  # Major increment: 1.x → 2.0
)
```

---

## Security & Multi-Tenancy

### Tenant Isolation

All methods enforce `tenant_id` filtering:

```python
# ✓ Correct: Always filter by tenant_id
agent = db.query(Agent).filter(
    Agent.id == agent_id,
    Agent.tenant_id == tenant_id,  # ← MANDATORY
).first()

# ✗ Wrong: Missing tenant_id filter
agent = db.query(Agent).filter(
    Agent.id == agent_id,  # ← Data leak!
).first()
```

### Validation Checks

```python
# 1. Agent must exist AND belong to tenant
agent = self._validate_agent_exists(db, tenant_id, agent_id)
# Raises ForbiddenError if not found or wrong tenant

# 2. Version must belong to agent
version = db.query(AgentVersion).filter(
    AgentVersion.id == version_id,
    AgentVersion.agent_id == agent_id,  # ← Implicit tenant check
).first()

# 3. System prompt validation
if not system_prompt or not system_prompt.strip():
    raise ValidationError("System prompt cannot be empty")
if len(system_prompt) > 5000:
    raise ValidationError("System prompt cannot exceed 5000 characters")
```

---

## Integration with AgentEngine

### Version Loading Flow

```
1. User requests agent execution
   ↓
2. AgentEngine requests active version
   → get_latest_version(db, tenant_id, agent_id)
   ↓
3. AgentVersionService returns active version config
   ↓
4. AgentEngine builds LLM with version configuration
   ↓
5. Agent executes with version's system_prompt and tools
```

### Pseudo-code Integration

```python
# In AgentEngine (Phase 4 integration)
async def execute_agent(self, agent_id: str, user_message: str):
    # Get active version
    version = await version_service.get_latest_version(
        db=db_session,
        tenant_id=current_tenant_id,
        agent_id=agent_id,
    )
    
    # Build execution context with version config
    execution_context = ExecutionContext(
        agent_id=agent_id,
        version_id=version.id,
        version_number=version.version,
        system_prompt=version.system_prompt,
        llm_config=version.configuration,
    )
    
    # Execute with version-specific settings
    return await self.run_agent_loop(execution_context, user_message)
```

---

## Workflow Example

### Complete Agent Versioning Workflow

```python
from app.agents import AgentService, AgentVersionService

agent_svc = AgentService()
version_svc = AgentVersionService()

# 1. Create agent (AgentService)
agent = await agent_svc.create_agent(
    db=db,
    tenant_id="tenant_123",
    created_by="user_789",
    name="Support Bot",
    description="Customer support",
    agent_type="chat",
)
# Result: agent.status = "draft", agent.default_version_id = None

# 2. Create first version (1.0)
v1 = await version_svc.create_version(
    db=db,
    tenant_id="tenant_123",
    agent_id=agent.id,
    created_by="user_789",
    system_prompt="You are a helpful support agent.",
    configuration={"llm_model": "gpt-4-turbo-preview", "temperature": 0.7},
)
# Result: v1.version = "1.0", v1.is_active = False

# 3. Activate version (make it live)
active = await version_svc.activate_version(
    db=db,
    tenant_id="tenant_123",
    agent_id=agent.id,
    version_id=v1.id,
)
# Result: agent.default_version_id = v1.id, v1.is_active = True

# 4. Agent is now ready (status="active", has active version)

# 5. User improves prompt, create v1.1
v2 = await version_svc.create_version(
    db=db,
    tenant_id="tenant_123",
    agent_id=agent.id,
    created_by="user_789",
    system_prompt="You are a helpful support agent with improved responses.",
    configuration={"temperature": 0.5},  # More deterministic
)
# Result: v2.version = "1.1", v2.is_active = False

# 6. Test v1.1 for a while, then activate it
await version_svc.activate_version(
    db=db,
    tenant_id="tenant_123",
    agent_id=agent.id,
    version_id=v2.id,
)
# v1 is now inactive, v2 is now active

# 7. User wants to rollback to v1.0
await version_svc.rollback_version(
    db=db,
    tenant_id="tenant_123",
    agent_id=agent.id,
    version_number="1.0",
)
# v1 is now active again, v2 is inactive

# 8. View version history
history = await version_svc.get_versions(
    db=db,
    tenant_id="tenant_123",
    agent_id=agent.id,
)
# Returns all 2 versions, newest first
```

---

## Database Queries Generated

### Create Version
```sql
INSERT INTO agent_versions (id, agent_id, version, is_active, system_prompt, configuration, created_by, created_at)
VALUES ('v123', 'agent456', '1.0', FALSE, 'You are...', '{}', 'user789', NOW());
```

### Get Active Version
```sql
SELECT * FROM agent_versions
WHERE agent_id = 'agent456'
AND is_active = TRUE;
```

### Get All Versions (Ordered)
```sql
SELECT * FROM agent_versions
WHERE agent_id = 'agent456'
ORDER BY created_at DESC;
```

### Activate Version (atomic)
```sql
-- Deactivate others
UPDATE agent_versions SET is_active = FALSE
WHERE agent_id = 'agent456' AND id != 'v123';

-- Activate selected
UPDATE agent_versions SET is_active = TRUE
WHERE id = 'v123';

-- Update agent pointer
UPDATE agents SET default_version_id = 'v123'
WHERE id = 'agent456';
```

---

## Exception Hierarchy

All exceptions inherit from `AppError` with automatic HTTP status code mapping:

```python
NotFoundError          # 404 - Version/agent not found
ValidationError        # 400 - Invalid parameters
ForbiddenError         # 403 - Tenant isolation violation
```

---

## Production Considerations

### Performance Optimization

1. **Indexes Created**:
   - `agent_id` - Fast agent lookups
   - `(agent_id, is_active)` - Fast active version lookup
   - `created_at` - Fast order_by DESC

2. **Query Patterns**:
   - Single active version per agent (indexed)
   - Version list rarely queries >10 versions per agent
   - Semantic versioning prevents unbounded growth

### Pagination

Not needed for versions (users rarely have >20 versions per agent).

### Caching Opportunity

```python
# Cache active version for 5 minutes (invalidate on activate_version)
@cache.cached(timeout=300, key="active_version_{agent_id}")
async def get_latest_version(...) -> AgentVersionResponse:
    ...
```

---

## Next Steps

1. **AgentToolService** (Step 2.3)
   - Manages tools per version
   - Enable/disable tools
   - Per-tool configuration

2. **AgentPromptService** (Step 2.4)
   - Manages prompt types
   - System, instruction, context, fallback prompts
   - One prompt per type per version

3. **AgentLoader** (Step 2.5)
   - Orchestrates all services
   - Returns complete AgentConfig for execution

4. **API Routers** (Step 3)
   - REST endpoints using these services
   - Version management UI

5. **Integration** (Step 4)
   - AgentEngine uses get_latest_version()
   - Celery workers load versions dynamically
