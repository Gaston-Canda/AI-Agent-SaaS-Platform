"""
Routes package - REST API endpoints.

This package contains all API route handlers organized by domain:
- agents.py: Agent management, versioning, tools, and prompts
"""

from app.routes.agents import router as agents_router

__all__ = [
    "agents_router",
]
