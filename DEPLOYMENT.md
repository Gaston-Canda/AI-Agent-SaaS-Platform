# Deployment Guide

This platform can be deployed on Railway, Fly.io, and AWS without changing application code.

## 1. Railway

### Recommended service layout
- `api` service from repository root (`Dockerfile`)
- `worker` service from repository root (`Dockerfile`) with custom start command
- `frontend` service from `frontend/Dockerfile`
- PostgreSQL plugin/service
- Redis plugin/service

### Root config
- `railway.json` defines build/deploy defaults for API.

### API service settings
- Start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

- Health check path: `/api/health`

### Worker service settings
- Use same source image and set start command:

```bash
celery -A app.workers.celery_worker worker --loglevel=info --concurrency=4
```

### Frontend service settings
- Dockerfile path: `frontend/Dockerfile`
- Exposed port: `80`

### Required environment variables
- `APP_ENV=production`
- `DATABASE_URL`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `SECRET_KEY`
- `OPENAI_API_KEY` (if OpenAI enabled)

---

## 2. Fly.io

### Files
- `fly.toml`
- `Procfile` (optional process reference)

### Deploy API

```bash
fly launch --no-deploy
fly deploy
```

### Run worker process
Worker is defined in `fly.toml` under `[processes]`.
Scale process groups as needed:

```bash
fly scale count 2 --group api
fly scale count 2 --group worker
```

### Health check
- Path: `/api/health`

### Required secrets

```bash
fly secrets set \
  APP_ENV=production \
  DATABASE_URL=... \
  REDIS_URL=... \
  CELERY_BROKER_URL=... \
  CELERY_RESULT_BACKEND=... \
  SECRET_KEY=... \
  OPENAI_API_KEY=...
```

---

## 3. AWS

### Available templates
- `deploy/aws/ec2-docker-compose.yml`
- `deploy/aws/ecs-task-definition-api.json`
- `deploy/aws/ecs-task-definition-worker.json`
- `deploy/aws/README.md`

### Single-node option (EC2)
- Use `ec2-docker-compose.yml`
- Suitable for small teams and internal deployments.

### Multi-node option (ECS)
- API on ECS Fargate
- Worker on ECS Fargate
- PostgreSQL on RDS
- Redis on ElastiCache
- ALB health check on `/api/health`

---

## 4. Environment strategy

The app now supports layered environment loading:
- `.env.<APP_ENV>` (if present)
- `.env`
- cloud runtime environment variables always take precedence

Supported modes:
- `development`
- `staging`
- `production`

Reference files:
- `.env.development.example`
- `.env.staging.example`
- `.env.production.example`

---

## 5. Logging and cloud collectors

Logging is structured and stdout-friendly:
- JSON output by default (`LOG_JSON=True`)
- configurable level (`LOG_LEVEL`)
- compatible with CloudWatch, Datadog, Loki, ELK, Railway/Fly log collectors

---

## 6. Scaling readiness

- API is stateless and can scale horizontally.
- Workers are horizontally scalable by increasing replicas.
- Redis coordinates Celery queue and result backend.
- PostgreSQL remains the system of record.

---

## 7. Quick smoke checks after deploy

- API health: `GET /api/health`
- Auth login: `POST /api/auth/login`
- Sync execution: `POST /api/agents/{agent_id}/execute`
- Async execution: `POST /api/agents/{agent_id}/execute-async`
