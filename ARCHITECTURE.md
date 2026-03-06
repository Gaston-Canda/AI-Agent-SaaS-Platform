# AI Agents SaaS Backend Developer Guide

## Architecture Overview

The platform follows a **layered architecture** with clear separation of concerns:

```
HTTP Request
    ↓
Routers (API endpoints)
    ↓
Services (Business logic)
    ↓
Database (Models & ORM)
    ↓
PostgreSQL
```

## Layer Breakdown

### 1. **Routers** (`app/routers/`)

Handle HTTP requests and responses. They:

- Define API endpoints
- Validate request data using Pydantic schemas
- Handle authentication via dependencies
- Delegate business logic to services

Example:

```python
@router.post("/agents")
async def create_agent(
    agent_data: AgentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgentResponse:
    agent = AgentService.create_agent(db, agent_data, current_user.tenant_id, current_user.id)
    return AgentResponse.model_validate(agent)
```

### 2. **Services** (`app/services/`)

Contain business logic. They:

- Perform CRUD operations via the ORM
- Implement business rules
- Interact with other services
- Don't depend on HTTP (testable)

Example:

```python
class AgentService:
    @staticmethod
    def create_agent(db: Session, agent_data: AgentCreate, tenant_id: str, created_by: str) -> Agent:
        agent = Agent(
            tenant_id=tenant_id,
            created_by=created_by,
            name=agent_data.name,
            # ...
        )
        db.add(agent)
        db.commit()
        return agent
```

### 3. **Models** (`app/models/`)

SQLAlchemy ORM models representing database tables:

- Define table schema
- Handle relationships between entities
- Include proper indexes for performance

### 4. **Schemas** (`app/schemas/`)

Pydantic models for request/response validation:

- Define API contracts
- Enable automatic OpenAPI documentation
- Validate input data

### 5. **Core** (`app/core/`)

- **config.py**: Environment configuration
- **security.py**: JWT tokens, password hashing
- **dependencies.py**: Dependency injection (current_user, etc.)
- **database.py**: Database connection and session management

## Multi-Tenancy

All data is tenant-scoped:

1. **User Creation**: Associate user with tenant
2. **Query Filtering**: ALL queries include `tenant_id` filter
3. **Permissions**: Users can only see their tenant's data

Example:

```python
# Always filter by tenant_id
agent = db.query(Agent).filter(
    Agent.id == agent_id,
    Agent.tenant_id == current_user.tenant_id,  # ← Tenant isolation
).first()
```

## Authentication Flow

```
1. User registers/logs in
2. System validates credentials
3. Returns JWT access token + refresh token
4. Client sends access token in Authorization header
5. get_current_user dependency validates token
6. Route handler receives authenticated User object
```

## Adding a New Feature

### 1. Define the Model

```python
# app/models/feature.py
class Feature(Base):
    __tablename__ = "features"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    # ... other fields
```

### 2. Create Schemas

```python
# app/schemas/feature.py
class FeatureCreate(BaseModel):
    name: str
    description: Optional[str] = None

class FeatureResponse(FeatureCreate):
    id: str
    tenant_id: str
    class Config:
        from_attributes = True
```

### 3. Create Service

```python
# app/services/feature_service.py
class FeatureService:
    @staticmethod
    def create_feature(db: Session, feature_data: FeatureCreate, tenant_id: str) -> Feature:
        feature = Feature(
            tenant_id=tenant_id,
            name=feature_data.name,
            description=feature_data.description,
        )
        db.add(feature)
        db.commit()
        db.refresh(feature)
        return feature
```

### 4. Create Routes

```python
# app/routers/features.py
@router.post("", response_model=FeatureResponse)
async def create_feature(
    feature_data: FeatureCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeatureResponse:
    feature = FeatureService.create_feature(db, feature_data, current_user.tenant_id)
    return FeatureResponse.model_validate(feature)
```

### 5. Register Router

```python
# app/main.py
from app.routers import features
app.include_router(features.router)
```

## Common Patterns

### Tenant-Scoped Queries

```python
# ✓ Good - includes tenant_id
resource = db.query(Model).filter(
    Model.id == id,
    Model.tenant_id == tenant_id,
).first()

# ✗ Bad - missing tenant_id
resource = db.query(Model).filter(Model.id == id).first()
```

### Permission Checks

```python
# Check if user owns resource
if resource.created_by != current_user.id and not current_user.is_admin:
    raise HTTPException(status_code=403, detail="Permission denied")
```

### Error Handling

```python
if not resource:
    raise HTTPException(status_code=404, detail="Resource not found")

if not resource.is_active:
    raise HTTPException(status_code=400, detail="Resource is inactive")
```

## Testing Strategy

1. **Unit Tests**: Test services in isolation
2. **Integration Tests**: Test routers with database
3. **E2E Tests**: Full API testing with Docker

```python
def test_create_agent(test_db, test_tenant, test_user):
    """Test agent creation."""
    agent_data = AgentCreate(
        name="Test Agent",
        agent_type="chat",
    )
    agent = AgentService.create_agent(
        test_db, agent_data, test_tenant.id, test_user.id
    )
    assert agent.name == "Test Agent"
    assert agent.tenant_id == test_tenant.id
```

## Performance Tips

1. **Indexing**: Add indexes on frequently queried columns

   ```python
   __table_args__ = (
       Index("idx_agent_tenant_id", "tenant_id"),
       Index("idx_agent_created_by", "created_by"),
   )
   ```

2. **Eager Loading**: Load related data when needed

   ```python
   agent = db.query(Agent).options(
       joinedload(Agent.tenant),
       joinedload(Agent.creator),
   ).first()
   ```

3. **Pagination**: Limit query results
   ```python
   agents = db.query(Agent).limit(100).offset(skip).all()
   ```

## Deployment Checklist

- [ ] Set environment variables for production
- [ ] Configure database for persistence
- [ ] Set up Redis for caching
- [ ] Enable HTTPS/TLS
- [ ] Configure rate limiting
- [ ] Set up monitoring and logging
- [ ] Create database backups
- [ ] Test with load balancing
- [ ] Configure auto-scaling

## Useful Commands

```bash
# Development
uvicorn app.main:app --reload

# Initialize database
python init_db.py

# Run tests
pytest -v

# Docker
docker-compose up -d
docker-compose logs -f api

# Generate OpenAPI schema
curl http://localhost:8000/openapi.json
```

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8949)
