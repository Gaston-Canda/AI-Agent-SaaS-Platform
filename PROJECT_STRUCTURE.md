# Estructura del Proyecto - Arquitectura Mejorada

```
SaaS IA Agents/
│
├── 📄 agents.md                           # Instrucciones de proyecto
├── 📄 README.md                           # Introducción
├── 📄 ARCHITECTURE.md                     # Diseño y patrones
├── 📄 API_GUIDE.md                        # Ejemplos de API
├── 📄 IMPLEMENTATION_GUIDE.md             # Guía técnica detallada
├── 📄 USAGE_EXAMPLES.md                   # Casos de uso completos
├── 📄 IMPROVEMENTS_SUMMARY.md             # Este resumen
│
├── 🔧 Configuración
├── ├── .env.example                       # Variables de entorno
├── ├── requirements.txt                   # Dependencias Python
├── ├── Dockerfile                         # Multi-stage build
├── ├── docker-compose.yml                 # Orquestación (API, Worker, Flower)
├── ├── setup.sh / setup.bat               # Setup scripts
│
├── 📁 app/                                # Aplicación Principal
│
│   ├── 📁 core/                           # Configuración y seguridad
│   │   ├── __init__.py
│   │   ├── config.py                      # Settings desde .env
│   │   ├── security.py                    # JWT, password hashing
│   │   ├── dependencies.py                # ✨ ACTUALIZADO - RBAC dependencies
│   │   └── middleware.py                  # ✨ NUEVO - Logging, rate limiting
│   │
│   ├── 📁 db/                             # Base de datos
│   │   ├── __init__.py
│   │   └── database.py                    # SQLAlchemy setup
│   │
│   ├── 📁 models/                         # ORM Models
│   │   ├── __init__.py
│   │   ├── user.py                        # User, Tenant models
│   │   ├── agent.py                       # Agent, AgentExecution models
│   │   └── extended.py                    # ✨ NUEVO - UserRole, ExecutionLog, etc
│   │
│   ├── 📁 schemas/                        # Pydantic validation
│   │   ├── __init__.py
│   │   ├── user.py                        # User, Auth schemas
│   │   ├── agent.py                       # Agent execution schemas
│   │   └── extended.py                    # ✨ NUEVO - RBAC, usage schemas
│   │
│   ├── 📁 services/                       # Business logic
│   │   ├── __init__.py
│   │   ├── user_service.py                # User authentication
│   │   ├── agent_service.py               # Agent CRUD
│   │   ├── rbac_service.py                # ✨ NUEVO - Role management
│   │   └── usage_service.py               # ✨ NUEVO - Tracking, quotas
│   │
│   ├── 📁 routers/                        # FastAPI endpoints
│   │   ├── __init__.py
│   │   ├── auth.py                        # Login, register, refresh
│   │   ├── agents.py                      # ✨ ACTUALIZADO - Async execution
│   │   └── users.py                       # ✨ NUEVO - RBAC endpoints
│   │
│   ├── 📁 workers/                        # ✨ NUEVO - Background workers
│   │   ├── __init__.py
│   │   ├── tasks.py                       # Celery tasks
│   │   └── celery_worker.py               # Worker configuration
│   │
│   ├── 📁 engine/                         # ✨ NUEVO - Agent execution engine
│   │   ├── __init__.py
│   │   └── engine.py                      # AgentEngine, AgentMemory, ToolExecutor
│   │
│   ├── 📁 queue/                          # ✨ NUEVO - Task queue interface
│   │   ├── __init__.py
│   │   └── queue.py                       # ExecutionQueue con Celery
│   │
│   ├── 📁 monitoring/                     # ✨ NUEVO - Observability
│   │   ├── __init__.py
│   │   └── logging.py                     # StructuredLogger, RequestTracer
│   │
│   ├── 📁 rate_limiting/                  # ✨ NUEVO - Rate limiting
│   │   ├── __init__.py
│   │   └── limiter.py                     # Token bucket rate limiter
│   │
│   └── main.py                            # ✨ ACTUALIZADO - FastAPI app
│
├── 📁 tests/                              # Testing
│   ├── __init__.py
│   ├── conftest.py                        # Pytest fixtures
│   └── test_auth.py                       # Sample tests
│
└── init_db.py                             # Database initialization script
```

## 📊 Modelos de Base de Datos

### Existentes (Actualizado)

```
tenants
├── id (PK)
├── name
├── slug (UNIQUE)
├── is_active
├── created_at / updated_at

users
├── id (PK)
├── tenant_id (FK)
├── email
├── username
├── hashed_password
├── is_active
├── created_at / updated_at

agents
├── id (PK)
├── tenant_id (FK)
├── created_by (FK)
├── name
├── agent_type
├── config (JSON)
├── system_prompt
├── model
├── is_active
├── version
├── created_at / updated_at

agent_executions
├── id (PK)
├── agent_id (FK)
├── input_data (JSON)
├── output_data (JSON)
├── status (pending/running/completed/failed)
├── error_message
├── execution_time_ms
├── created_at / completed_at
```

### Nuevos (Extensión)

```
tenant_users              # RBAC - Roles por usuario y tenant
├── id (PK)
├── user_id (FK)
├── tenant_id (FK)
├── role (owner/admin/member)
├── is_active
├── created_at / updated_at

execution_logs            # Tracking detallado de pasos
├── id (PK)
├── execution_id (FK)
├── step (número secuencial)
├── action (input_received/prompt_built/llm_response/...)
├── details (JSON)
├── timestamp

agent_usage               # Metrics para billing
├── id (PK)
├── tenant_id (FK)
├── agent_id (FK)
├── execution_id (FK)
├── input_tokens
├── output_tokens
├── total_tokens
├── execution_time_ms
├── cost_usd
├── model_used
├── created_at

tenant_subscriptions      # Planes y límites
├── id (PK)
├── tenant_id (FK - UNIQUE)
├── plan_name (free/starter/pro/enterprise)
├── executions_per_minute
├── executions_per_day
├── concurrent_executions
├── tokens_per_month
├── custom_models (bool)
├── advanced_tools (bool)
├── created_at / updated_at
```

## 🔀 Flujo de Datos - Ejecución Completa

```
┌─────────────────┐
│  Cliente HTTP   │
└────────┬────────┘
         │
         │ GET /api/docs
         │ POST /api/agents/{id}/execute
         │ GET /api/agents/{id}/executions/{exec_id}
         │
    ┌────▼──────────────────────────┐
    │   FastAPI App (app/main.py)   │
    │                                │
    │  ┌──────────────────────────┐  │
    │  │ Middleware:              │  │
    │  │ 1. Logging Middleware    │  │
    │  │ 2. RateLimit Middleware  │  │
    │  │ 3. CORS Middleware       │  │
    │  └──────────────────────────┘  │
    │                                │
    │  ┌──────────────────────────┐  │
    │  │ Routers:                 │  │
    │  │ - auth.py (Login)        │  │
    │  │ - agents.py (CRUD + Exec)│  │
    │  │ - users.py (RBAC)        │  │
    │  └──────────────┬───────────┘  │
    │                 │               │
    │  ┌──────────────▼───────────┐  │
    │  │ Services:                │  │
    │  │ - user_service           │  │
    │  │ - agent_service          │  │
    │  │ - rbac_service ✨        │  │
    │  │ - usage_service ✨       │  │
    │  └──────────────┬───────────┘  │
    │                 │               │
    └─────────────────┼───────────────┘
                      │
          ┌───────────┴────────────┐
          │                        │
    ┌─────▼────────┐      ┌────────▼──────────┐
    │ PostgreSQL   │      │  Redis + Celery   │
    │              │      │                   │
    │ - Tenants    │      │ Queue Task:       │
    │ - Users      │      │ execute_agent()   │
    │ - Agents     │      │                   │
    │ - Executions │      └────────┬──────────┘
    │ - Logs       │               │
    │ - Usage      │               │
    │ (Persistencia)   ┌──────────▼────────────┐
    │                  │ Celery Worker(s)     │
    │                  │                      │
    │                  │ ┌──────────────────┐ │
    │                  │ │ AgentEngine      │ │
    │                  │ ├──────────────────┤ │
    │                  │ │- Memory (history)│ │
    │                  │ │- LLM calls       │ │
    │                  │ │- Tool execution  │ │
    │                  │ │- Logging steps   │ │
    │                  │ └──────────────────┘ │
    │                  │                      │
    │                  │ Output:              │
    │                  │ - Save result        │
    │                  │ - Track usage        │
    │                  │ - Store logs         │
    │                  └──────────────────────┘
    │
    │ (Read Status)
    │ ◄─────────────────────────────────────
    │
    └──────────────────────────────────────►
       Update status in PostgreSQL
```

## 🎯 Endpoints Disponibles

### Autenticación

- `POST /api/auth/register` - Registrarse
- `POST /api/auth/login` - Login
- `POST /api/auth/refresh` - Renovar token

### Agentes (CRUD + Execution)

- `POST /api/agents` - Crear agente
- `GET /api/agents` - Listar agentes
- `GET /api/agents/{id}` - Obtener agente
- `PATCH /api/agents/{id}` - Actualizar agente
- `DELETE /api/agents/{id}` - Eliminar agente
- `POST /api/agents/{id}/execute` - Ejecutar ✨ (202 Async)
- `GET /api/agents/{id}/executions/{exec_id}` - Ver resultado con logs
- `GET /api/agents/{id}/usage` - Estadísticas del agente
- `GET /api/agents/usage/summary` - Uso total del tenant

### Usuarios y RBAC ✨

- `GET /api/users/me` - Mi perfil
- `GET /api/users/tenant/members` - Listar miembros (admin)
- `POST /api/users/tenant/members/{user_id}/role` - Asignar rol (owner)
- `GET /api/users/tenant/role` - Mi rol

### General

- `GET /health` - Health check
- `GET /api/docs` - Swagger UI
- `GET /api/openapi.json` - OpenAPI schema

## 🔐 Permisos por Rol

| Acción                  | Owner | Admin | Member |
| ----------------------- | ----- | ----- | ------ |
| Crear agente            | ✓     | ✓     | ✗      |
| Editar agente propio    | ✓     | ✓     | ✓      |
| Editar agente ajeno     | ✓     | ✓     | ✗      |
| Ejecutar agente         | ✓     | ✓     | ✓      |
| Ver estadísticas tenant | ✓     | ✓     | ✗      |
| Listar miembros         | ✓     | ✓     | ✗      |
| Asignar roles           | ✓     | ✗     | ✗      |

## 📦 Dependencias Principales

```
FastAPI              # Web framework
SQLAlchemy           # ORM
PostgreSQL (adapter) # Database
Redis                # Cache + queue broker
Celery               # Task queue
Pydantic             # Validation
JWT (python-jose)   # Authentication
bcrypt               # Password hashing
python-json-logger  # Structured logging
httpx                # Async HTTP client
```

## 🚀 Deployment Ready

✓ Multi-tenant architecture
✓ Async processing (Celery)
✓ Structured logging
✓ Rate limiting
✓ RBAC
✓ Usage tracking
✓ Error handling
✓ Database migrations ready
✓ Docker support
✓ Health checks
✓ Graceful shutdown

**La plataforma está lista para deployment en producción.**
