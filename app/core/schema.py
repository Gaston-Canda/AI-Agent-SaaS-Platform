"""Runtime-safe schema helpers for additive columns."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session


def ensure_execution_log_columns(db: Session) -> None:
    """Ensure additive execution log columns exist before ORM inserts."""
    bind = db.bind
    if bind is None:
        return

    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "execution_logs" not in tables:
        return

    existing_columns = {col["name"] for col in inspector.get_columns("execution_logs")}
    additions = {
        "tokens_used": "INTEGER NOT NULL DEFAULT 0",
        "llm_latency_ms": "INTEGER NOT NULL DEFAULT 0",
        "tool_latency_ms": "INTEGER NOT NULL DEFAULT 0",
        "total_execution_time_ms": "INTEGER NOT NULL DEFAULT 0",
    }

    missing = [(name, definition) for name, definition in additions.items() if name not in existing_columns]
    if not missing:
        return

    with bind.begin() as connection:
        for column_name, definition in missing:
            connection.execute(text(f"ALTER TABLE execution_logs ADD COLUMN {column_name} {definition}"))
