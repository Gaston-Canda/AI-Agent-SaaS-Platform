"""Compatibility database dependencies for async-style imports."""

from typing import AsyncGenerator
from sqlalchemy.orm import Session

from app.db.database import SessionLocal


async def get_async_db() -> AsyncGenerator[Session, None]:
    """
    Compatibility dependency used by routers expecting an async DB provider.

    Returns a regular SQLAlchemy session wrapped in an async generator.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

