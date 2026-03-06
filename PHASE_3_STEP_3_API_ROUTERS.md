# Phase 3 Step 3: API Routers

**Status**: ✅ COMPLETE  
**Lines of Code**: 800+  
**Complexity**: High  
**Date**: 2024-03-05

## Overview

**Phase 3 Step 3** implementa los endpoints REST de la plataforma de agentes dinámicos. Todos los endpoints requieren autenticación JWT y aplican multi-tenancy obligatorio.

### Separación de Rutas

Se mantienen DOS grupos de rutas:

```
Phase 1/2 - Agent Execution (app/routers/agents.py)
├─ POST   /api/agents                    ✅ Create agent
├─ GET    /api/agents                    ✅ List agents
├─ GET    /api/agents/{id}               ✅ Get agent
├─ PATCH  /api/agents/{id}               ✅ Update agent
├─ DELETE /api/agents/{id}               ✅ Delete agent
├─ POST   /api/agents/{id}/execute       ✅ Execute agent
├─ GET    /api/agents/{id}/executions    ✅ Get execution
└─ GET    /api/agents/{id}/usage         ✅ Get usage stats

Phase 3 - Agent Configuration (app/routers/agent_platform.py)
├─ Agent Management
│  ├─ POST   /api/agent-platform/agents                           ✅ Create
│  ├─ GET    /api/agent-platform/agents                           ✅ List
│  ├─ GET    /api/agent-platform/agents/{agent_id}              ✅ Get
│  ├─ PUT    /api/agent-platform/agents/{agent_id}              ✅ Update
│  └─ DELETE /api/agent-platform/agents/{agent_id}              ✅ Delete
│
├─ Version Management
│  ├─ POST   /api/agent-platform/agents/{agent_id}/versions     ✅ Create version
│  ├─ GET    /api/agent-platform/agents/{agent_id}/versions     ✅ List versions
│  ├─ POST   /api/agent-platform/agents/{id}/versions/{v}/activate     ✅ Activate
│  └─ POST   /api/agent-platform/agents/{id}/versions/{v}/rollback    ✅ Rollback
│
├─ Tool Management
│  ├─ POST   /api/agent-platform/agents/{id}/versions/{v}/tools ✅ Add tool
│  ├─ GET    /api/agent-platform/agents/{id}/versions/{v}/tools ✅ List tools
│  ├─ DELETE /api/agent-platform/agents/{id}/versions/{v}/tools/{name} ✅ Remove tool
│  └─ PATCH  /api/agent-platform/agents/{id}/versions/{v}/tools/{name} ✅ Update tool
│
├─ Prompt Management
│  ├─ POST   /api/agent-platform/agents/{id}/versions/{v}/prompts ✅ Create prompt
│  ├─ GET    /api/agent-platform/agents/{id}/versions/{v}/prompts ✅ List prompts
│  ├─ PUT    /api/agent-platform/agents/{id}/versions/{v}/prompts/{type} ✅ Update prompt
│  └─ DELETE /api/agent-platform/agents/{id}/versions/{v}/prompts/{type} ✅ Delete prompt
│
└─ Configuration Loading
   └─ POST   /api/agent-platform/agents/{agent_id}/load         ✅ Load config
```

## Arquitectura HTTP

### Authentication Pattern

```python
# Request
GET /api/agent-platform/agents
Headers: Authorization: Bearer <jwt_token>

# Token Verification
Token Data = verify_token(token)
tenant_id = token_data.tenant_id  # Extracted from JWT
user_id = token_data.user_id

# All database queries filtered:
WHERE tenant_id = :tenant_id
```

### HTTP Status Codes

| Código  | Significado                 | Ejemplos                                   |
| ------- | --------------------------- | ------------------------------------------ |
| **200** | OK - GET exitoso            | Lista de agentes, detalles                 |
| **201** | Created - POST exitoso      | Agente creado, versión creada              |
| **202** | Accepted - Async processing | Ejecución encolada                         |
| **204** | No Content - DELETE exitoso | Agente eliminado                           |
| **400** | Bad Request                 | Datos inválidos                            |
| **401** | Unauthorized                | Token faltante/inválido                    |
| **403** | Forbidden                   | Permisos insuficientes                     |
| **404** | Not Found                   | Agente no existe                           |
| **409** | Conflict                    | Nombre duplicado, tool duplicada           |
| **422** | Unprocessable Entity        | Config inválida, versión sin system prompt |

## Endpoint Groups

### 1. Agent Management Endpoints

#### POST /api/agent-platform/agents

```python
Request:
{
    "name": "Customer Support Agent",
    "description": "Handles customer inquiries",
    "config": {"key": "value"}
}

Response (201):
{
    "id": "agent_123abc",
    "tenant_id": "tenant_456def",
    "name": "Customer Support Agent",
    "description": "Handles customer inquiries",
    "status": "draft",
    "config": {"key": "value"},
    "created_at": "2024-03-05T10:00:00",
    "updated_at": "2024-03-05T10:00:00"
}

Errors:
- 400: Invalid data
- 409: Name already exists
```

#### GET /api/agent-platform/agents

```python
Query Parameters:
- skip: int (default: 0)
- limit: int (default: 10, max: 100)

Response (200):
{
    "items": [
        {
            "id": "agent_123abc",
            "name": "Customer Support Agent",
            ...
        }
    ],
    "total": 5
}
```

#### GET /api/agent-platform/agents/{agent_id}

```python
Response (200):
{
    "id": "agent_123abc",
    "tenant_id": "tenant_456def",
    "name": "Customer Support Agent",
    ...
}

Errors:
- 404: Agent not found
- 403: Belongs to different tenant
```

#### PUT /api/agent-platform/agents/{agent_id}

```python
Request (partial update):
{
    "name": "Updated name",     # optional
    "description": "New desc",  # optional
    "config": {"key": "value"}  # optional
}

Response (200):
{
    "id": "agent_123abc",
    "name": "Updated name",
    ...
}
```

#### DELETE /api/agent-platform/agents/{agent_id}

```python
Response (204): No Content

Note: Soft delete (archives agent with status="archived")
```

---

### 2. Version Management Endpoints

#### POST /api/agent-platform/agents/{agent_id}/versions

```python
Request:
{
    "system_prompt": "You are a helpful assistant...",
    "configuration": {
        "llm_config": {
            "provider": "openai",
            "model": "gpt-4-turbo-preview",
            "temperature": 0.7,
            "max_tokens": 2048,
            "top_p": 1.0
        },
        "memory_config": {
            "type": "conversation",
            "max_history": 10
        }
    }
}

Response (201):
{
    "id": "version_456def",
    "agent_id": "agent_123abc",
    "version": "1.0",              # Auto-incremented
    "is_active": false,
    "system_prompt": "You are...",
    "configuration": {...},
    "created_at": "2024-03-05T10:05:00"
}

Errors:
- 404: Agent not found
- 422: Missing required LLM config
```

#### GET /api/agent-platform/agents/{agent_id}/versions

```python
Query Parameters:
- skip: int (default: 0)
- limit: int (default: 10)

Response (200):
{
    "items": [
        {
            "id": "version_456def",
            "version": "1.0",
            "is_active": false,
            ...
        }
    ],
    "total": 3
}
```

#### POST /api/agent-platform/agents/{agent_id}/versions/{version_id}/activate

```python
Request: {} (empty body)

Response (200):
{
    "id": "version_456def",
    "version": "1.0",
    "is_active": true,      # Changed from false
    ...
}

Behavior:
- Deactivates current active version
- Activates specified version
- Validates configuration before activation
```

#### POST /api/agent-platform/agents/{agent_id}/versions/{version_id}/rollback

```python
Request: {} (empty body)

Response (200):
{
    "id": "version_456def",
    "is_active": true,
    ...
}

Use case: Incident recovery (revert to previous known-good version)
```

---

### 3. Tool Management Endpoints

#### POST /api/agent-platform/agents/{id}/versions/{v}/tools

```python
Request:
{
    "tool_name": "google_search",
    "tool_config": {
        "timeout": 30,
        "max_results": 5
    }
}

Response (201):
{
    "id": "tool_789ghi",
    "agent_version_id": "version_456def",
    "name": "google_search",
    "enabled": true,
    "tool_config": {"timeout": 30, "max_results": 5},
    "created_at": "2024-03-05T10:10:00"
}

Validations:
✅ Tool exists in ToolRegistry
✅ Tool not already added to version

Errors:
- 404: Agent/version not found
- 409: Tool already added
- 422: Tool not in ToolRegistry
```

#### GET /api/agent-platform/agents/{id}/versions/{v}/tools

```python
Query Parameters:
- enabled_only: bool (default: False)
  - True:  Only enabled tools
  - False: All tools (enabled + disabled)
- skip: int (default: 0)
- limit: int (default: 10)

Response (200):
{
    "items": [
        {
            "id": "tool_789ghi",
            "name": "google_search",
            "enabled": true,
            "tool_config": {...}
        }
    ],
    "total": 3
}
```

#### PATCH /api/agent-platform/agents/{id}/versions/{v}/tools/{tool_name}

```python
Request:
{
    "enabled": false,                    # Optional
    "tool_config": {
        "timeout": 60,
        "max_results": 10
    }
}

Response (200):
{
    "id": "tool_789ghi",
    "name": "google_search",
    "enabled": false,              # Updated
    "tool_config": {...updated...}
}

Use case:
- Temporarily disable a tool without removing it
- Update tool-specific settings
```

#### DELETE /api/agent-platform/agents/{id}/versions/{v}/tools/{tool_name}

```python
Request: (no body)

Response (204): No Content

Note: Hard delete (removed from database)
```

---

### 4. Prompt Management Endpoints

#### POST /api/agent-platform/agents/{id}/versions/{v}/prompts

```python
Request:
{
    "prompt_type": "system",
    "prompt_content": "You are a helpful customer support agent..."
}

Valid Types:
- "system"      (REQUIRED - must be present)
- "instruction" (Optional)
- "context"     (Optional)
- "fallback"    (Optional)

Response (201):
{
    "id": "prompt_abc123",
    "agent_version_id": "version_456def",
    "prompt_type": "system",
    "prompt_content": "You are...",
    "created_by": "user_123",
    "created_at": "2024-03-05T10:15:00",
    "updated_at": "2024-03-05T10:15:00"
}

Constraint:
- UNIQUE(version_id, prompt_type)
- Only 1 system, 1 instruction, 1 context, 1 fallback per version

Errors:
- 404: Agent/version not found
- 409: Prompt of this type already exists
- 422: Invalid prompt type
```

#### GET /api/agent-platform/agents/{id}/versions/{v}/prompts

```python
Query Parameters:
- skip: int (default: 0)
- limit: int (default: 10)

Response (200):
{
    "items": [
        {
            "id": "prompt_abc123",
            "prompt_type": "system",
            "prompt_content": "You are...",
            ...
        }
    ],
    "total": 2
}
```

#### PUT /api/agent-platform/agents/{id}/versions/{v}/prompts/{prompt_type}

```python
Request:
{
    "prompt_content": "Updated prompt content..."
}

Response (200):
{
    "id": "prompt_abc123",
    "prompt_type": "system",
    "prompt_content": "Updated prompt content...",
    "updated_at": "2024-03-05T10:20:00"
}

Errors:
- 404: Prompt not found
- 422: Invalid prompt type
```

#### DELETE /api/agent-platform/agents/{id}/versions/{v}/prompts/{prompt_type}

```python
Request: (no body)

Response (204): No Content

Constraints:
- Cannot delete "system" prompt (required)
- Can delete "instruction", "context", "fallback"

Errors:
- 404: Prompt not found
- 422: Cannot delete required system prompt
```

---

### 5. Configuration Loading (Pre-Execution)

#### POST /api/agent-platform/agents/{agent_id}/load

```python
Request: {} (empty body)

Response (200):
{
    "agent_id": "agent_123abc",
    "version_number": "1.0",
    "system_prompt": "[SYSTEM]\nYou are a helpful assistant...\n\n[INSTRUCTIONS]\n...",
    "prompts": {
        "system": "You are a helpful assistant...",
        "instruction": "Be brief and professional.",
        "context": "Company founded in 2020...",
        "fallback": "I cannot help with that."
    },
    "llm_config": {
        "provider": "openai",
        "model": "gpt-4-turbo-preview",
        "temperature": 0.7,
        "max_tokens": 2048,
        "top_p": 1.0
    },
    "tools": [
        {
            "name": "google_search",
            "enabled": true,
            "config": {"timeout": 30}
        }
    ],
    "memory_config": {
        "type": "conversation",
        "max_history": 10,
        "enable_vector": false
    }
}

Validations:
✅ Agent exists + tenant verified
✅ Active version exists
✅ System prompt present
✅ All tools in ToolRegistry
✅ LLM config complete

Usage:
agent_config = await loader.load_agent(...)
agent = AgentEngine(agent_config)
result = await agent.execute("user query")

Errors:
- 404: Agent not found
- 403: Belongs to different tenant
- 422: Config validation failed
- 409: Data consistency error
```

## Autenticación y Autorización

### JWT Token Flow

```
┌─────────────────────────────────────┐
│  Client                             │
└────────────────┬────────────────────┘
                 │
                 │ POST /auth/login
                 │ {"email": "user@company.com", "password": "***"}
                 ▼
┌─────────────────────────────────────┐
│  Auth Service                       │
│  - Verify credentials               │
│  - Create JWT token                 │
└────────────────┬────────────────────┘
                 │
                 │ 200 OK
                 │ {"access_token": "eyJhbGc...", "token_type": "bearer"}
                 ▼
┌─────────────────────────────────────┐
│  Client stores token                │
└────────────────┬────────────────────┘
                 │
                 │ GET /api/agent-platform/agents
                 │ Headers: Authorization: Bearer eyJhbGc...
                 ▼
┌─────────────────────────────────────┐
│  API Router (agent_platform.py)     │
│  - Parse Authorization header       │
│  - Call verify_token(token)         │
│  - Extract: user_id, tenant_id,... │
└────────────────┬────────────────────┘
                 │
                 │ tenant_id mandatory in all queries:
                 │ WHERE tenant_id = :tenant_id
                 ▼
┌─────────────────────────────────────┐
│  Service Layer                      │
│  - Execute query with tenant filter │
│  - Return Pydantic schemas          │
└────────────────┬────────────────────┘
                 │
                 │ 200 OK
                 │ {"items": [...], "total": 5}
                 ▼
┌─────────────────────────────────────┐
│  Client                             │
└─────────────────────────────────────┘
```

### Token Payload

```python
{
    "user_id": "user_123abc",              # Identificador de usuario
    "tenant_id": "tenant_456def",          # Tenant ID - MANDATORY en todas las queries
    "email": "user@company.com",
    "exp": 1709623200,                     # Expiration timestamp
    "type": "access"                       # Token type: "access" o "refresh"
}
```

## Manejo de Errores

### Error Responses

Todos los errores siguen este patrón:

```json
{
  "detail": "Descripción del error"
}
```

### Ejemplos de Errores

**400 Bad Request** - Datos inválidos:

```json
{
  "detail": "name must contain at least 1 character"
}
```

**401 Unauthorized** - Token faltante/inválido:

```json
{
  "detail": "Invalid token: Token expired"
}
```

**403 Forbidden** - Permisos insuficientes (cross-tenant access):

```json
{
  "detail": "Agent agent_123 not found for tenant tenant_456"
}
```

**404 Not Found** - Recurso no existe:

```json
{
  "detail": "Agent agent_123 not found"
}
```

**409 Conflict** - Constraints violados:

```json
{
  "detail": "Agent with name 'Support Agent' already exists for tenant"
}
```

**422 Unprocessable Entity** - Validación fallida:

```json
{
  "detail": "Tool 'google_search' is not in ToolRegistry. Tool may have been removed from system."
}
```

## Almacenamiento de Caché (Opcional)

Para mejorar performance de endpoints frecuentes como `/load`:

```python
# En Redis
cache_key = f"agent_config:{tenant_id}:{agent_id}"
ttl = 3600  # 1 hora

# On load
config = redis.get(cache_key)
if config:
    return config

# Load from DB
config = await loader.load_agent(...)
redis.setex(cache_key, ttl, config.json())
return config

# Invalidate on change
await service.update_agent(...)
redis.delete(cache_key)
```

## Límites de Tasa (Rate Limiting)

### Propuesta de Límites

| Endpoint      | Tasa    | Ventana |
| ------------- | ------- | ------- |
| GET /agents   | 100 req | 1 min   |
| POST /agents  | 10 req  | 1 min   |
| GET /versions | 100 req | 1 min   |
| POST /load    | 50 req  | 1 min   |
| DELETE /\*    | 20 req  | 1 min   |

Middleware existente debería aplicar estos límites automáticamente.

## Documentación OpenAPI

El servidor incluye automáticamente:

- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **OpenAPI JSON**: http://localhost:8000/api/openapi.json

Todos los endpoints incluyen docstrings detallados que se renderean automáticamente.

## Archivos Modificados/Creados

- ✅ **Created**: `app/routers/agent_platform.py` (+800 líneas)
- ✅ **Modified**: `app/main.py` (agregado router de Phase 3)
- ✅ **Created**: `PHASE_3_STEP_3_API_ROUTERS.md` (este archivo)

## Testing

### Ejemplos de cURL

```bash
# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@company.com",
    "password": "password"
  }'

# Respuesta
{"access_token": "eyJhbGc...", "token_type": "bearer"}

# Create agent
curl -X POST http://localhost:8000/api/agent-platform/agents \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Support Agent",
    "description": "Customer support",
    "config": {}
  }'

# Create version
curl -X POST http://localhost:8000/api/agent-platform/agents/agent_123/versions \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "Content-Type: application/json" \
  -d '{
    "system_prompt": "You are helpful...",
    "configuration": {
      "llm_config": {
        "provider": "openai",
        "model": "gpt-4",
        "temperature": 0.7,
        "max_tokens": 2048
      }
    }
  }'

# Load configuration
curl -X POST http://localhost:8000/api/agent-platform/agents/agent_123/load \
  -H "Authorization: Bearer eyJhbGc..."
```

---

**Status**: ✅ IMPLEMENTATION COMPLETE

**Next Steps**:

1. Phase 3 Step 4: Integration with AgentEngine
2. Testing (unit tests + integration tests)
3. Performance optimization + caching
