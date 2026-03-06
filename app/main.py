"""
Main FastAPI application for SaaS AI Agents platform.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text
import redis as redis_client_lib

from app.core.config import settings
from app.db.database import engine, Base
from app.routers import auth, agents, users
from app.routers import agent_platform
from app.routers import billing
from app.core.middleware import LoggingMiddleware, RateLimitMiddleware
from app.core.request_limits import RequestSizeLimitMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.initialization import initialize_application
from app.queue.queue import celery_app

# Create tables
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""

    print("🚀 Starting AI Agents SaaS Platform...")
    print(f"📊 Environment: Debug={settings.DEBUG}")
    print(f"🔌 Database: {settings.DATABASE_URL.split('//')[-1].split('@')[-1]}")
    print(f"🔄 Redis: {settings.REDIS_URL}")

    initialize_application()

    print("✅ Application initialized successfully")
    print("📚 API Docs: http://127.0.0.1:8000/api/docs")

    yield

    print("🛑 Shutting down application...")


# Create FastAPI app
app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

# -----------------------------------------------------
# Middleware
# -----------------------------------------------------

# 1 Logging
app.add_middleware(LoggingMiddleware)

# 2 Rate limit
app.add_middleware(RateLimitMiddleware)

# 3 Request size limit
app.add_middleware(RequestSizeLimitMiddleware)

# 4 Security headers
app.add_middleware(SecurityHeadersMiddleware)

# -----------------------------------------------------
# CORS FIX
# -----------------------------------------------------

# fallback origins for development
default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

allowed_origins = settings.ALLOWED_ORIGINS or default_origins

print("🌐 Allowed CORS origins:", allowed_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------
# Routers
# -----------------------------------------------------

app.include_router(auth.router)
app.include_router(agents.router)
app.include_router(users.router)
app.include_router(agent_platform.router)
app.include_router(billing.router)


# -----------------------------------------------------
# Health endpoints
# -----------------------------------------------------

@app.get("/api/health")
async def api_health_check() -> dict:

    database_status = "down"
    redis_status = "down"
    worker_status = "down"

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        database_status = "up"
    except Exception:
        pass

    try:
        redis_client = redis_client_lib.from_url(settings.REDIS_URL)
        redis_status = "up" if redis_client.ping() else "down"
    except Exception:
        pass

    try:
        replies = celery_app.control.ping(timeout=1.5)
        worker_status = "up" if replies else "down"
    except Exception:
        pass

    overall = "healthy" if database_status == "up" and redis_status == "up" else "degraded"

    return {
        "status": overall,
        "service": "ai-agents-api",
        "version": settings.API_VERSION,
        "database": database_status,
        "redis": redis_status,
        "worker": worker_status,
    }


@app.get("/health")
async def health_check() -> dict:
    return {
        "status": "healthy",
        "service": "ai-agents-api",
        "version": settings.API_VERSION,
    }


@app.get("/")
async def root() -> dict:
    return {
        "name": settings.API_TITLE,
        "version": settings.API_VERSION,
        "description": settings.API_DESCRIPTION,
        "docs": "/api/docs",
        "openapi": "/api/openapi.json",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)