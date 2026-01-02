"""
Custom exception hierarchy for the AXON application.
All API exceptions should inherit from BaseAPIException.
"""

from typing import Optional, Dict, Any


class BaseAPIException(Exception):
    """Base exception for all API errors."""
    
    def __init__(
        self,
        detail: Optional[str] = None,
        status_code: int = 500,
        headers: Optional[Dict[str, Any]] = None
    ):
        self.detail = detail or self.default_detail
        self.status_code = status_code
        self.headers = headers or {}
        super().__init__(self.detail)
    
    @property
    def default_detail(self) -> str:
        """Default error message for this exception type."""
        return "An error occurred"


class NotFoundError(BaseAPIException):
    """Exception raised when a resource is not found."""
    
    status_code = 404
    
    @property
    def default_detail(self) -> str:
        return "Resource not found"


class ValidationError(BaseAPIException):
    """Exception raised when validation fails."""
    
    status_code = 400
    
    @property
    def default_detail(self) -> str:
        return "Validation failed"


class AuthenticationError(BaseAPIException):
    """Exception raised when authentication fails."""
    
    status_code = 401
    
    @property
    def default_detail(self) -> str:
        return "Authentication failed"


class AuthorizationError(BaseAPIException):
    """Exception raised when user lacks required permissions."""
    
    status_code = 403
    
    @property
    def default_detail(self) -> str:
        return "Insufficient permissions"


class ConflictError(BaseAPIException):
    """Exception raised when a resource conflict occurs."""
    
    status_code = 409
    
    @property
    def default_detail(self) -> str:
        return "Resource conflict"


class RateLimitError(BaseAPIException):
    """Exception raised when rate limit is exceeded."""
    
    status_code = 429
    
    @property
    def default_detail(self) -> str:
        return "Rate limit exceeded"


class InternalServerError(BaseAPIException):
    """Exception raised for internal server errors."""
    
    status_code = 500
    
    @property
    def default_detail(self) -> str:
        return "Internal server error"

