# AI Agents SaaS Platform

A scalable, production-ready FastAPI backend for managing AI agents in a multi-tenant SaaS environment.

## Features

- **Multi-tenant Architecture**: Isolated tenant data with secure tenant scoping
- **JWT Authentication**: Secure token-based authentication with refresh tokens
- **Agent Management**: Create, update, delete, and execute AI agents
- **PostgreSQL Database**: Robust relational database with proper indexing
- **Redis Support**: Caching and task queue support
- **Docker Support**: Complete Docker setup with docker-compose
- **Type Hints**: Full type annotations for better IDE support and code quality
- **Clean Architecture**: Separated routers, services, models, and schemas

## Project Structure

```
app/
├── core/              # Configuration, security, dependencies
├── db/                # Database setup and session management
├── models/            # SQLAlchemy ORM models
├── routers/           # FastAPI route handlers
├── schemas/           # Pydantic request/response models
├── services/          # Business logic
└── main.py            # FastAPI app initialization

tests/                 # Unit and integration tests
docker-compose.yml     # Docker services configuration
requirements.txt       # Python dependencies
```

## Prerequisites

- Python 3.11+
- PostgreSQL 13+
- Redis 6+
- Docker & Docker Compose (optional)

## Setup

### 1. Clone and Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/ai_agents
SECRET_KEY=your-super-secret-key-here
REDIS_URL=redis://localhost:6379/0
```

### 3. Database Setup

```bash
# Create database
createdb ai_agents

# Run migrations (once Alembic is set up)
alembic upgrade head
```

## Running the Application

### Development (Local)

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

### Using Docker Compose

```bash
docker-compose up -d
```

Check logs with:

```bash
docker-compose logs -f api
```

## API Endpoints

### Authentication

- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login user
- `POST /api/auth/refresh` - Refresh access token

### Agents

- `POST /api/agents` - Create agent
- `GET /api/agents` - List agents
- `GET /api/agents/{agent_id}` - Get agent details
- `PATCH /api/agents/{agent_id}` - Update agent
- `DELETE /api/agents/{agent_id}` - Delete agent
- `POST /api/agents/{agent_id}/execute` - Execute agent
- `GET /api/agents/{agent_id}/executions/{execution_id}` - Get execution status

## Authentication Flow

1. User registers with tenant slug, email, and password
2. System creates tenant if needed, then creates user
3. User receives access and refresh tokens
4. Access token used in `Authorization: Bearer <token>` header
5. Refresh token used to get new access token when expired

## Database Schema

### Tenants

- Multi-tenant isolation
- Tenant-scoped operations

### Users

- Email-based authentication
- Tenant association
- Admin flag for permissions

### Agents

- Agent metadata and configuration
- System prompts and model selection
- Version tracking

### AgentExecutions

- Execution history and logs
- Input/output data
- Error tracking and execution time

## Security Considerations

1. **JWT Tokens**: Signed with HS256, short expiration times
2. **Password Hashing**: bcrypt with salt
3. **Tenant Isolation**: All queries filtered by tenant_id
4. **CORS**: Configured for allowed origins
5. **Database**: PostgreSQL with parameterized queries (SQLAlchemy ORM)

## Production Checklist

- [ ] Change SECRET_KEY in production
- [ ] Set DEBUG=False
- [ ] Configure proper ALLOWED_ORIGINS
- [ ] Use environment variables for all secrets
- [ ] Set up proper logging
- [ ] Configure database backups
- [ ] Set up Redis persistence
- [ ] Enable HTTPS/TLS
- [ ] Implement rate limiting
- [ ] Add request monitoring
- [ ] Configure horizontal scaling

## Extending the Platform

### Adding New Agent Types

1. Create service in `app/services/`
2. Add routes in `app/routers/`
3. Create schemas in `app/schemas/`
4. Update models if needed in `app/models/`

### Integrating External AI Services

1. Create service wrapper (e.g., `app/services/llm_service.py`)
2. Implement agent execution logic
3. Queue tasks with Celery or similar
4. Store results in database

## License

MIT
