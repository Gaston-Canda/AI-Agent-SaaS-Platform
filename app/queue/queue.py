"""
Queue system for agent execution using Redis and Celery.
Handles task queuing and result storage.
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional
from celery import Celery
from app.core.config import settings

# Initialize Celery
celery_app = Celery(
    "ai_agents",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes hard limit
    task_soft_time_limit=25 * 60,  # 25 minutes soft limit
)


class ExecutionQueue:
    """Interface for queueing agent executions."""
    
    @staticmethod
    def queue_execution(
        execution_id: str,
        agent_id: str,
        tenant_id: str,
        input_data: Dict[str, Any],
        user_id: Optional[str] = None,
        agent_config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Queue an agent execution task.
        
        Returns task ID for tracking.
        """
        # Backward compatibility:
        # old signature: (..., input_data, agent_config)
        if isinstance(user_id, dict) and agent_config is None:
            agent_config = user_id
            user_id = None

        message = input_data.get("message", "")
        if user_id or agent_config is not None:
            args = (execution_id, agent_id, tenant_id, user_id, input_data)
            task_name = "app.workers.tasks.execute_agent"
        else:
            args = (agent_id, "", tenant_id, message, execution_id)
            task_name = "app.tasks.agent_tasks.execute_agent_task"

        task = celery_app.send_task(
            task_name,
            args=args,
            queue="default",
            retry=True,
            retry_policy={
                "max_retries": 3,
                "interval_start": 1,
                "interval_step": 1,
                "interval_max": 10,
            },
        )
        return task.id
    
    @staticmethod
    def get_task_status(task_id: str) -> Dict[str, Any]:
        """
        Get the status of a queued task.
        """
        from celery.result import AsyncResult
        
        result = AsyncResult(task_id, app=celery_app)
        return {
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.successful() else None,
            "error": str(result.info) if result.failed() else None,
        }
