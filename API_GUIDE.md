# API Quick Start Guide

This guide shows how to interact with the AI Agents SaaS API.

## Prerequisites

1. Start the API server:

```bash
uvicorn app.main:app --reload
```

2. Database should be running (use docker-compose or local PostgreSQL)

## Health Check

```bash
curl -X GET "http://localhost:8000/health"
```

Response:

```json
{
  "status": "healthy",
  "service": "ai-agents-api",
  "version": "1.0.0"
}
```

## Authentication Flow

### 1. Register a New User

```bash
curl -X POST "http://localhost:8000/api/auth/register?tenant_slug=mycompany" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@mycompany.com",
    "username": "newuser",
    "password": "securepassword123"
  }'
```

Response:

```json
{
  "user": {
    "id": "uuid-here",
    "email": "user@mycompany.com",
    "username": "newuser",
    "tenant_id": "tenant-uuid",
    "is_active": true,
    "is_admin": false,
    "created_at": "2024-01-15T10:30:00",
    "updated_at": "2024-01-15T10:30:00"
  },
  "access_token": "eyJhbGciOiJIUzI1N...",
  "refresh_token": "eyJhbGciOiJIUzI1N...",
  "token_type": "bearer"
}
```

### 2. Login

```bash
curl -X POST "http://localhost:8000/api/auth/login?tenant_slug=mycompany" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@mycompany.com",
    "password": "securepassword123"
  }'
```

### 3. Refresh Access Token

```bash
curl -X POST "http://localhost:8000/api/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "eyJhbGciOiJIUzI1N..."
  }'
```

## Agent Management

All agent endpoints require authentication. Use the access token from login:

```bash
TOKEN="your-access-token-here"
```

### Create an Agent

```bash
curl -X POST "http://localhost:8000/api/agents" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Customer Support Bot",
    "description": "AI agent for customer support",
    "agent_type": "chat",
    "system_prompt": "You are a helpful customer support agent.",
    "model": "gpt-4",
    "config": {
      "temperature": 0.7,
      "max_tokens": 2000
    }
  }'
```

Response:

```json
{
  "id": "agent-uuid",
  "name": "Customer Support Bot",
  "description": "AI agent for customer support",
  "agent_type": "chat",
  "tenant_id": "tenant-uuid",
  "created_by": "user-uuid",
  "system_prompt": "You are a helpful customer support agent.",
  "model": "gpt-4",
  "config": {
    "temperature": 0.7,
    "max_tokens": 2000
  },
  "version": 1,
  "is_active": true,
  "created_at": "2024-01-15T10:30:00",
  "updated_at": "2024-01-15T10:30:00"
}
```

### List All Agents

```bash
curl -X GET "http://localhost:8000/api/agents" \
  -H "Authorization: Bearer $TOKEN"
```

Query parameters:

- `skip`: Number of agents to skip (default: 0)
- `limit`: Number of agents to return (default: 100, max: 1000)

```bash
curl -X GET "http://localhost:8000/api/agents?skip=0&limit=10" \
  -H "Authorization: Bearer $TOKEN"
```

### Get Agent Details

```bash
curl -X GET "http://localhost:8000/api/agents/agent-uuid" \
  -H "Authorization: Bearer $TOKEN"
```

### Update an Agent

```bash
curl -X PATCH "http://localhost:8000/api/agents/agent-uuid" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Agent Name",
    "system_prompt": "Updated system prompt",
    "is_active": true
  }'
```

Note: Only the fields you want to update are required.

### Delete an Agent

```bash
curl -X DELETE "http://localhost:8000/api/agents/agent-uuid" \
  -H "Authorization: Bearer $TOKEN"
```

## Agent Execution

### Execute an Agent (Direct Response)

```bash
curl -X POST "http://localhost:8000/api/agents/agent-uuid/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello agent"
  }'
```

Response:

```json
{
  "execution_id": "execution-uuid",
  "response": "Hello. How can I help you today?",
  "tokens_used": 42,
  "execution_time_ms": 1180,
  "tools_executed": [
    "echo_tool"
  ],
  "status": "completed"
}
```

### Get Execution Status

```bash
curl -X GET "http://localhost:8000/api/agents/agent-uuid/executions/execution-uuid" \
  -H "Authorization: Bearer $TOKEN"
```

Response (completed execution):

```json
{
  "id": "execution-uuid",
  "agent_id": "agent-uuid",
  "status": "completed",
  "input_data": {...},
  "output_data": {
    "response": "I'd be happy to help with your order ORD-12345...",
    "confidence": 0.95
  },
  "error_message": null,
  "execution_time_ms": 2340,
  "created_at": "2024-01-15T10:30:00",
  "completed_at": "2024-01-15T10:30:02"
}
```

## Status Codes

| Code | Meaning                              |
| ---- | ------------------------------------ |
| 200  | Success - GET, PATCH                 |
| 201  | Created - POST                       |
| 204  | No Content - DELETE                  |
| 400  | Bad Request - Invalid input          |
| 401  | Unauthorized - Missing/invalid token |
| 403  | Forbidden - Permission denied        |
| 404  | Not Found - Resource doesn't exist   |
| 500  | Server Error                         |

## Python Client Example

```python
import requests
from typing import Optional

class AIAgentClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.token = None
        self.tenant_slug = None

    def register(self, tenant_slug: str, email: str, username: str, password: str) -> dict:
        """Register a new user."""
        response = requests.post(
            f"{self.base_url}/api/auth/register",
            params={"tenant_slug": tenant_slug},
            json={
                "email": email,
                "username": username,
                "password": password,
            }
        )
        response.raise_for_status()
        data = response.json()
        self.token = data["access_token"]
        self.tenant_slug = tenant_slug
        return data

    def login(self, tenant_slug: str, email: str, password: str) -> dict:
        """Login user."""
        response = requests.post(
            f"{self.base_url}/api/auth/login",
            params={"tenant_slug": tenant_slug},
            json={
                "email": email,
                "password": password,
            }
        )
        response.raise_for_status()
        data = response.json()
        self.token = data["access_token"]
        self.tenant_slug = tenant_slug
        return data

    def _headers(self) -> dict:
        """Get request headers with authorization."""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def create_agent(self, name: str, agent_type: str, **kwargs) -> dict:
        """Create an agent."""
        response = requests.post(
            f"{self.base_url}/api/agents",
            headers=self._headers(),
            json={
                "name": name,
                "agent_type": agent_type,
                **kwargs,
            }
        )
        response.raise_for_status()
        return response.json()

    def list_agents(self, skip: int = 0, limit: int = 100) -> list:
        """List agents."""
        response = requests.get(
            f"{self.base_url}/api/agents",
            headers=self._headers(),
            params={"skip": skip, "limit": limit},
        )
        response.raise_for_status()
        return response.json()

    def execute_agent(self, agent_id: str, message: str) -> dict:
        """Execute an agent."""
        response = requests.post(
            f"{self.base_url}/api/agents/{agent_id}/execute",
            headers=self._headers(),
            json={"message": message},
        )
        response.raise_for_status()
        return response.json()

    def get_execution(self, agent_id: str, execution_id: str) -> dict:
        """Get execution status."""
        response = requests.get(
            f"{self.base_url}/api/agents/{agent_id}/executions/{execution_id}",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()


# Usage example
if __name__ == "__main__":
    client = AIAgentClient()

    # Register
    client.register(
        tenant_slug="mycompany",
        email="user@mycompany.com",
        username="newuser",
        password="securepassword123",
    )
    print("✓ User registered")

    # Create agent
    agent = client.create_agent(
        name="Support Bot",
        agent_type="chat",
        system_prompt="You are a helpful assistant.",
    )
    print(f"✓ Agent created: {agent['id']}")

    # Execute agent
    execution = client.execute_agent(agent_id=agent["id"], message="Hello!")
    print(f"✓ Execution completed: {execution['execution_id']}")

    # Check status
    status = client.get_execution(agent["id"], execution["id"])
    print(f"Status: {status['status']}")
```

## Using with Postman

1. Import the OpenAPI schema:
   - GET: `http://localhost:8000/openapi.json`
   - Use Postman's "Import" → "Link"

2. Create environment variables:

   ```
   base_url: http://localhost:8000
   token: (will be set after login)
   tenant_slug: mycompany
   ```

3. Use `{{token}}` in Authorization headers
4. Use `{{base_url}}` in request URLs

## Demo Data

The initialization script creates:

- Tenant: `demo` with slug `demo`
- User: `demo@example.com` with password `demo123`
- Agent: Sample chat agent

Login with: `tenant_slug=demo`, `email=demo@example.com`, `password=demo123`
