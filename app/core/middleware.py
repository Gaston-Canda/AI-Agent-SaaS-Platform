"""
Middleware for logging, tracing, and error handling.
"""

import time
import traceback
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.monitoring.logging import logger, RequestTracer
from app.core.rate_limiter import SecurityRateLimiter


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for structured logging of requests and responses."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request and response."""
        # Generate trace ID
        trace_id = RequestTracer.generate_trace_id()
        
        # Extract user info from token if available
        user_id = "anonymous"
        try:
            # Would extract from JWT token in real scenario
            pass
        except Exception:
            pass
        
        # Log incoming request
        logger.log_request(
            trace_id,
            request.method,
            request.url.path,
            user_id,
        )
        
        # Record start time
        start_time = time.time()
        
        try:
            # Call next middleware/handler
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log response
            logger.log_response(
                trace_id,
                response.status_code,
                duration_ms,
            )
            
            # Add trace ID to response headers
            response.headers["X-Trace-ID"] = trace_id
            
            return response
            
        except Exception as exc:
            # Log error
            duration_ms = (time.time() - start_time) * 1000
            logger.log_error(
                trace_id,
                type(exc).__name__,
                str(exc),
                traceback.format_exc(),
            )
            
            raise


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for route-aware rate limiting per tenant/user/ip."""

    def __init__(self, app):
        super().__init__(app)
        self.limiter = SecurityRateLimiter()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check rate limit before processing request."""
        profile = self.limiter.get_profile(request.url.path)
        if profile is None:
            return await call_next(request)

        auth_header = request.headers.get("authorization")
        remote_addr = request.client.host if request.client else "unknown"
        subjects = self.limiter.build_subjects(auth_header, request.url.path, remote_addr)

        remaining_by_subject: list[int] = []
        for subject in subjects:
            allowed, remaining = self.limiter.is_allowed(subject, profile)
            remaining_by_subject.append(remaining)
            if not allowed:
                return Response(
                    status_code=429,
                    content="Rate limit exceeded. Please try again later.",
                    headers={
                        "Retry-After": "60",
                        "X-RateLimit-Remaining": str(min(remaining_by_subject) if remaining_by_subject else 0),
                    },
                )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(min(remaining_by_subject) if remaining_by_subject else 0)
        return response
