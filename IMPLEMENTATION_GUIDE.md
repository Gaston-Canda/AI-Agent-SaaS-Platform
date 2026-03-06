# Guía de Implementación - Arquitectura Mejorada de SaaS AI Agents

## 📐 Arquitectura General

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI API Server                     │
│  - Routers (Auth, Agents, Users)                          │
│  - Middleware (Logging, Rate Limiting)                    │
│  - RBAC Dependencies                                      │
└─────────────────────────────┬───────────────────────────┘
                              │
                ┌─────────────┴────────────────┐
                │                              │
         ┌──────v──────────┐        ┌────────v────────┐
         │   PostgreSQL    │        │     Redis       │
         │   Database      │        │   Task Queue    │
         │  - Models       │        │  - Executions   │
         │  - Audit Log    │        │  - Caching      │
         └─────────────────┘        └────────┬────────┘
                                             │
                                   ┌─────────v─────────┐
                                   │  Celery Workers   │
                                   │  - Execution      │
                                   │  - Agent Engine   │
                                   └───────────────────┘
```

## 🏗️ Nuevos Componentes

### 1. **Sistema de Ejecución Asincrónica (Queue)**

**Archivos:**

- `app/queue/queue.py` - Interface de colas con Celery

**Flujo:**

```
API Request → Create Execution → Queue Task → Return 202 → Worker Processes
```

**Ventajas:**

- API no bloquea
- Escalable: múltiples workers
- Reintentos automáticos
- Tracking de tareas

### 2. **Motor de Agentes (Engine)**

**Archivos:**

- `app/engine/engine.py` - Core logic para ejecutar agentes

**Componentes:**

- `AgentMemory` - Gestiona conversaciones
- `ToolExecutor` - Ejecuta funciones externas
- `AgentEngine` - Orquesta la ejecución

**Flujo:**

```
Input → Build Prompt → Call LLM → Process Tools → Log Steps → Return Result
```

### 3. **Workers (Procesos en Background)**

**Archivos:**

- `app/workers/tasks.py` - Tareas Celery
- `app/workers/celery_worker.py` - Configuración de worker

**Responsabilidades:**

- Consumir tareas de la cola
- Ejecutar agentes usando `AgentEngine`
- Guardar resultados y logs
- Tracked de uso

### 4. **Tracking de Uso**

**Modelo:** `AgentUsage` en `app/models/extended.py`

**Registra:**

- Tokens de entrada/salida
- Tiempo de ejecución
- Costo estimado (LLM)
- Modelo usado

**Servicio:** `UsageService` en `app/services/usage_service.py`

### 5. **Rate Limiting**

**Archivos:**

- `app/rate_limiting/limiter.py` - Token bucket algorithm

**Características:**

- Por tenant
- Configurable por plan
- Fallback en memoria si Redis no disponible

### 6. **Observabilidad**

**Archivos:**

- `app/monitoring/logging.py` - Logging estructurado

**Registra:**

- Solicitudes HTTP (método, path, usuario)
- Respuestas (código, duración)
- Errores con stack trace
- Eventos de ejecución de agentes

### 7. **RBAC (Control de Acceso)**

**Modelos:**

- `UserRole` - owner, admin, member
- `TenantUser` - Relación usuario-rol-tenant

**Servicio:** `RBACService` en `app/services/rbac_service.py`

**Validación:** En dependencias de FastAPI (`app/core/dependencies.py`)

## 🚀 Cómo Ejecutar

### 1. **Instalación**

```bash
# Instalar dependencias
pip install -r requirements.txt

# Crear archivo .env
cp .env.example .env

# Actualizar .env con credenciales reales
```

### 2. **Inicializar Base de Datos**

```bash
# Ejecutar migraciones (si se configuró Alembic)
alembic upgrade head

# O crear tablas iniciales
python init_db.py
```

### 3. **Ejecutar API Server**

```bash
# Modo desarrollo
uvicorn app.main:app --reload

# Modo producción
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 4. **Ejecutar Celery Workers**

```bash
# Terminal 2 - Worker por defecto
celery -A app.workers.celery_worker worker --loglevel=info

# Múltiples workers para escalabilidad
celery -A app.workers.celery_worker worker --loglevel=info --concurrency=4

# Worker con nombre específico
celery -A app.workers.celery_worker worker -n worker1@%h --loglevel=info
```

### 5. **Monitorear Celery (Opcional)**

```bash
# Terminal 3 - Dashboard de Celery
pip install flower
celery -A app.workers.celery_worker flower
# Visita http://localhost:5555
```

### 6. **Docker Compose**

```bash
# Ejecutar todo con Docker
docker-compose up -d

# Ver logs
docker-compose logs -f api

# Detener
docker-compose down
```

## 📊 Estructura de Datos

### Tablas Nuevas

**tenant_users**

```sql
id | user_id | tenant_id | role | is_active | created_at
```

**execution_logs**

```sql
id | execution_id | step | action | details | timestamp
```

**agent_usage**

```sql
id | tenant_id | agent_id | execution_id | input_tokens | output_tokens | cost_usd | created_at
```

**tenant_subscriptions**

```sql
id | tenant_id | plan_name | executions_per_minute | tokens_per_month | custom_models
```

## 🔄 Flujo de Ejecución Completo

### Paso a Paso

1. **Usuario solicita ejecución**

   ```
   POST /api/agents/{agent_id}/execute
   Respuesta: 202 + execution_id
   ```

2. **API crea ejecución**
   - Status: "pending"
   - Carga configuración del agente

3. **API encola tarea**
   - Envía a Redis
   - Retorna inmediatamente

4. **Cliente obtiene estado**

   ```
   GET /api/agents/{agent_id}/executions/{execution_id}
   ```

5. **Worker consume tarea**
   - Actualiza status a "running"
   - Carga `AgentEngine`

6. **AgentEngine ejecuta**
   - Prepara prompt
   - Llama LLM
   - Ejecuta tools si es necesario
   - Registra logs

7. **Worker guarda resultados**
   - Status: "completed" o "failed"
   - Output data
   - Execution time
   - Tokens usados

8. **Cliente verifica completitud**
   - Status: "completed"
   - Response: resultado + logs

## 🔐 Seguridad

### Aislamiento Multi-Tenant

- Todos los queries filtran por `tenant_id`
- Usuarios solo ven datos de su tenant
- RBAC valida permisos por rol

### Autenticación

- JWT tokens con expiración
- Refresh tokens para renovar
- Validación en cada request

### Rate Limiting

- Por tenant
- Configurable por plan
- Previene abuso

## 📈 Escalabilidad

### Horizontal

- Múltiples instancias de API
- Múltiples workers Celery
- Load balancer frente (nginx/k8s)

### Vertical

- Aumentar workers por instancia
- Aumentar concurrency de Celery
- Aumentar pool de conexiones DB

### Monitoreo

- Prometheus metrics
- Grafana dashboards
- ELK stack para logs

## 🎯 Próximos Pasos

1. **Integración LLM**
   - OpenAI API
   - Anthropic API
   - Local models (Ollama)

2. **Sistema de Tools**
   - HTTP requests
   - Búsqueda
   - Base de datos
   - APIs externas

3. **Facturación**
   - Usar `AgentUsage.cost_usd`
   - Integrar con Stripe
   - Reportes de uso

4. **Persistencia Mejorada**
   - Usuario datos en caché
   - Memory vector store
   - Conversation history

5. **Testing**
   - Unit tests para servicios
   - Integration tests para API
   - Load testing

## 📚 Referencias

- [Celery Documentation](https://docs.celeryproject.org/)
- [FastAPI Middleware](https://fastapi.tiangolo.com/tutorial/middleware/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)
- [Redis Documentation](https://redis.io/docs/)
