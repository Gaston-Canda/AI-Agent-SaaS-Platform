# 📚 Documentation Index

Complete guide to the AI Agents SaaS Platform.

## Quick Navigation

### ⚡ Getting Started (Choose One)

- **[QUICK_START.md](./QUICK_START.md)** - 5 min setup guide
  - Best for: "I want to run this NOW"
  - Covers: Docker, environment, health check, test agent

- **[README.md](./README.md)** - Comprehensive overview
  - Best for: Understanding the platform
  - Covers: Features, architecture, endpoints, deployment

### 🤖 Agent Framework (New!)

- **[FRAMEWORK_SUMMARY.md](./FRAMEWORK_SUMMARY.md)** - High-level overview of new systems
  - Best for: Understanding what changed from v1 to v2
  - Covers: 5 new systems, before/after comparison, architecture evolution

- **[AGENT_FRAMEWORK.md](./AGENT_FRAMEWORK.md)** - Complete technical reference
  - Best for: Deep dive into each system with examples
  - Covers: LLM providers, tools, memory, orchestrator, configuration, production setup

### 📖 Implementation Guides

- **[IMPLEMENTATION_GUIDE.md](./IMPLEMENTATION_GUIDE.md)** - Step-by-step implementation
  - Language: Spanish 🇪🇸
  - Covers: Setup, architecture explanation, detailed component walkthrough

- **[PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md)** - File organization and system design
  - Covers: Directory structure, data models, endpoint matrix, execution flow

### 💻 Code Examples & Usage

- **[USAGE_EXAMPLES.md](./USAGE_EXAMPLES.md)** - Runnable API examples
  - Format: curl commands, Python client
  - Covers: Registration, agent creation, async execution, monitoring

- **[examples/complete_agent_execution.py](./examples/complete_agent_execution.py)** - Python examples
  - Format: Runnable async code
  - Covers: Simple chat, agent with tools, provider switching, memory management

### 📊 System Improvements

- **[IMPROVEMENTS_SUMMARY.md](./IMPROVEMENTS_SUMMARY.md)** - What was improved
  - Best for: PMs, stakeholders
  - Covers: 9 systems added, features, production readiness

---

## Documentation by Topic

### 🚀 Getting Started

1. [QUICK_START.md](./QUICK_START.md) - Start here
2. [README.md](./README.md) - Understand platform
3. Run locally or with Docker (see QUICK_START)

### 🤖 Building with Agents

1. [FRAMEWORK_SUMMARY.md](./FRAMEWORK_SUMMARY.md) - What's available
2. [AGENT_FRAMEWORK.md](./AGENT_FRAMEWORK.md) - How to use each system
3. [USAGE_EXAMPLES.md](./USAGE_EXAMPLES.md) - API examples
4. [examples/complete_agent_execution.py](./examples/complete_agent_execution.py) - Python code
5. [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md) - Understanding the code

### 🔧 LLM Providers

- [AGENT_FRAMEWORK.md - Section 1](./AGENT_FRAMEWORK.md#1️⃣-llm-provider-abstraction-apllm) - LLM provider details
- How to: Switch providers, add new provider, configure model

### 🛠️ Tools System

- [AGENT_FRAMEWORK.md - Section 2](./AGENT_FRAMEWORK.md#2️⃣-tool-system-apptools) - Tools reference
- How to: Create custom tool, execute tools, allowed tools per agent

### 💭 Memory System

- [AGENT_FRAMEWORK.md - Section 3](./AGENT_FRAMEWORK.md#3️⃣-agent-memory-system-appmemory) - Memory reference
- How to: Store messages, search history, prepare for RAG

### ⚙️ Agent Execution

- [AGENT_FRAMEWORK.md - Section 4](./AGENT_FRAMEWORK.md#4️⃣-agent-execution-orchestrator-appengine) - Orchestrator details
- How to: Build agent config, understanding execution flow, use MemoryManager

### 🏗️ Architecture

- [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md) - Database schema, endpoints, data flow
- [FRAMEWORK_SUMMARY.md](./FRAMEWORK_SUMMARY.md) - Before/after comparison

### 📊 Monitoring & Operations

- [QUICK_START.md - Monitoreo](./QUICK_START.md#-monitoreo) - Flower dashboard, logs
- [PROJECT_STRUCTURE.md - Data Models](./PROJECT_STRUCTURE.md#data-models) - What gets tracked
- Structured logging with JSON format

### 🔐 Security & Multi-Tenancy

- [README.md - Security](./README.md#security-considerations) - Security checks
- [IMPLEMENTATION_GUIDE.md](./IMPLEMENTATION_GUIDE.md) - Tenant isolation details
- RBAC, JWT tokens, tenant scoping

### 📈 Deployment & Scaling

- [QUICK_START.md - Deployment](./QUICK_START.md#-deployment-checklist) - Pre-production checklist
- [QUICK_START.md - Escalabilidad](./QUICK_START.md#-escalabilidad) - Horizontal scaling
- Docker, Kubernetes, multiple workers

### 💰 Billing & Usage

- [AGENT_FRAMEWORK.md - Production Setup](./AGENT_FRAMEWORK.md#-configuración-para-producción) - Token tracking
- [PROJECT_STRUCTURE.md - Usage Tracking](./PROJECT_STRUCTURE.md) - AgentUsage model
- Cost estimation, token counting

---

## Quick Reference

### Commands

```bash
# Setup
pip install -r requirements.txt
cp .env.example .env

# Docker (all-in-one)
docker-compose up -d

# Local (3 terminals)
uvicorn app.main:app --reload
celery -A app.workers.celery_worker worker
celery -A app.workers.celery_worker flower

# Health check
curl http://localhost:8000/health

# API Docs
open http://localhost:8000/api/docs

# Monitoring
open http://localhost:5555  # Flower
```

### API Quick Reference

```bash
# Register (creates tenant)
curl -X POST http://localhost:8000/api/auth/register?tenant_slug=my-org \
  -d '{"email":"user@example.com","username":"user","password":"pass"}'

# Login
curl -X POST http://localhost:8000/api/auth/login?tenant_slug=my-org \
  -d '{"email":"user@example.com","password":"pass"}'

# Create agent
curl -X POST http://localhost:8000/api/agents \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"Bot","config":{...}}'

# Execute agent (async)
curl -X POST http://localhost:8000/api/agents/:ID/execute \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message":"Your prompt"}'

# Get result
curl http://localhost:8000/api/agents/:ID/executions/:EXEC_ID \
  -H "Authorization: Bearer $TOKEN"
```

### Key Concepts

| Concept              | Definition                                | Doc                                |
| -------------------- | ----------------------------------------- | ---------------------------------- |
| **Tenant**           | Organization/workspace isolation          | README, IMPLEMENTATION_GUIDE       |
| **Agent**            | AI entity with config, tools, memory      | AGENT_FRAMEWORK, PROJECT_STRUCTURE |
| **Execution**        | Single agent run (async, queued)          | USAGE_EXAMPLES                     |
| **LLM Provider**     | OpenAI, Anthropic, etc. (pluggable)       | AGENT_FRAMEWORK Section 1          |
| **Tool**             | Action agent can execute (HTTP, calc, DB) | AGENT_FRAMEWORK Section 2          |
| **Memory**           | Conversation history + vector storage     | AGENT_FRAMEWORK Section 3          |
| **ExecutionContext** | All metadata from a single run            | FRAMEWORK_SUMMARY                  |
| **RBAC**             | Role-based access (owner/admin/member)    | README                             |

---

## Language Notes

- **English**: All code, variables, function names, comments
- **Spanish**: Some documentation files marked 🇪🇸
  - [IMPLEMENTATION_GUIDE.md](./IMPLEMENTATION_GUIDE.md) - Technical guide in Spanish
  - [QUICK_START.md](./QUICK_START.md) - Mixed Spanish/English

---

## File Origins

| File                                 | Created          | Purpose                      |
| ------------------------------------ | ---------------- | ---------------------------- |
| FRAMEWORK_SUMMARY.md                 | This Session     | v2.0 framework overview      |
| AGENT_FRAMEWORK.md                   | This Session     | Complete framework reference |
| examples/complete_agent_execution.py | This Session     | Python code examples         |
| Previous docs                        | Earlier sessions | Original architecture        |

---

## For Different Roles

### 👨‍💻 Developer

1. [QUICK_START.md](./QUICK_START.md) - Get running
2. [AGENT_FRAMEWORK.md](./AGENT_FRAMEWORK.md) - Learn systems
3. [examples/complete_agent_execution.py](./examples/complete_agent_execution.py) - See code
4. [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md) - Understand codebase
5. Build features

### 👩‍💼 Product Manager

1. [FRAMEWORK_SUMMARY.md](./FRAMEWORK_SUMMARY.md) - What changed
2. [IMPROVEMENTS_SUMMARY.md](./IMPROVEMENTS_SUMMARY.md) - Before/after
3. [README.md](./README.md) - Features and capabilities
4. Understand roadmap

### 🏗️ DevOps/Platform Engineer

1. [QUICK_START.md](./QUICK_START.md) - Deployment section
2. [docker-compose.yml](./docker-compose.yml) - Infrastructure
3. [README.md - Production Checklist](./README.md#production-checklist) - Hardening
4. Configure scaling

### 🤝 Stakeholder/Non-Technical

1. [IMPROVEMENTS_SUMMARY.md](./IMPROVEMENTS_SUMMARY.md) - Business impact
2. [README.md](./README.md) - Features overview
3. [FRAMEWORK_SUMMARY.md](./FRAMEWORK_SUMMARY.md) - What's possible

---

## Troubleshooting

**Can't find something?**

1. Check this index
2. Search in [AGENT_FRAMEWORK.md](./AGENT_FRAMEWORK.md)
3. Look in [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md)
4. Check [USAGE_EXAMPLES.md](./USAGE_EXAMPLES.md) for API examples

**Want to do X?**

- Run agents → [QUICK_START.md](./QUICK_START.md) + [USAGE_EXAMPLES.md](./USAGE_EXAMPLES.md)
- Add tools → [AGENT_FRAMEWORK.md - Section 2](./AGENT_FRAMEWORK.md#2️⃣-tool-system-apptools)
- Add LLM → [AGENT_FRAMEWORK.md - Section 1](./AGENT_FRAMEWORK.md#1️⃣-llm-provider-abstraction-apllm)
- Deploy → [QUICK_START.md - Deployment](./QUICK_START.md#-deployment-checklist)
- Monitor → [QUICK_START.md - Monitoreo](./QUICK_START.md#-monitoreo)

---

**Last Updated**: March 5, 2026  
**Version**: 2.0 (Agent Framework Complete)  
**Status**: ✅ Production Ready
