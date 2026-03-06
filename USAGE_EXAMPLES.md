# Ejemplos de Uso - Nueva Arquitectura

## 1. Workflow Completo: Crear y Ejecutar Agente

### Paso 1: Registrarse

```bash
curl -X POST "http://localhost:8000/api/auth/register?tenant_slug=mycompany" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@mycompany.com",
    "username": "john_doe",
    "password": "secure_password_123"
  }'
```

**Respuesta (201):**

```json
{
  "user": {
    "id": "user-123",
    "email": "user@mycompany.com",
    "username": "john_doe",
    "tenant_id": "tenant-456",
    "is_active": true,
    "is_admin": false,
    "created_at": "2024-01-15T10:30:00"
  },
  "access_token": "eyJhbGciOiJIUzI1N...",
  "refresh_token": "eyJhbGciOiJIUzI1N..."
}
```

### Paso 2: Crear Agente

```bash
TOKEN="eyJhbGciOiJIUzI1N..."

curl -X POST "http://localhost:8000/api/agents" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Customer Support Bot",
    "description": "Responds to customer inquiries",
    "agent_type": "chat",
    "system_prompt": "You are a helpful customer support agent.",
    "model": "gpt-4",
    "config": {
      "temperature": 0.7,
      "max_tokens": 2000
    }
  }'
```

**Respuesta (201):**

```json
{
  "id": "agent-789",
  "name": "Customer Support Bot",
  "tenant_id": "tenant-456",
  "created_by": "user-123",
  "agent_type": "chat",
  "model": "gpt-4",
  "system_prompt": "You are a helpful customer support agent.",
  "config": { "temperature": 0.7 },
  "version": 1,
  "is_active": true,
  "created_at": "2024-01-15T10:31:00"
}
```

### Paso 3: Ejecutar Agente (ASYNC)

**Importante:** La ejecución es ahora **asincrónica**. La API retorna **202 Accepted** inmediatamente.

```bash
curl -X POST "http://localhost:8000/api/agents/agent-789/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input_data": {
      "message": "How do I reset my password?",
      "user_id": "customer-123",
      "context": {
        "account_status": "active",
        "previous_messages": 2
      }
    }
  }'
```

**Respuesta (202 Accepted):**

```json
{
  "id": "exec-001",
  "agent_id": "agent-789",
  "status": "pending",
  "input_data": {
    "message": "How do I reset my password?",
    "user_id": "customer-123"
  },
  "output_data": null,
  "error_message": null,
  "execution_time_ms": null,
  "created_at": "2024-01-15T10:32:00",
  "completed_at": null
}
```

**Nota:** El cliente recibe el `execution_id` ("exec-001") para hacer polling del estado.

### Paso 4: Consultar Estado de Ejecución

Mientras el worker procesa, consulta el estado:

```bash
curl -X GET "http://localhost:8000/api/agents/agent-789/executions/exec-001" \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta 1 (En progreso - 200):**

```json
{
  "id": "exec-001",
  "agent_id": "agent-789",
  "status": "running",
  "input_data": {...},
  "output_data": null,
  "execution_time_ms": null,
  "completed_at": null,
  "logs": [
    {
      "id": "log-001",
      "execution_id": "exec-001",
      "step": 1,
      "action": "input_received",
      "details": {"input": "How do I reset my password?"},
      "timestamp": "2024-01-15T10:32:00.100"
    },
    {
      "id": "log-002",
      "execution_id": "exec-001",
      "step": 2,
      "action": "prompt_built",
      "details": {"message_count": 3},
      "timestamp": "2024-01-15T10:32:00.200"
    }
  ]
}
```

**Respuesta 2 (Completada - 200):**

```json
{
  "id": "exec-001",
  "agent_id": "agent-789",
  "status": "completed",
  "input_data": {...},
  "output_data": {
    "response": "To reset your password, please visit our website...",
    "success": true
  },
  "execution_time_ms": 2340,
  "completed_at": "2024-01-15T10:32:02.340",
  "logs": [
    {"step": 1, "action": "input_received", ...},
    {"step": 2, "action": "prompt_built", ...},
    {"step": 3, "action": "llm_response_received", "details": {"tokens_used": 245}},
    {"step": 4, "action": "execution_completed", ...}
  ]
}
```

## 2. Control de Acceso (RBAC)

### Asignar Rol a Usuario

Solo el **owner** puede cambiar roles:

```bash
curl -X POST "http://localhost:8000/api/users/tenant/members/user-123/role" \
  -H "Authorization: Bearer $OWNER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role": "admin"}'
```

**Respuesta:**

```json
{
  "id": "tenant-user-001",
  "user_id": "user-123",
  "tenant_id": "tenant-456",
  "role": "admin",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00"
}
```

### Listar Miembros del Tenant

Solo **admin** o **owner** pueden ver esto:

```bash
curl -X GET "http://localhost:8000/api/users/tenant/members" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Respuesta:**

```json
[
  {
    "id": "tenant-user-001",
    "user_id": "user-123",
    "tenant_id": "tenant-456",
    "role": "admin",
    "is_active": true,
    "created_at": "2024-01-15T10:30:00"
  },
  {
    "id": "tenant-user-002",
    "user_id": "user-456",
    "tenant_id": "tenant-456",
    "role": "member",
    "is_active": true,
    "created_at": "2024-01-15T10:31:00"
  }
]
```

## 3. Tracking de Uso

### Ver Estadísticas del Tenant

Solo **admin**:

```bash
curl -X GET "http://localhost:8000/api/agents/usage/summary?days=30" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Respuesta:**

```json
{
  "period_start": "2023-12-16T10:32:00",
  "period_end": "2024-01-15T10:32:00",
  "total_executions": 1250,
  "successful_executions": 1232,
  "failed_executions": 18,
  "total_tokens": 245000,
  "average_execution_time_ms": 2340,
  "total_cost_usd": 12.45
}
```

### Ver Uso de Agente Específico

```bash
curl -X GET "http://localhost:8000/api/agents/agent-789/usage?days=7" \
  -H "Authorization: Bearer $TOKEN"
```

## 4. Rate Limiting

El sistema limita automáticamente ejecuciones por tenant:

```bash
# Ejecución 1: OK
curl -X POST "http://localhost:8000/api/agents/agent-789/execute" ... (202)

# Ejecución 10: OK
curl -X POST "http://localhost:8000/api/agents/agent-789/execute" ... (202)

# Ejecución 11: BLOQUEADA (si límite es 10/minuto)
curl -X POST "http://localhost:8000/api/agents/agent-789/execute" ...
```

**Respuesta (429):**

```json
{
  "detail": "Rate limit exceeded. Please try again later."
}
```

Headers:

```
HTTP/1.1 429 Too Many Requests
Retry-After: 60
X-RateLimit-Remaining: 0
```

## 5. Observabilidad - Logs Estructurados

Los logs se escriben en JSON:

```json
{
  "event": "request_received",
  "request_id": "req-abc-123",
  "method": "POST",
  "path": "/api/agents/execute",
  "user_id": "user-123",
  "timestamp": "2024-01-15T10:32:00.123"
}
```

```json
{
  "event": "agent_execution",
  "execution_id": "exec-001",
  "agent_id": "agent-789",
  "tenant_id": "tenant-456",
  "status": "completed",
  "details": {
    "tokens_used": 245,
    "execution_time_ms": 2340
  },
  "timestamp": "2024-01-15T10:32:02.340"
}
```

```json
{
  "event": "error",
  "request_id": "req-xyz-789",
  "error_type": "AgentExecutionError",
  "error_message": "Failed to call LLM API",
  "stack_trace": "...",
  "timestamp": "2024-01-15T10:33:00"
}
```

## 6. Python Client Example

```python
from datetime import datetime
import time

class AIAgentClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.token = None

    def execute_agent_async(self, agent_id: str, message: str) -> str:
        """
        Execute agent and return execution_id.
        Use get_execution status to poll for results.
        """
        response = requests.post(
            f"{self.base_url}/api/agents/{agent_id}/execute",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"input_data": {"message": message}},
        )
        response.raise_for_status()
        return response.json()["id"]

    def get_execution_status(self, agent_id: str, execution_id: str) -> dict:
        """Get execution status and logs."""
        response = requests.get(
            f"{self.base_url}/api/agents/{agent_id}/executions/{execution_id}",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        response.raise_for_status()
        return response.json()

    def wait_for_execution(
        self,
        agent_id: str,
        execution_id: str,
        timeout_seconds: int = 60,
        poll_interval: float = 1.0,
    ) -> dict:
        """
        Wait for execution to complete.
        Polls status every poll_interval seconds.
        """
        start_time = time.time()

        while (time.time() - start_time) < timeout_seconds:
            status = self.get_execution_status(agent_id, execution_id)

            if status["status"] in ("completed", "failed", "cancelled"):
                return status

            print(f"⏳ Status: {status['status']}... ({len(status['logs'])} logs)")
            time.sleep(poll_interval)

        raise TimeoutError(f"Execution {execution_id} did not complete in {timeout_seconds}s")


# Uso
client = AIAgentClient()
client.token = "eyJhbGciOiJIUzI1N..."

# Ejecutar agente (retorna inmediatamente)
exec_id = client.execute_agent_async("agent-789", "Help me reset my password")
print(f"✓ Execution queued: {exec_id}")

# Esperar a que se complete
result = client.wait_for_execution("agent-789", exec_id, timeout_seconds=30)
print(f"✓ Completed in {result['execution_time_ms']}ms")
print(f"Response: {result['output_data']['response']}")

# Ver logs detallados
for log in result['logs']:
    print(f"  [{log['step']}] {log['action']}: {log['details']}")
```

## 7. Diferencias Principales vs Arquitectura Anterior

| Aspecto        | Anterior                | Nueva                         |
| -------------- | ----------------------- | ----------------------------- |
| Ejecución      | Sincrónica (bloqueante) | Asincrónica (202 Accepted)    |
| Respuesta API  | 2-30 segundos           | < 100ms                       |
| Escalabilidad  | Limitada por workers    | Ilimitada (múltiples workers) |
| Logs           | Básicos                 | Estructurados (JSON)          |
| RBAC           | is_admin binario        | owner/admin/member            |
| Rate Limiting  | No existe               | Por tenant                    |
| Tracking       | No existe               | Tokens, tiempo, costo         |
| Observabilidad | Logging simple          | Logging + Tracing             |

## 8. Troubleshooting

### Worker no procesa tareas

```bash
# Verificar que Redis está corriendo
redis-cli ping
# Debería responder: PONG

# Verificar workers activos
celery -A app.workers.celery_worker inspect active

# Ver tareas pendientes
celery -A app.workers.celery_worker inspect reserved
```

### Ejecución se queda en "pending"

```bash
# Verificar logs del worker
celery -A app.workers.celery_worker worker --loglevel=debug

# Verificar tarea en Redis
redis-cli
> KEYS celery*
> LLEN celery
```

### Rate limiting bloqueando todo

```bash
# Verificar límites del plan
curl -X GET http://localhost:8000/api/users/plan \
  -H "Authorization: Bearer $TOKEN"

# Aumentar límite (admin)
curl -X PATCH http://localhost:8000/api/subscriptions \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"executions_per_minute": 100}'
```
