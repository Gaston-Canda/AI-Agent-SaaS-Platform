"""
Worker process for executing agents.
Can be run as: celery -A app.workers.celery_worker worker --loglevel=info
"""

from app.queue.queue import celery_app
from app.workers import tasks as worker_tasks  # noqa: F401
from app.tasks import agent_tasks  # noqa: F401

__all__ = ["celery_app"]
