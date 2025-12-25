import time
from collections import defaultdict
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)  # client_ip -> list of timestamps

    async def dispatch(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)

        # Clean old requests (older than 1 minute)
        current_time = time.time()
        self.requests[client_ip] = [
            timestamp for timestamp in self.requests[client_ip]
            if current_time - timestamp < 60
        ]

        # Check if rate limit exceeded
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
                headers={"Retry-After": "60"}
            )

        # Add current request timestamp
        self.requests[client_ip].append(current_time)

        # Process the request
        response = await call_next(request)
        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Try X-Forwarded-For header first (for proxies)
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            # Take the first IP if multiple are present
            return x_forwarded_for.split(",")[0].strip()

        # Fall back to direct client IP
        client_ip = request.client.host if request.client else "unknown"
        return client_ip


class APIKeyRateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting specifically for API key authenticated requests."""

    def __init__(self, app, requests_per_minute: int = 100):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)  # api_key -> list of timestamps

    async def dispatch(self, request: Request, call_next):
        # Check if request has API key authentication
        api_key = self._extract_api_key(request)

        if api_key:
            # Clean old requests (older than 1 minute)
            current_time = time.time()
            self.requests[api_key] = [
                timestamp for timestamp in self.requests[api_key]
                if current_time - timestamp < 60
            ]

            # Check if rate limit exceeded
            if len(self.requests[api_key]) >= self.requests_per_minute:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="API key rate limit exceeded. Please try again later.",
                    headers={"Retry-After": "60"}
                )

            # Add current request timestamp
            self.requests[api_key].append(current_time)

        # Process the request
        response = await call_next(request)
        return response

    def _extract_api_key(self, request: Request) -> str:
        """Extract API key from Authorization header."""
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            # Check if it looks like an API key (longer than JWT tokens)
            token = auth_header[7:]  # Remove "Bearer "
            if len(token) > 50:  # API keys are typically longer than JWT tokens
                return token
        return ""
