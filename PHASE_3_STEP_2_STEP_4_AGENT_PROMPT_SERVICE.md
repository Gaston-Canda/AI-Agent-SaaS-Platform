# Phase 3 Step 2.4: AgentPromptService Implementation

## Overview

**AgentPromptService** manages prompt configuration per agent version. It enforces a strict constraint: **one prompt per type per version**. This enables users to craft custom agent behavior through prompt engineering without versioning overhead.

**Prompt Types**:

- **system** - Role definition and base behavior (e.g., "You are a support agent")
- **instruction** - Specific behavioral instructions (e.g., "Be brief, max 2 paragraphs")
- **context** - Background information (e.g., "Company founded in 2020...")
- **fallback** - Response when tools unavailable (e.g., "I apologize, I cannot...")

## Architecture

### Service Location

```
app/agents/
├── __init__.py                       # Exports all services and schemas
├── schemas.py                        # Pydantic models
├── agent_service.py                  # CRUD for agents
├── agent_version_service.py          # Version management
├── agent_tool_service.py             # Tool configuration
└── agent_prompt_service.py           # Prompt management (NEW)
```

### PromptType Enum

From `app/models/agent_platform.py`:

```python
class PromptType(str, enum.Enum):
    """Types of prompts in an agent."""
    SYSTEM = "system"
    INSTRUCTION = "instruction"
    CONTEXT = "context"
    FALLBACK = "fallback"
```

### Dependency Injection Pattern

```python
async def create_prompt(
    self,
    db: Session,            # ← Database session (injected)
    tenant_id: str,         # ← Always filter by tenant_id
    agent_id: str,
    version_id: str,
    prompt_type: str,       # ← Validated against PromptType enum
    prompt_content: str,    # ← 1-5000 chars
    created_by: str,
) -> AgentPromptResponse:  # ← Returns Pydantic, not ORM
    ...
```

## Data Models

### AgentPromptResponse (Pydantic Schema)

Returned by all operations:

```python
class AgentPromptResponse(BaseModel):
    id: str                    # Prompt ID (UUID)
    agent_version_id: str      # Version it belongs to
    prompt_type: str           # "system", "instruction", "context", "fallback"
    prompt_content: str        # Full prompt text (up to 5000 chars)
    created_by: str            # User who created this prompt
    created_at: datetime       # Creation timestamp
    updated_at: datetime       # Last update timestamp
```

### CreatePromptRequest (Pydantic Schema)

Request to create prompt:

```python
class CreatePromptRequest(BaseModel):
    prompt_type: str           # Required: one of the 4 types
    prompt_content: str        # Required: 1-5000 chars
```

### UpdatePromptRequest (Pydantic Schema)

Request to update prompt:

```python
class UpdatePromptRequest(BaseModel):
    prompt_content: str        # New content (1-5000 chars)
```

### ListAgentPromptsResponse (Pydantic Schema)

List of prompts:

```python
class ListAgentPromptsResponse(BaseModel):
    items: list[AgentPromptResponse]  # All prompts for version
    total: int                        # Total count
```

### Database Table

```sql
CREATE TABLE agent_prompts (
    id VARCHAR(36) PRIMARY KEY,
    agent_version_id VARCHAR(36) NOT NULL REFERENCES agent_versions(id),
    prompt_type ENUM('system', 'instruction', 'context', 'fallback') NOT NULL,
    prompt_content TEXT NOT NULL,      -- Full prompt text
    created_by VARCHAR(36) NOT NULL REFERENCES users(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    -- ONE PROMPT PER TYPE PER VERSION
    UNIQUE (agent_version_id, prompt_type),

    -- Indexes for performance
    INDEX idx_agent_prompt_version_id (agent_version_id),
    INDEX idx_agent_prompt_type (agent_version_id, prompt_type),
    INDEX idx_agent_prompt_created_at (created_at),
);
```

**Critical Constraint**: `UNIQUE (agent_version_id, prompt_type)` ensures only one prompt per type per version.

## Method Reference

### 1. create_prompt() - Create new prompt

```python
async def create_prompt(
    db: Session,
    tenant_id: str,
    agent_id: str,
    version_id: str,
    prompt_type: str,       # "system", "instruction", "context", "fallback"
    prompt_content: str,    # 1-5000 characters
    created_by: str,
) -> AgentPromptResponse
```

**Purpose**: Create a prompt of a specific type for a version.

**Validation**:

- Version exists and belongs to tenant
- prompt_type is valid enum value
- prompt_content is not empty and ≤5000 chars
- **Prompt of this type doesn't already exist** ← CRITICAL

**Behavior**:

- Creates new AgentPrompt record
- Raises ConflictError if prompt of this type exists (use update instead)
- Commits to database

**Example Usage**:

```python
from app.agents import AgentPromptService

service = AgentPromptService()

# Create system prompt
system_prompt = await service.create_prompt(
    db=db_session,
    tenant_id="tenant_123",
    agent_id="agent_456",
    version_id="version_789",
    prompt_type="system",
    prompt_content="You are a helpful customer support agent. Always be polite and professional.",
    created_by="user_abc",
)

# Create instruction prompt
instruction = await service.create_prompt(
    db=db_session,
    tenant_id="tenant_123",
    agent_id="agent_456",
    version_id="version_789",
    prompt_type="instruction",
    prompt_content="Be brief. Respond in maximum 2 paragraphs. Use simple language.",
    created_by="user_abc",
)

# Try to create another system prompt → ConflictError
await service.create_prompt(
    db=db_session,
    tenant_id="tenant_123",
    agent_id="agent_456",
    version_id="version_789",
    prompt_type="system",  # Already exists!
    prompt_content="Different content",
    created_by="user_abc",
)
# Result: ConflictError("Prompt of type 'system' already exists...")
```

**One Prompt Per Type Per Version**:

```
Version 1.0:
  ✓ system: "You are a support agent..."
  ✓ instruction: "Be brief..."
  ✓ context: "Company info..."
  ✗ system: "Different role..."  ← ERROR: Already exists!
```

---

### 2. update_prompt() - Update existing prompt

```python
async def update_prompt(
    db: Session,
    tenant_id: str,
    agent_id: str,
    version_id: str,
    prompt_type: str,
    prompt_content: str,
) -> AgentPromptResponse
```

**Purpose**: Modify the content of an existing prompt.

**Behavior**:

- Finds prompt by type
- Updates prompt_content
- Updates updated_at timestamp
- Cannot change prompt_type (delete + create new if needed)

**Workflow**:

```python
# Initial creation
await service.create_prompt(
    ..., prompt_type="system",
    prompt_content="v1 prompt"
)

# Iterate: improve with feedback
await service.update_prompt(
    ..., prompt_type="system",
    prompt_content="v2 improved prompt"
)

# Test more, refine further
await service.update_prompt(
    ..., prompt_type="system",
    prompt_content="v3 even better prompt"
)

# All updates use SAME prompt record, just changing content
# No new versions needed unless committing to stable version in history
```

**Example Usage**:

```python
# Update existing system prompt
updated = await service.update_prompt(
    db=db_session,
    tenant_id="tenant_123",
    agent_id="agent_456",
    version_id="version_789",
    prompt_type="system",
    prompt_content="You are a helpful customer support agent with 10+ years experience. Always be empathetic.",
)

print(f"System prompt updated: {updated.prompt_content[:50]}...")
```

---

### 3. get_prompt() - Retrieve specific prompt

```python
async def get_prompt(
    db: Session,
    tenant_id: str,
    agent_id: str,
    version_id: str,
    prompt_type: str,
) -> AgentPromptResponse
```

**Purpose**: Get a specific prompt by type.

**Use Cases**:

- UI: Show current prompt for editing
- AgentLoader: Load prompt for execution
- Debugging: Inspect exact text

**Example Usage**:

```python
# Get system prompt for editing
system = await service.get_prompt(
    db=db_session,
    tenant_id="tenant_123",
    agent_id="agent_456",
    version_id="version_789",
    prompt_type="system",
)

print(f"Current system prompt:")
print(system.prompt_content)
print(f"Last updated: {system.updated_at}")

# Edit it
new_content = system.prompt_content.replace("agent", "AI assistant")

# Update
await service.update_prompt(
    db=db_session,
    tenant_id="tenant_123",
    agent_id="agent_456",
    version_id="version_789",
    prompt_type="system",
    prompt_content=new_content,
)
```

---

### 4. list_prompts() - List all prompts for version

```python
async def list_prompts(
    db: Session,
    tenant_id: str,
    agent_id: str,
    version_id: str,
) -> ListAgentPromptsResponse
```

**Purpose**: Get all prompts (any type) for a version.

**Important**: Some prompt types may not exist, which is valid.

**Behavior**:

- Returns ALL prompts for version
- Ordered by creation time
- No filtering

**Example Usage**:

```python
# Get all prompts
response = await service.list_prompts(
    db=db_session,
    tenant_id="tenant_123",
    agent_id="agent_456",
    version_id="version_789",
)

print(f"Total prompts: {response.total}")
for prompt in response.items:
    print(f"\n{prompt.prompt_type.upper()}:")
    print(f"  {prompt.prompt_content[:100]}...")
    print(f"  Updated: {prompt.updated_at}")

# Output example:
# Total prompts: 3
#
# SYSTEM:
#   You are a helpful customer support agent...
#   Updated: 2024-03-05T10:05:00
#
# INSTRUCTION:
#   Be brief. Respond in maximum 2 paragraphs...
#   Updated: 2024-03-05T10:05:00
#
# CONTEXT:
#   Our company was founded in 2020...
#   Updated: 2024-03-05T10:00:00
```

**Missing Types Are OK**:

```python
# Version with only system prompt
response = await service.list_prompts(...)
# Result: 1 prompt (just system)

# AgentEngine knows how to handle missing instruction, context, fallback
# It uses defaults or skips those sections
```

---

### 5. delete_prompt() - Remove prompt

```python
async def delete_prompt(
    db: Session,
    tenant_id: str,
    agent_id: str,
    version_id: str,
    prompt_type: str,
) -> None
```

**Purpose**: Permanently delete a prompt.

**Behavior**:

- Hard delete (no soft delete)
- Removes prompt completely
- Updates updated_at NOT recorded (record deleted)

**When to Use**:

- Cleaning up unnecessary prompts
- Switching prompt strategies

**Example Usage**:

```python
# Remove fallback prompt if not needed
await service.delete_prompt(
    db=db_session,
    tenant_id="tenant_123",
    agent_id="agent_456",
    version_id="version_789",
    prompt_type="fallback",
)

# Verify it's gone
response = await service.list_prompts(...)
has_fallback = any(p.prompt_type == "fallback" for p in response.items)
print(f"Has fallback: {has_fallback}")  # False
```

---

## Complete Workflow Example

### Scenario: Build Agent with Custom Prompts

```python
from app.agents import (
    AgentService,
    AgentVersionService,
    AgentToolService,
    AgentPromptService,
)

agent_svc = AgentService()
version_svc = AgentVersionService()
tool_svc = AgentToolService()
prompt_svc = AgentPromptService()

# 1. Create agent
agent = await agent_svc.create_agent(
    db=db,
    tenant_id="tenant_123",
    created_by="user_789",
    name="Customer Support Bot",
    agent_type="chat",
)

# 2. Create version
version = await version_svc.create_version(
    db=db,
    tenant_id="tenant_123",
    agent_id=agent.id,
    created_by="user_789",
    system_prompt="You are a customer support specialist.",
)

# 3. Add prompts to customize behavior
system = await prompt_svc.create_prompt(
    db=db,
    tenant_id="tenant_123",
    agent_id=agent.id,
    version_id=version.id,
    prompt_type="system",
    prompt_content="You are a professional customer support specialist with 10+ years experience. Your goal is to resolve issues quickly and leave customers satisfied.",
    created_by="user_789",
)

instruction = await prompt_svc.create_prompt(
    db=db,
    tenant_id="tenant_123",
    agent_id=agent.id,
    version_id=version.id,
    prompt_type="instruction",
    prompt_content="1. Be empathetic\n2. Be concise (max 2 paragraphs)\n3. Offer solutions\n4. Follow up if needed",
    created_by="user_789",
)

context = await prompt_svc.create_prompt(
    db=db,
    tenant_id="tenant_123",
    agent_id=agent.id,
    version_id=version.id,
    prompt_type="context",
    prompt_content="Company context: Founded 2020, 100+ employees, operating in 15 countries. Known for excellent customer service. Response time target: <5 minutes.",
    created_by="user_789",
)

fallback = await prompt_svc.create_prompt(
    db=db,
    tenant_id="tenant_123",
    agent_id=agent.id,
    version_id=version.id,
    prompt_type="fallback",
    prompt_content="I apologize, but I'm unable to fully assist with your request at this moment. Please allow me to escalate your ticket to a human specialist who will help you within 1 hour.",
    created_by="user_789",
)

# 4. Add tools
await tool_svc.add_tool_to_version(
    db=db,
    tenant_id="tenant_123",
    agent_id=agent.id,
    version_id=version.id,
    tool_name="ticket_search",
    tool_config={"max_results": 10},
)

await tool_svc.add_tool_to_version(
    db=db,
    tenant_id="tenant_123",
    agent_id=agent.id,
    version_id=version.id,
    tool_name="knowledge_base",
    tool_config={"confidence_threshold": 0.8},
)

# 5. Activate version (make it live)
await version_svc.activate_version(
    db=db,
    tenant_id="tenant_123",
    agent_id=agent.id,
    version_id=version.id,
)

# === AGENT IS NOW LIVE ===

# 6. During execution, AgentLoader gathers all components
prompts = await prompt_svc.list_prompts(
    db=db,
    tenant_id="tenant_123",
    agent_id=agent.id,
    version_id=version.id,
)

tools = await tool_svc.get_tools_for_version(
    db=db,
    tenant_id="tenant_123",
    agent_id=agent.id,
    version_id=version.id,
    enabled_only=True,
)

# === AgentLoader ASSEMBLES everything into AgentConfig ===

# 7. User reports: system prompt needs update
await prompt_svc.update_prompt(
    db=db,
    tenant_id="tenant_123",
    agent_id=agent.id,
    version_id=version.id,
    prompt_type="system",
    prompt_content="You are a professional customer success specialist (formerly called support). Focus on helping customers reach their goals, not just solving problems.",
)

# Agent now uses updated prompt on next execution (no version bump needed)

# 8. Iteration: instructions need refinement
await prompt_svc.update_prompt(
    db=db,
    tenant_id="tenant_123",
    agent_id=agent.id,
    version_id=version.id,
    prompt_type="instruction",
    prompt_content="1. Listen actively to understand customer needs\n2. Provide personalized solutions\n3. Be concise but not rushed\n4. Always follow up",
)

# 9. Review all current prompts
all_prompts = await prompt_svc.list_prompts(
    db=db,
    tenant_id="tenant_123",
    agent_id=agent.id,
    version_id=version.id,
)

print(f"Agent has {all_prompts.total} custom prompts")
for p in all_prompts.items:
    print(f"  {p.prompt_type}: {p.prompt_content[:50]}...")
```

---

## Security & Multi-Tenancy

### Tenant Isolation

Every query validates tenant_id:

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

### Prompt Type Validation

```python
# Validate against enum, handle case-insensitively
def _validate_prompt_type(self, prompt_type: str) -> PromptType:
    normalized = prompt_type.upper()
    valid_types = [t.value for t in PromptType]

    if normalized not in [t.upper() for t in valid_types]:
        raise ValidationError(
            f"Invalid prompt_type '{prompt_type}'. "
            f"Valid types: {', '.join(valid_types)}"
        )

    return PromptType[normalized]

# Usage: accepts "system", "System", "SYSTEM" → all map to PromptType.SYSTEM
```

---

## Restrictions & Constraints

### ✅ PERMITTED

- Create one prompt of each type per version
- Update prompts multiple times
- Have different prompts across versions
- Delete prompts (all types optional)
- Leave some types empty
- Copy prompts from v1 to v2 manually

### ❌ NOT PERMITTED

- Create 2+ prompts of same type in same version (uniqueness constraint)
- Empty prompt content
- Invalid prompt_type (not in enum)
- Cross-tenant access

---

## Prompt Assembly

**AgentPromptService**: Only manages prompt storage/retrieval

**AgentLoader** (Phase 4): Assembles prompts into final template

**AgentEngine** (Phase 2): Uses assembled prompt in LLM calls

```
AgentPromptService
  │
  ├─ create_prompt("system", "You are...")
  ├─ create_prompt("instruction", "Be brief...")
  ├─ create_prompt("context", "Company info...")
  └─ create_prompt("fallback", "I apologize...")

  ↓ list_prompts() returns all 4

AgentLoader
  │
  ├─ Gathers prompts from prompt_svc
  ├─ Gathers tools from tool_svc
  ├─ Gathers version config from version_svc
  │
  └─ Assembles into final_prompt:
      """
      [SYSTEM]
      You are...

      [INSTRUCTIONS]
      Be brief...

      [CONTEXT]
      Company info...
      """

  ↓ Returns AgentConfig

AgentEngine
  │
  └─ Executes with final_prompt:
      response = llm.create_message(
          system=final_prompt,
          messages=conversation_history
      )
```

---

## Database Queries Generated

### Create Prompt

```sql
INSERT INTO agent_prompts (id, agent_version_id, prompt_type, prompt_content, created_by, created_at, updated_at)
VALUES ('p123', 'v456', 'system', 'You are...', 'u789', NOW(), NOW());
```

### Get Prompt

```sql
SELECT * FROM agent_prompts
WHERE agent_version_id = 'v456'
AND prompt_type = 'system';
```

### List Prompts

```sql
SELECT * FROM agent_prompts
WHERE agent_version_id = 'v456'
ORDER BY created_at;
```

### Update Prompt

```sql
UPDATE agent_prompts
SET prompt_content = 'Updated text...', updated_at = NOW()
WHERE agent_version_id = 'v456'
AND prompt_type = 'system';
```

### Delete Prompt

```sql
DELETE FROM agent_prompts
WHERE agent_version_id = 'v456'
AND prompt_type = 'fallback';
```

---

## Integration Points

### With AgentVersionService

```python
# Prompts belong to versions
version = await version_svc.create_version(...)
prompt = await prompt_svc.create_prompt(..., version_id=version.id)
```

### With AgentToolService

```python
# Both service different aspects of same version
tools = await tool_svc.get_tools_for_version(...)
prompts = await prompt_svc.list_prompts(...)

# AgentLoader combines them
```

### With AgentLoader (Phase 4)

```python
# AgentLoader orchestrates all services
prompts = await prompt_svc.list_prompts(...)
tools = await tool_svc.get_tools_for_version(...)
version = await version_svc.get_latest_version(...)

# Returns complete AgentConfig ready for execution
return AgentConfig(
    system_prompt=assemble_prompt(prompts),
    tools=tools,
    llm_config=version.configuration,
)
```

---

## Exception Hierarchy

```python
ValidationError      # 400 - Invalid prompt_type, empty content
ConflictError        # 409 - Prompt of type already exists
NotFoundError        # 404 - Prompt not found
ForbiddenError       # 403 - Tenant isolation violation
```

---

## Next Steps

1. **AgentLoader** (Step 2.5)
   - Orchestrates all services
   - Assembles complete AgentConfig
   - Validation and error handling

2. **API Routers** (Step 3)
   - REST endpoints for prompt management
   - Prompt editing UI endpoints

3. **Integration** (Step 4)
   - AgentEngine loads assembled prompts
   - Celery workers use AgentLoader
   - End-to-end testing
