"""
Structured logging and monitoring.
"""

import logging
import uuid
from typing import Dict, Any
from datetime import datetime, timezone
from pythonjsonlogger import jsonlogger
import sys
from app.core.config import settings


class StructuredLogger:
    """Structured logging with JSON output."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
        self.logger.setLevel(level)
        self.logger.propagate = False

        if not self.logger.handlers:
            stream_handler = logging.StreamHandler(sys.stdout)
            if settings.LOG_JSON:
                formatter = jsonlogger.JsonFormatter()
            else:
                formatter = logging.Formatter(
                    "%(asctime)s %(levelname)s %(name)s %(message)s"
                )
            stream_handler.setFormatter(formatter)
            self.logger.addHandler(stream_handler)
    
    def log_request(self, request_id: str, method: str, path: str, user_id: str) -> None:
        """Log incoming request."""
        self.logger.info({
            "event": "request_received",
            "request_id": request_id,
            "method": method,
            "path": path,
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    
    def log_response(
        self,
        request_id: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        """Log response sent."""
        self.logger.info({
            "event": "response_sent",
            "request_id": request_id,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    
    def log_error(
        self,
        request_id: str,
        error_type: str = None,
        error_message: str = None,
        stack_trace: str = None,
    ) -> None:
        """
        Log error.

        Supports legacy call style:
            log_error("message", {"context": "value"})
        """
        if isinstance(error_type, dict) and error_message is None:
            self.logger.error({
                "event": "error",
                "request_id": None,
                "error_type": "runtime_error",
                "error_message": request_id,
                "stack_trace": None,
                "details": error_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return

        self.logger.error({
            "event": "error",
            "request_id": request_id,
            "error_type": error_type or "runtime_error",
            "error_message": error_message or "",
            "stack_trace": stack_trace,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    
    def log_execution(
        self,
        execution_id: str,
        agent_id: str = None,
        tenant_id: str = None,
        status: str = None,
        details: Dict[str, Any] = None,
    ) -> None:
        """
        Log agent execution event.

        Supports legacy call style:
            log_execution("message", {"execution_id": "...", ...})
        """
        if isinstance(agent_id, dict) and tenant_id is None and status is None:
            self.logger.info({
                "event": "agent_execution",
                "message": execution_id,
                "execution_id": agent_id.get("execution_id"),
                "agent_id": agent_id.get("agent_id"),
                "tenant_id": agent_id.get("tenant_id"),
                "status": agent_id.get("status", "info"),
                "details": agent_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return

        self.logger.info({
            "event": "agent_execution",
            "execution_id": execution_id,
            "agent_id": agent_id,
            "tenant_id": tenant_id,
            "status": status or "info",
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


class RequestTracer:
    """Request tracing with unique IDs."""
    
    @staticmethod
    def generate_trace_id() -> str:
        """Generate unique trace ID."""
        return str(uuid.uuid4())
    
    @staticmethod
    def get_trace_context() -> Dict[str, str]:
        """Get current trace context."""
        # In production, this would use contextvars
        return {
            "trace_id": str(uuid.uuid4()),
            "span_id": str(uuid.uuid4()),
        }


# Global logger instance
logger = StructuredLogger("ai_agents")
