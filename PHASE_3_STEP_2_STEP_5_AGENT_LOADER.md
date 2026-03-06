# Phase 3 Step 2.5: AgentLoader Service

**Status**: ✅ COMPLETE  
**Lines of Code**: 450+  
**Complexity**: High  
**Date**: 2024-03-05

## Overview

El **AgentLoader** es el orquestador central que transforma la configuración almacenada en la base de datos en un **AgentConfig** runtime listo para ser ejecutado por el **AgentEngine**.

### Responsabilidades Principales

```
┌─────────────────────────┐
│   Database Records      │
│ (Agent, Version, Tools  │
│  Prompts, LLM Config)   │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│    AgentLoader          │
│  (Orchestrator)         │
│                         │
│ - Validate agent        │
│ - Load version          │
│ - Load prompts          │
│ - Load tools            │
│ - Assemble config       │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│    AgentConfig          │
│  (Pydantic Schema)      │
│                         │
│  - agent_id             │
│  - version_number       │
│  - system_prompt        │
│  - prompts              │
│  - llm_config           │
│  - tools                │
│  - memory_config        │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│    AgentEngine          │
│  (Executor)             │
│  ready for .execute()   │
└─────────────────────────┘
```

## Método Principal: load_agent()

El método público que actúa como entry point principal:

```python
async def load_agent(
    db: AsyncSession,
    agent_id: str,
    tenant_id: str,
) -> AgentConfig:
    """Cargar configuración completa del agente."""
```

### Flujo Operacional

```
load_agent(db, "agent_123", "tenant_456")
│
├─> _load_agent_record()
│   │
│   ├─ Query: SELECT Agent WHERE id=agent_123 AND tenant_id=tenant_456
│   ├─ Validate: Agent exists
│   ├─ Validate: Agent NOT archived
│   └─ Return: Agent ORM record
│
├─> _load_agent_version()
│   │
│   ├─ Query: SELECT AgentVersion WHERE agent_id=agent_123 AND is_active=True
│   ├─ Validate: Exactly 1 active version
│   └─ Return: AgentVersion ORM record
│
├─> _load_agent_prompts()
│   │
│   ├─ Query: SELECT AgentPrompt WHERE version_id=version_456
│   ├─ Validate: System prompt exists (required)
│   ├─ Validate: Instruction/Context/Fallback optional
│   └─ Return: AgentPromptConfigItem Pydantic schema
│
├─> _load_agent_tools()
│   │
│   ├─ Query: SELECT AgentTool WHERE version_id=version_456 AND enabled=True
│   ├─ For each tool:
│   │  ├─ Cross-check against ToolRegistry
│   │  └─ Validate tool still exists in system
│   └─ Return: List[AgentToolConfigItem]
│
└─> _assemble_agent_config()
    │
    ├─ Parse version.configuration JSON
    ├─ Extract LLM config
    ├─ Extract memory config
    ├─ Assemble final system_prompt
    └─ Return: AgentConfig (ready for AgentEngine)
```

## Métodos Privados (Helpers)

### 1. \_load_agent_record()

**Responsabilidad**: Cargar y validar el registro del agente

**Validaciones**:

- ✅ El agente existe
- ✅ El agente pertenece al tenant especificado
- ✅ El agente NO está archivado

**Raises**:

- `ResourceNotFoundError`: Agente no encontrado
- `PermissionDeniedError`: Agente pertenece a otro tenant

**Patrón de Seguridad Multi-tenant**:

```python
stmt = select(Agent).where(
    Agent.id == agent_id,
    Agent.tenant_id == tenant_id,  # ← CRITICAL: Prevent cross-tenant access
)
```

### 2. \_load_agent_version()

**Responsabilidad**: Cargar la versión activa del agente

**Validaciones**:

- ✅ Existe al menos una versión activa
- ✅ Existe exactamente una versión activa (no múltiples)
- ✅ La versión sigue formato semántico (1.0, 1.1, 2.0)

**Raises**:

- `ValidationError`: No hay versión activa
- `ConflictError`: Múltiples versiones activas (error de BD)

**Nota**: Solo retorna versiones con `is_active=True`. Esta restricción garantiza que siempre se use una versión conocida y probada.

### 3. \_load_agent_prompts()

**Responsabilidad**: Cargar todos los prompts para la versión

**Estructura de Prompts**:

| Tipo          | Requerido | Uso                                     | Default             |
| ------------- | --------- | --------------------------------------- | ------------------- |
| `system`      | ✅ SÍ     | Instrucciones base para el agente       | N/A                 |
| `instruction` | ❌ No     | Instrucciones operacionales adicionales | AgentEngine default |
| `context`     | ❌ No     | Contexto/información de fondo           | Ninguno             |
| `fallback`    | ❌ No     | Respuesta si algo falla                 | Generic fallback    |

**Organización por tipos**:

```python
# Database stores individual prompts
AgentPrompt.prompt_type = PromptType.SYSTEM
AgentPrompt.prompt_type = PromptType.INSTRUCTION
AgentPrompt.prompt_type = PromptType.CONTEXT
AgentPrompt.prompt_type = PromptType.FALLBACK

# Loader groups them
AgentPromptConfigItem(
    system="...",           # REQUIRED
    instruction="...",      # Optional
    context="...",          # Optional
    fallback="...",         # Optional
)
```

**Validaciones**:

- ✅ System prompt siempre presente (required)
- ✅ Otros tipos son opcionales

**Raises**:

- `ValidationError`: System prompt faltante

### 4. \_load_agent_tools()

**Responsabilidad**: Cargar herramientas habilitadas con validación

**Validaciones Críticas**:

1. ✅ Herramienta existe en BD
2. ✅ Herramienta está `enabled=True`
3. ✅ **Herramienta existe en ToolRegistry global** (después del deployment)
4. ✅ Configuración por herramienta se incluye

**¿Por qué validar contra ToolRegistry?**

```
Scenario 1 - Normal:
┌──────────────┐         ┌──────────────┐
│   Database   │         │  ToolRegistry│
│              │         │              │
│- google_api  │────────▶│- google_api  │ ✅ Match - OK
└──────────────┘         └──────────────┘

Scenario 2 - After Upgrade:
┌──────────────┐         ┌──────────────┐
│   Database   │         │  ToolRegistry│
│              │         │              │
│- old_api     │────✗───▶│- new_api     │ ❌ Mismatch - FAIL
│              │         │- modern_api  │
└──────────────┘         └──────────────┘
```

**Manejo de Errores**:

```python
if tool_db.name not in available_tools:
    raise ValidationError(
        f"Tool '{tool_db.name}' is not in ToolRegistry. "
        "Tool may have been removed from system."
    )
```

**Raises**:

- `ValidationError`: Herramienta no existe en ToolRegistry

### 5. \_assemble_agent_config()

**Responsabilidad**: Ensamblar la configuración final completa

**Operaciones**:

1. **Parse LLM Config** (from version.configuration JSON):

```python
llm_config_data = version_config.get("llm_config")
llm_config = AgentLLMConfig(**llm_config_data)
```

**Estructura esperada**:

```json
{
  "llm_config": {
    "provider": "openai",
    "model": "gpt-4-turbo-preview",
    "temperature": 0.7,
    "max_tokens": 2048,
    "top_p": 1.0
  }
}
```

2. **Parse Memory Config** (optional, con defaults):

```python
memory_config_data = version_config.get("memory_config", {})
memory_config = AgentMemoryConfig(**memory_config_data)
```

3. **Assemble Final System Prompt** (template formatting):

```python
[SYSTEM]
{system_prompt}

[INSTRUCTIONS]
{instruction_prompt}

[CONTEXT]
{context_prompt}
```

**Ejemplo**:

```
[SYSTEM]
You are a customer support agent.

[INSTRUCTIONS]
Be brief. Maximum 2 paragraphs.

[CONTEXT]
Company was founded in 2020. Handles 100K clients.
```

4. **Combine into AgentConfig**:

```python
AgentConfig(
    agent_id="agent_123abc",
    version_number="1.1",
    system_prompt="[SYSTEM]\nYou are...",
    prompts=prompts,
    llm_config=llm_config,
    tools=tools,
    memory_config=memory_config,
)
```

**Validaciones**:

- ✅ LLM config presente y válido
- ✅ Memory config presente (con defaults si falta)
- ✅ System prompt puede ensamblarse

**Raises**:

- `ValidationError`: LLM config faltante

## Modelos Pydantic de Configuración

### AgentLLMConfig

```python
class AgentLLMConfig(BaseModel):
    provider: str              # "openai", "anthropic", etc.
    model: str                 # "gpt-4", "claude-3", etc.
    temperature: float = 0.7
    max_tokens: Optional[int]
    top_p: Optional[float]
    frequency_penalty: Optional[float]
    presence_penalty: Optional[float]
```

### AgentToolConfigItem

```python
class AgentToolConfigItem(BaseModel):
    name: str                  # "google_search", "email_send", etc.
    enabled: bool              # Must be True to include
    config: dict               # Tool-specific config (timeouts, limits, etc.)
```

### AgentPromptConfigItem

```python
class AgentPromptConfigItem(BaseModel):
    system: str                # REQUIRED
    instruction: Optional[str] # Optional
    context: Optional[str]     # Optional
    fallback: Optional[str]    # Optional
```

### AgentMemoryConfig

```python
class AgentMemoryConfig(BaseModel):
    type: str = "conversation"     # "conversation", "semantic", etc.
    max_history: int = 10          # Conversation history size
    enable_vector: bool = False    # Vector memory support
    vector_similarity_threshold: Optional[float]  # For semantic search
```

### AgentConfig (Main Output)

```python
class AgentConfig(BaseModel):
    agent_id: str                          # "agent_123abc"
    version_number: str                    # "1.1"
    system_prompt: str                     # Final assembled prompt
    prompts: AgentPromptConfigItem         # Individual prompt items
    llm_config: AgentLLMConfig             # LLM parameters
    tools: list[AgentToolConfigItem]       # Available tools
    memory_config: AgentMemoryConfig       # Memory settings
```

## Restricciones Arquitectónicas

### 1. **Nunca ejecuta herramientas**

- Solo gestiona configuración
- La ejecución es responsabilidad de AgentEngine

### 2. **Validación cruzada con ToolRegistry**

- Garantiza consistencia post-deployment
- Detecta herramientas removidas o renombradas

### 3. **Multi-tenancy obligatorio**

```python
# SIEMPRE filtrar por tenant_id
select(Agent).where(
    Agent.id == agent_id,
    Agent.tenant_id == tenant_id,  # ← No opcional
)
```

### 4. **System prompt siempre requerido**

- Sin system prompt = no se puede cargar el agente
- Otros prompts tienen defaults en AgentEngine

### 5. **Transacciones de lectura**

- NO hace commits (lectura solamente)
- Usa `asyncio` con AsyncSession

## Manejo de Errores

| Escenario                  | Excepción               | Código del Cliente       |
| -------------------------- | ----------------------- | ------------------------ |
| Agente no existe           | `ResourceNotFoundError` | 404 Not Found            |
| Permisos insuficientes     | `PermissionDeniedError` | 403 Forbidden            |
| Agente archivado           | `ValidationError`       | 422 Unprocessable Entity |
| No hay versión activa      | `ValidationError`       | 422 Unprocessable Entity |
| Herramienta no en registry | `ValidationError`       | 422 Unprocessable Entity |
| LLM config faltante        | `ValidationError`       | 422 Unprocessable Entity |
| System prompt faltante     | `ValidationError`       | 422 Unprocessable Entity |

## Casos de Uso

### Caso 1: Cargar agente para ejecución

```python
# En API route handler
loader = get_agent_loader()
config = await loader.load_agent(db, "agent_123", "tenant_456")
engine = AgentEngine(config)
result = await engine.execute("user query")
```

### Caso 2: Validar configuración antes de activar

```python
# En AgentVersionService.activate_version()
try:
    config = await loader.load_agent(db, agent_id, tenant_id)
    # Si llegamos aquí, la versión es válida para ser activada
except ValidationError as e:
    # Versión inválida, no activar
```

### Caso 3: Pre-flight check en UI

```python
# En frontend, antes de permitir que usuario ejecute agente
POST /agents/{agent_id}/validate
-> Internamente: loader.load_agent()
-> Si falla: mostrar error amigable al usuario
-> Si success: "Agent ready to execute"
```

## Integración con Otros Componentes

### Con AgentService

```
AgentService.get_agent()
     ↓
Retorna AgentResponse con datos básicos
     ↓
Cliente llama loader.load_agent()
     ↓
Obtiene AgentConfig completo
```

### Con AgentVersionService

```
AgentVersionService.activate_version()
     ↓
Valida version internamente
     ↓
Pero AgentLoader hace validación final
     ↓
Detecta inconsistencias (tools removidas, etc.)
```

### Con AgentToolService

```
AgentToolService.add_tool_to_version()
     ↓
Valida contra ToolRegistry
     ↓
AgentLoader también valida (segunda barrera)
     ↓
Garantiza consistencia
```

### Con AgentEngine

```
AgentEngine.__init__(config: AgentConfig)
     ↓
Config viene de loader.load_agent()
     ↓
No necesita acceso a BD
     ↓
Es completamente autocontido
```

## Patrón Singleton

```python
_loader_instance: Optional[AgentLoader] = None

def get_agent_loader() -> AgentLoader:
    """Obtener instancia singleton."""
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = AgentLoader()
    return _loader_instance
```

**Uso en rutas**:

```python
from app.agents import get_agent_loader

@router.post("/agents/{agent_id}/execute")
async def execute_agent(db: AsyncSession, agent_id: str, tenant_id: str):
    loader = get_agent_loader()
    config = await loader.load_agent(db, agent_id, tenant_id)
    # ... rest of logic
```

## Pruebas Unitarias (Pseudocódigo)

```python
# test_agent_loader.py

class TestAgentLoader:

    async def test_load_agent_success(self):
        """Cargar agente exitosamente."""
        # Arrange: Create agent + version + prompts + tools
        # Act: load_agent()
        # Assert: AgentConfig returned correctly

    async def test_load_agent_not_found(self):
        """Agente no existe."""
        # Assert: ResourceNotFoundError

    async def test_load_agent_wrong_tenant(self):
        """Agente pertenece a otro tenant."""
        # Assert: PermissionDeniedError

    async def test_load_agent_no_active_version(self):
        """No hay versión activa."""
        # Assert: ValidationError

    async def test_load_agent_missing_system_prompt(self):
        """System prompt faltante."""
        # Assert: ValidationError

    async def test_load_agent_tool_not_in_registry(self):
        """Herramienta no está en ToolRegistry."""
        # Assert: ValidationError

    async def test_load_agent_missing_llm_config(self):
        """LLM config faltante."""
        # Assert: ValidationError

    async def test_system_prompt_assembly(self):
        """Verificar ensamblaje de system prompt."""
        # Assert: Contiene [SYSTEM], [INSTRUCTIONS], [CONTEXT]
```

## Performance Considerations

### Consultas a BD

```
_load_agent_record()       → 1 SELECT
_load_agent_version()      → 1 SELECT
_load_agent_prompts()      → 1 SELECT (retorna múltiples rows)
_load_agent_tools()        → 1 SELECT (retorna múltiples rows)
─────────────────────────────────────
Total:                     → 4 SELECTs
```

**Posible optimización futura: JOIN en una sola query** (si BD no es bottleneck)

### Validación de ToolRegistry

```python
available_tools = registry.get_all_tools()  # O(1) in-memory dict
for tool_db in tools_db:
    if tool_db.name not in available_tools:  # O(1) dict lookup
        raise ValidationError(...)
```

**O(N)** where N = number of tools (típicamente <50, negligible)

## Archivos Relacionados

- `app/agents/agent_loader.py` - Implementación
- `app/agents/schemas.py` - Pydantic models
- `app/models/agent_platform.py` - ORM models
- `app/tools/tool_registry.py` - Tool registry validation
- `app/core/exceptions.py` - Custom exceptions

---

**Status**: ✅ IMPLEMENTATION COMPLETE

**Next Steps**:

1. Phase 3 Step 3: API Routers (REST endpoints)
2. Phase 3 Step 4: Integration with AgentEngine
