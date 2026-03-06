# Agent Framework Complete

## 📐 Arquitectura Implementada

El sistema ahora cuenta con un framework completo de agentes con soporte para:

### 1️⃣ LLM Provider Abstraction (`app/llm/`)

**Propósito**: Permitir múltiples proveedores de LLM sin cambiar el código del agente.

**Componentes**:

- `BaseLLMProvider`: Clase base para todos los providers
- `OpenAIProvider`: Soporte para GPT-4, GPT-3.5
- `AnthropicProvider`: Soporte para Claude 2/3/Opus
- `ProviderRegistry`: Registro centralizado de providers

**Ejemplo de uso**:

```python
from app.llm import ProviderRegistry

# Obtener provider
provider = ProviderRegistry.get_provider(
    name="openai",
    model="gpt-4-turbo-preview"
)

# O
provider = ProviderRegistry.get_provider(
    name="anthropic",
    model="claude-3-opus-20240229"
)

# Llamar LLM
response = await provider.call(
    messages=[LLMMessage(role="user", content="Hello!")],
    temperature=0.7,
    max_tokens=2048,
    tools=[...]  # Tool definitions
)
```

**Agregar nuevo provider**:

```python
from app.llm import BaseLLMProvider, ProviderRegistry

class MyProviderProvider(BaseLLMProvider):
    async def call(self, messages, temperature, max_tokens, tools, **kwargs):
        # Implementar lógica
        pass

    async def validate_connection(self):
        # Validar conexión
        pass

# Registrar
ProviderRegistry.register("my_provider", MyProviderProvider)
```

---

### 2️⃣ Tool System (`app/tools/`)

**Propósito**: Permitir que agentes ejecuten acciones externas.

**Componentes**:

- `BaseTool`: Clase base para herramientas
- `ToolRegistry`: Registro de herramientas disponibles
- `ToolExecutor`: Ejecuta herramientas cuando el LLM las solicita
- Built-in Tools:
  - `HTTPRequestTool`: Hacer HTTP requests
  - `CalculatorTool`: Cálculos matemáticos
  - `DatabaseQueryTool`: Queries a PostgreSQL (read-only)

**Ejemplo - HTTPRequestTool**:

```python
from app.tools import ToolRegistry

# Obtener herramienta registrada
http_tool = ToolRegistry.get_tool("http_request")

# O ver todas herramientas disponibles
tools = ToolRegistry.list_tools()
# ['http_request', 'calculator', 'database_query']

# Obtener en formato para LLM
llm_tools = ToolRegistry.get_tools_for_llm(['http_request', 'calculator'])
```

**Crear herramienta personalizada**:

```python
from app.tools import BaseTool, ToolOutput, ToolRegistry

class SendEmailTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="send_email",
            description="Send an email to a recipient"
        )

    def get_schema(self):
        return {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"}
            },
            "required": ["to", "subject", "body"]
        }

    async def execute(self, to: str, subject: str, body: str, **kwargs):
        try:
            # Implementar envío
            # await send_email(to, subject, body)
            return ToolOutput(success=True, result={"message_id": "123"})
        except Exception as e:
            return ToolOutput(success=False, error=str(e))

# Registrar
ToolRegistry.register(SendEmailTool())

# Usar en agente
agent_config = {
    "tools": ["http_request", "send_email", "calculator"]
}
```

**Flow - Cómo trabaja con el LLM**:

1. Agente incluye herramientas en prompt al LLM
2. LLM decide si necesita usar una herramienta
3. Si sí, solicita: `{tool_name: "http_request", tool_input: {url: "...", method: "GET"}}`
4. ToolExecutor ejecuta la herramienta
5. Resultado se retorna al LLM
6. LLM continúa razonando con la nueva información

---

### 3️⃣ Memory System (`app/memory/`)

**Propósito**: Mantener contexto de conversaciones y búsqueda semántica.

**Componentes**:

- `BaseMemory`: Clase base abstracta
- `ConversationMemory`: Memoria de corto plazo (Redis)
  - Últimos N mensajes para contexto
  - Rápido acceso
  - Expira después de 7 días
- `VectorMemory`: Memoria de largo plazo (vector-ready)
  - Preparada para embedding/RAG
  - Búsqueda semántica (futura)
  - Puede exportarse a Pinecone/Weaviate
- `MemoryManager`: Gestor centralizado de ambas

**Ejemplo**:

```python
from app.memory import MemoryManager

# Crear manager
memory = MemoryManager(memory_id="conversation-123")

# Agregar mensaje
await memory.add_message(role="user", content="Hola")
await memory.add_message(role="assistant", content="¿Cómo estás?")

# Obtener contexto para LLM
context = await memory.get_context_for_llm(max_tokens=2000)
# Retorna: formatted conversation history

# Buscar en memoria
results = await memory.search_memory(
    query="Qué tipo de base de datos",
    use_vector=True,
    limit=5
)

# Limpiar sesión pero mantener vector memory
await memory.prepare_for_new_session()

# Limpiar todo
await memory.clear_all()

# Ver resumen
summary = await memory.get_memory_summary()
```

**Preparación para RAG (futuro)**:

```python
# VectorMemory ya almacena embeddings
messages = await vector_memory.get_messages()

# Exportar para vector DB
export_data = await vector_memory.export_for_vector_db()
# Cada item tiene: message_id, content, embedding, metadata

# Entonces mover a Pinecone:
# for item in export_data:
#     pinecone_index.upsert(item.message_id, item.embedding, item.metadata)
```

---

### 4️⃣ Agent Execution Orchestrator (`app/engine/`)

**Propósito**: Orquestar flujo de ejecución del agente.

**Flow**:

```
1. Load Agent Configuration
   ├─ Cargar parámetros del agent
   ├─ Validar LLM provider
   └─ Validar tools permitidas

2. Build Prompt
   ├─ System prompt
   ├─ Conversation history (de memoria)
   └─ User input

3. Call LLM Provider
   ├─ Enviar mensajes al LLM
   ├─ Incluir tools disponibles
   └─ Recibir respuesta

4. Parse LLM Response
   ├─ ¿Retorna texto? → avanza a paso 6
   ├─ ¿Solicita tool? → avanza a paso 5
   └─ retry si parseado falló

5. Execute Tools (Loop)
   ├─ Tool executor ejecuta herramienta
   ├─ Obtiene resultado
   ├─ Agrega resultado a historial
   └─ Vuelve a paso 3 (max N veces)

6. Update Memory
   ├─ Guardar respuesta final
   ├─ Actualizar conversation memory
   └─ Opcionalmente vector memory

7. Return Result
   ├─ Response text
   ├─ ExecutionContext (metadata)
   └─ Logs de pasos
```

**Ejemplo**:

```python
from app.engine import AgentEngine
from app.memory import MemoryManager
from app.schemas.agent_config import AgentConfig, AgentLLMConfig

engine = AgentEngine()

# Configurar agent
config = AgentConfig(
    name="Research Assistant",
    system_prompt="You are a research assistant that finds information.",
    llm=AgentLLMConfig(
        provider="openai",
        model="gpt-4-turbo-preview",
        temperature=0.7,
        max_tokens=2048
    ),
    tools=["http_request", "database_query"],
    max_tool_loops=5
)

# Preparar memoria
memory = MemoryManager(memory_id="conversation-123")

# Ejecutar
result = await engine.execute(
    agent_config=config.to_dict(),
    user_input="Find me the latest Bitcoin price",
    execution_id="exec-123",
    agent_id="agent-123",
    user_id="user-123",
    tenant_id="tenant-123",
    memory_manager=memory,
)

if result["success"]:
    print(result["response"])  # "The current Bitcoin price is..."
    ctx = result["execution_context"]
    print(f"Tokens: {ctx.prompt_tokens + ctx.completion_tokens}")
    print(f"Tools called: {len(ctx.tools_executed)}")
    for step in ctx.steps:
        print(f"  {step.action}: {step.success}")
else:
    print(f"Error: {result['error']}")
```

---

## 🔄 Integración con REST API

El router de agents (`app/routers/agents.py`) fue mejorado:

**Crear agent**:

```bash
POST /api/agents
{
  "name": "Support Bot",
  "config": {
    "system_prompt": "You are a support agent...",
    "llm_provider": "openai",
    "llm_model": "gpt-4-turbo-preview",
    "tools": ["http_request", "database_query"],
    "temperature": 0.7,
    "max_tokens": 2048
  }
}
```

**Ejecutar agent (async)**:

```bash
POST /api/agents/{agent_id}/execute
{
  "message": "What's my order status?"
}

# Respuesta inmediata (202):
{
  "execution_id": "exec-...",
  "status": "pending"
}
```

**Obtener resultado**:

```bash
GET /api/agents/{agent_id}/executions/{execution_id}

# Respuesta cuando completed:
{
  "status": "completed",
  "response": "Your order #123 is being shipped",
  "execution_time_ms": 3421,
  "logs": [
    {"step": 1, "action": "load_config", ...},
    {"step": 2, "action": "build_prompt", ...},
    {"step": 3, "action": "call_llm", ...},
    {"step": 4, "action": "execute_tool", ...},
    ...
  ]
}
```

---

## 🚀 Configuración para Producción

### Variables de entorno necesarias:

```bash
# Base de datos
DATABASE_URL=postgresql://user:password@localhost:5432/saas_agents

# Redis
REDIS_URL=redis://localhost:6379/0

# OpenAI (si usas OpenAI)
OPENAI_API_KEY=sk-...

# Anthropic (si usas Anthropic)
ANTHROPIC_API_KEY=sk-ant-...

# General
DEBUG=false
SECRET_KEY=your-secret-key-here
API_TITLE="AI Agents SaaS Platform"
```

### Múltiples providers a la vez:

```python
# Cada agente elige su provider
agent_1 = {
    "llm_provider": "openai",
    "llm_model": "gpt-4-turbo-preview"
}

agent_2 = {
    "llm_provider": "anthropic",
    "llm_model": "claude-3-opus-20240229"
}

agent_3 = {
    "llm_provider": "openai",
    "llm_model": "gpt-3.5-turbo"  # Más barato
}

# Cada uno cuesta diferente → Billing integrado
```

---

## 📊 Monitoreo y Observabilidad

Cada ejecución almacena:

```
ExecutionLog (por paso):
- step_number
- action (load_config, build_prompt, call_llm, execute_tool, etc.)
- details (configuración, respuestas)
- duration_ms
- success / error

AgentUsage (por ejecución):
- input_tokens / output_tokens
- cost_usd (para billing)
- execution_time_ms
- model_used
```

**Queries útiles**:

```sql
-- Uso mensuales
SELECT
    DATE_TRUNC('month', created_at) as month,
    SUM(total_tokens) as tokens,
    SUM(cost_usd) as cost,
    COUNT(*) as executions
FROM agent_usage
GROUP BY month
ORDER BY month DESC;

-- Herramientas más usadas
SELECT
    details->>'tool_name' as tool_name,
    COUNT(*) as usage_count
FROM execution_logs
WHERE action = 'execute_tool'
GROUP BY tool_name
ORDER BY usage_count DESC;

-- Providers más usados
SELECT
    model_used,
    COUNT(*) as count,
    SUM(cost_usd) as total_cost
FROM agent_usage
GROUP BY model_used;
```

---

## ✅ Checklist para Usar

- [ ] Instalar dependencias: `pip install -r requirements.txt`
- [ ] Configurar `.env` con API keys
- [ ] Iniciar PostgreSQL y Redis
- [ ] Ejecutar migrations (si existen)
- [ ] Iniciar API: `uvicorn app.main:app --reload`
- [ ] Iniciar workers: `celery -A app.workers.celery_worker worker`
- [ ] Crear agente con `/api/agents POST`
- [ ] Ejecutar agente con `/api/agents/{id}/execute POST`
- [ ] Verificar resultado con `/api/agents/{id}/executions/{exec_id} GET`

---

## 🔗 Próximos Pasos

1. **Integración de Embeddings**: Usar OpenAI embeddings en VectorMemory
2. **Vector DB**: Conectar Pinecone/Weaviate para RAG
3. **Custom Tools**: Agregar herramientas específicas del negocio
4. **Streaming**: Soporte para streaming de respuestas (Server-Sent Events)
5. **Advanced Prompting**: Chain-of-thought, few-shot examples
6. **Monitoring Dashboard**: UI para visualizar execuciones
