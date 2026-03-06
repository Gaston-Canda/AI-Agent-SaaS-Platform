"""Celery tasks for optional async agent execution endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from app.db.database import SessionLocal
from app.models.agent import AgentExecution
from app.models.extended import ExecutionStatus
from app.monitoring.logging import StructuredLogger
from app.queue.queue import celery_app


logger = StructuredLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.tasks.agent_tasks.execute_agent_task",
    max_retries=3,
    time_limit=600,
)
def execute_agent_task(
    self,
    agent_id: str,
    user_id: str,
    tenant_id: str,
    message: str,
    execution_id: str | None = None,
) -> dict:
    """
    Queue-friendly async execution entrypoint.

    Required contract:
      execute_agent_task(agent_id, user_id, tenant_id, message)

    Optional:
      execution_id for API flows that pre-create execution rows.
    """
    db = SessionLocal()
    try:
        if execution_id is None:
            execution = AgentExecution(
                agent_id=agent_id,
                input_data={"message": message},
                status=ExecutionStatus.PENDING.value,
            )
            db.add(execution)
            db.commit()
            db.refresh(execution)
            execution_id = execution.id

        from app.workers.tasks import execute_agent

        result = execute_agent.run(
            execution_id=execution_id,
            agent_id=agent_id,
            tenant_id=tenant_id,
            user_id=user_id,
            input_data={"message": message},
        )

        return {
            "execution_id": execution_id,
            "status": result.get("status", "completed"),
            "success": result.get("success", False),
        }
    except Exception as exc:
        logger.log_error(
            "Async execution task failed",
            {"error": str(exc), "execution_id": execution_id, "retries": self.request.retries},
        )
        if execution_id:
            execution = db.query(AgentExecution).filter(AgentExecution.id == execution_id).first()
            if execution:
                execution.status = ExecutionStatus.FAILED.value
                execution.error_message = str(exc)
                execution.completed_at = datetime.now(timezone.utc)
                db.commit()
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=2 ** self.request.retries)
        return {"execution_id": execution_id, "status": "failed", "success": False, "error": str(exc)}
    finally:
        db.close()
