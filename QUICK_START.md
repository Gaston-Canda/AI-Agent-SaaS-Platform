# 🚀 Quick Start Guide

## 5 Minutos para ejecutar todo

### Prerrequisitos

- Python 3.11+
- PostgreSQL 13+
- Redis 6+
- Docker & Docker Compose (Opcional)

---

## Opción 1: Docker (Más fácil)

### 1. Clonar y Configurar

```bash
# Copiar variables
cp .env.example .env
```

### 2. Ejecutar Stack Completo

```bash
docker-compose up -d
```

### 3. Ejecutar Agente (Respuesta Directa)

```bash
curl -X POST "http://localhost:8000/api/agents/$AGENT_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello agent"}'
```

La respuesta ya incluye resultado final y métricas:

```json
{
  "execution_id": "exec-uuid-here",
  "response": "Hello! How can I help you?",
  "tokens_used": 42,
  "execution_time_ms": 980,
  "tools_executed": [],
  "status": "completed"
}
```

### 4. Verificar Estado

```bash
EXEC_ID="exec-uuid-here"
curl -X GET "http://localhost:8000/api/agents/$AGENT_ID/executions/$EXEC_ID" \
  -H "Authorization: Bearer $TOKEN"
```

Estado posible: `running` o `completed`

### 5. Ver Resultado

Si el endpoint de ejecución respondió `completed`, ya tienes la respuesta final.
También puedes consultar el detalle histórico con:

```bash
curl -X GET "http://localhost:8000/api/agents/$AGENT_ID/executions/$EXEC_ID" \
  -H "Authorization: Bearer $TOKEN"
```
**Terminal 2 - Celery Worker:**

```bash
celery -A app.workers.celery_worker worker --loglevel=info
```

**Terminal 3 (Opcional) - Flower (Monitor):**

```bash
celery -A app.workers.celery_worker flower
```

### 6. Verificar

```bash
curl http://localhost:8000/health
```

---

## 🧪 Test Rápido

### 1. Registrarse

```bash
curl -X POST "http://localhost:8000/api/auth/register?tenant_slug=demo-test" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "username": "testuser",
    "password": "testpass123"
  }'
```

Guardar `access_token` de la respuesta:

```bash
TOKEN="eyJhbGciOiJIUzI1N..."
```

### 2. Crear Agente

```bash
curl -X POST "http://localhost:8000/api/agents" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Agent",
    "agent_type": "chat",
    "system_prompt": "You are helpful."
  }'
```

Guardar `id` del agente:

```bash
AGENT_ID="agent-uuid-here"
```

### 3. Ejecutar Agente (Respuesta Directa)

```bash
curl -X POST "http://localhost:8000/api/agents/$AGENT_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello agent"}'
```

La respuesta ya incluye resultado final y m�tricas:

```json
{
  "execution_id": "exec-uuid-here",
  "response": "Hello! How can I help you?",
  "tokens_used": 42,
  "execution_time_ms": 980,
  "tools_executed": [],
  "status": "completed"
}
```

### 4. Verificar Estado

```bash
EXEC_ID="exec-uuid-here"
curl -X GET "http://localhost:8000/api/agents/$AGENT_ID/executions/$EXEC_ID" \
  -H "Authorization: Bearer $TOKEN"
```

Estado posible: `running` o `completed`

### 5. Ver Resultado

Si el endpoint de ejecución respondió `completed`, ya tienes la respuesta final.
También puedes consultar el detalle histórico con:

```bash
curl -X GET "http://localhost:8000/api/agents/$AGENT_ID/executions/$EXEC_ID" \
  -H "Authorization: Bearer $TOKEN"
```


---

## 📊 Monitoreo

### Ver Workers Activos

```bash
celery -A app.workers.celery_worker inspect active
```

### Ver Tareas Pendientes

```bash
celery -A app.workers.celery_worker inspect reserved
```

### Dashboard Flower

```
http://localhost:5555
```

Visualiza:

- Workers disponibles
- Tasks en progreso
- Task history
- Success/failure rates

---

## 🛠️ Troubleshooting

### Los workers no procesan tareas

**Verificar Redis:**

```bash
redis-cli ping
# Debería responder: PONG
```

**Verificar worker ejecutándose:**

```bash
ps aux | grep celery  # Linux/Mac
tasklist | findstr celery  # Windows
```

**Ver logs del worker:**

```bash
celery -A app.workers.celery_worker worker --loglevel=debug
```

### API retorna 404 en todos lados

Verificar que las tables fueron creadas:

```bash
# Terminal Python
python
>>> from app.db.database import SessionLocal
>>> db = SessionLocal()
>>> db.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES")
```

### Rate limiting bloqueando todo

```bash
# Aumentar límites en .env o en base de datos
# Reiniciar API
```

### Token inválido

```bash
# El token está expirado. Hacer login nuevamente
curl -X POST "http://localhost:8000/api/auth/login?tenant_slug=demo-test" ...
```

---

## ✅ Deployment Checklist

### Antes de Producción

- [ ] Variables de entorno configuradas (SECRET_KEY, etc)
- [ ] DEBUG=False en .env
- [ ] PostgreSQL con backups configurados
- [ ] Redis con persistencia (RDB o AOF)
- [ ] HTTPS/TLS configurado
- [ ] CORS origins actualizado
- [ ] Múltiples workers Celery (al menos 2)
- [ ] Logging centralizado (ELK, Datadog, etc)
- [ ] Monitoring (Prometheus + Grafana)
- [ ] Load balancer (nginx, HAProxy)
- [ ] Database migrations (Alembic)
- [ ] Tests pasando (pytest)

### Escalabilidad

Para aumentar throughput:

**Agregar más Workers:**

```bash
# Ejecutar múltiples workers en máquinas diferentes
celery -A app.workers.celery_worker worker -n worker1@prod1 --loglevel=info
celery -A app.workers.celery_worker worker -n worker2@prod2 --loglevel=info
```

**Aumentar Concurrency:**

```bash
celery -A app.workers.celery_worker worker --concurrency=8 --loglevel=info
```

**Agregar Instancias API:**

```bash
# Con load balancer (nginx)
uvicorn app.main:app --port 8001 --workers 4
uvicorn app.main:app --port 8002 --workers 4
```

**Escalar con Kubernetes:**

```bash
# Usar helm charts o manifests
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/worker-deployment.yaml
kubectl scale deployment api-deployment --replicas=3
```

---

## 🎓 Próximos Aprendizajes

### En Corto Plazo

1. Leer `IMPLEMENTATION_GUIDE.md` para entender arquitectura
2. Ver `USAGE_EXAMPLES.md` para casos de uso
3. Explorar endpoints en `/api/docs`

### En Mediano Plazo

1. Integrar LLM real (OpenAI/Anthropic)
2. Implementar más tools para los agentes
3. Agregar testing (pytest)

### En Largo Plazo

1. Integrar Stripe para billing
2. Crear dashboard de admin
3. Implementar vector store (RAG)
4. Kubernetes deployment

---

## 📚 Documentación

1. **README.md** - Visión general
2. **PROJECT_STRUCTURE.md** - Mapeo de archivos
3. **ARCHITECTURE.md** - Diseño y patrones
4. **IMPLEMENTATION_GUIDE.md** - Guía técnica
5. **USAGE_EXAMPLES.md** - Casos de uso
6. **IMPROVEMENTS_SUMMARY.md** - Qué fue mejorado
7. **API_GUIDE.md** - Referencia de API

---

## 🎉 ¡Listo!

Tu plataforma SaaS de AI Agents está corriendo.

**Endpoints principales:**

- API: http://localhost:8000
- Docs: http://localhost:8000/api/docs
- Health: http://localhost:8000/health

**Comenzar con API:**

```bash
# 1. Registrarse
curl -X POST http://localhost:8000/api/auth/register?tenant_slug=mycompany ...

# 2. Ver agentes
curl -X GET http://localhost:8000/api/agents -H "Authorization: Bearer $TOKEN"

# 3. Crear y ejecutar agente
# ... (ver sección Test Rápido arriba)
```

**Monitorear workers:**

```bash
# Dashboard
open http://localhost:5555

# O CLI
celery -A app.workers.celery_worker inspect active
```

¡Diviértete construyendo! 🚀
