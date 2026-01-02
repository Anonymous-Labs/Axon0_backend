"""
Request/response logging middleware for tracking API usage.
"""

import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses."""
    
    async def dispatch(self, request: Request, call_next):
        """
        Log request details before processing and response details after.
        
        Args:
            request: FastAPI request object
            call_next: Next middleware/route handler
        
        Returns:
            Response object
        """
        # Extract client information
        client_ip = self._get_client_ip(request)
        method = request.method
        path = request.url.path
        query_params = str(request.query_params) if request.query_params else ""
        
        # Start timing
        start_time = time.time()
        
        # Log request
        logger.info(
            "Request started",
            extra={
                "type": "request",
                "method": method,
                "path": path,
                "query_params": query_params,
                "client_ip": client_ip,
                "user_agent": request.headers.get("user-agent", ""),
            }
        )
        
        # Process request
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            # Log successful response
            logger.info(
                "Request completed",
                extra={
                    "type": "response",
                    "method": method,
                    "path": path,
                    "status_code": response.status_code,
                    "process_time_ms": round(process_time * 1000, 2),
                    "client_ip": client_ip,
                }
            )
            
            # Add process time to response headers
            response.headers["X-Process-Time"] = str(round(process_time, 3))
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            
            # Log error
            logger.error(
                "Request failed",
                extra={
                    "type": "error",
                    "method": method,
                    "path": path,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "process_time_ms": round(process_time * 1000, 2),
                    "client_ip": client_ip,
                },
                exc_info=True
            )
            
            raise
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP address from request.
        
        Args:
            request: FastAPI request object
        
        Returns:
            Client IP address as string
        """
        # Check for forwarded IP (from proxy/load balancer)
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            # Take the first IP if multiple are present
            return x_forwarded_for.split(",")[0].strip()
        
        # Check for real IP header
        x_real_ip = request.headers.get("X-Real-IP")
        if x_real_ip:
            return x_real_ip
        
        # Fall back to direct client IP
        if request.client:
            return request.client.host
        
        return "unknown"

