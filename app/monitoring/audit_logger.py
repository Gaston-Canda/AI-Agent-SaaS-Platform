"""Audit logging utilities for security-sensitive events."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.extended import AuditLog
from app.monitoring.logging import StructuredLogger


logger = StructuredLogger(__name__)


class AuditLogger:
    """Persists audit events and mirrors them to structured logs."""

    @staticmethod
    def log_event(
        db: Session | None,
        action: str,
        tenant_id: str | None,
        user_id: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "action": action,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        logger.log_execution("audit_event", payload)

        if db is None:
            return

        try:
            event = AuditLog(
                tenant_id=tenant_id,
                user_id=user_id,
                action=action,
                event_metadata=metadata or {},
            )
            db.add(event)
            db.flush()
        except SQLAlchemyError as exc:
            logger.log_error("audit_log_db_error", {"error": str(exc), "action": action})
        except Exception as exc:  # pragma: no cover - defensive path
            logger.log_error("audit_log_error", {"error": str(exc), "action": action})
