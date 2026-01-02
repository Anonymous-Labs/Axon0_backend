"""
Redis-based rate limiting middleware for distributed rate limiting.
"""
import time
import logging
from typing import Tuple
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.redis_client import get_redis_client
from app.exceptions import RateLimitError

logger = logging.getLogger(__name__)


class RedisRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using Redis for distributed rate limiting.
    
    This allows rate limiting to work across multiple server instances.
    """
    
    def __init__(self, app, requests_per_minute: int = 60, key_prefix: str = "rate_limit"):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.key_prefix = key_prefix
    
    async def dispatch(self, request: Request, call_next):
        """
        Check rate limit before processing request.
        
        Args:
            request: FastAPI request object
            call_next: Next middleware/route handler
        
        Returns:
            Response object
        """
        try:
            # Get client identifier
            client_id = self._get_client_id(request)
            
            # Check rate limit
            allowed, remaining, reset_time = await self._check_rate_limit(client_id)
            
            if not allowed:
                logger.warning(
                    "Rate limit exceeded",
                    extra={
                        "client_id": client_id,
                        "path": request.url.path,
                        "method": request.method,
                    }
                )
                raise RateLimitError(
                    detail=f"Rate limit exceeded. Maximum {self.requests_per_minute} requests per minute.",
                    headers={
                        "X-RateLimit-Limit": str(self.requests_per_minute),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(reset_time),
                        "Retry-After": str(int(reset_time - time.time())),
                    }
                )
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers
            response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(reset_time)
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Rate limit middleware error", extra={"error": str(e)}, exc_info=True)
            # If Redis fails, allow request to proceed (fail open)
            return await call_next(request)
    
    async def _check_rate_limit(self, client_id: str) -> Tuple[bool, int, int]:
        """
        Check if client has exceeded rate limit.
        
        Args:
            client_id: Unique identifier for the client
        
        Returns:
            Tuple of (allowed, remaining_requests, reset_timestamp)
        """
        try:
            redis_client = await get_redis_client()
            if redis_client is None:
                # Redis unavailable, fail open
                return True, self.requests_per_minute, int(time.time()) + 60
            
            key = f"{self.key_prefix}:{client_id}"
            window_start = int(time.time() / 60) * 60  # Current minute window
            window_key = f"{key}:{window_start}"
            
            # Increment counter for this window
            current_count = await redis_client.incr(window_key)
            
            # Set expiration to end of current minute + 1 minute buffer
            await redis_client.expire(window_key, 120)
            
            # Calculate remaining requests
            remaining = max(0, self.requests_per_minute - current_count)
            allowed = current_count <= self.requests_per_minute
            
            # Reset time is start of next minute
            reset_time = window_start + 60
            
            return allowed, remaining, reset_time
            
        except Exception as e:
            logger.error("Rate limit check failed", extra={"error": str(e)}, exc_info=True)
            # Fail open - allow request if Redis is down
            return True, self.requests_per_minute, int(time.time()) + 60
    
    def _get_client_id(self, request: Request) -> str:
        """
        Get unique identifier for the client.
        
        Args:
            request: FastAPI request object
        
        Returns:
            Client identifier string
        """
        # Check for API key in Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            # If token looks like an API key (longer than typical JWT), use it
            if len(token) > 50:
                return f"api_key:{token[:20]}"  # Use first 20 chars for key
        
        # Fall back to IP address
        return f"ip:{self._get_client_ip(request)}"
    
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
            return x_forwarded_for.split(",")[0].strip()
        
        # Check for real IP header
        x_real_ip = request.headers.get("X-Real-IP")
        if x_real_ip:
            return x_real_ip
        
        # Fall back to direct client IP
        if request.client:
            return request.client.host
        
        return "unknown"


class RedisAPIKeyRateLimitMiddleware(RedisRateLimitMiddleware):
    """
    Rate limiting middleware specifically for API key authenticated requests.
    Uses higher rate limits than general requests.
    """
    
    def __init__(self, app, requests_per_minute: int = 100):
        super().__init__(app, requests_per_minute=requests_per_minute, key_prefix="api_rate_limit")
    
    async def dispatch(self, request: Request, call_next):
        """
        Only apply rate limiting if request has API key authentication.
        
        Args:
            request: FastAPI request object
            call_next: Next middleware/route handler
        
        Returns:
            Response object
        """
        # Check if request has API key authentication
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            # If token looks like an API key (longer than typical JWT), apply rate limiting
            if len(token) > 50:
                return await super().dispatch(request, call_next)
        
        # No API key, skip rate limiting (will be handled by general rate limiter)
        return await call_next(request)

