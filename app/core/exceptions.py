"""
Custom exceptions for the application.

These exceptions are used throughout the service layer and API endpoints
to provide consistent error handling and messaging.
"""


class AppError(Exception):
    """Base exception for application errors."""
    
    def __init__(self, message: str, status_code: int = 500):
        """Initialize app error."""
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundError(AppError):
    """Resource not found error (404)."""
    
    def __init__(self, message: str = "Resource not found"):
        """Initialize not found error."""
        super().__init__(message, status_code=404)


class ValidationError(AppError):
    """Validation error (400)."""
    
    def __init__(self, message: str = "Validation failed"):
        """Initialize validation error."""
        super().__init__(message, status_code=400)


class ForbiddenError(AppError):
    """Access forbidden error (403)."""
    
    def __init__(self, message: str = "Access denied"):
        """Initialize forbidden error."""
        super().__init__(message, status_code=403)


class UnauthorizedError(AppError):
    """Unauthorized error (401)."""
    
    def __init__(self, message: str = "Unauthorized"):
        """Initialize unauthorized error."""
        super().__init__(message, status_code=401)


class ConflictError(AppError):
    """Conflict error (409)."""
    
    def __init__(self, message: str = "Resource conflict"):
        """Initialize conflict error."""
        super().__init__(message, status_code=409)


# Compatibility aliases used across older/newer modules
class ResourceNotFoundError(NotFoundError):
    """Backward-compatible alias for NotFoundError."""


class PermissionDeniedError(ForbiddenError):
    """Backward-compatible alias for ForbiddenError."""


class InternalServerError(AppError):
    """Internal server error (500)."""
    
    def __init__(self, message: str = "Internal server error"):
        """Initialize internal server error."""
        super().__init__(message, status_code=500)
