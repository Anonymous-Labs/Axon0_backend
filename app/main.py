"""
Main FastAPI application entry point.
"""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from app.config import settings
from app.database import create_tables
from app.api.auth.routes import router as auth_router
from app.api.v1.memories import router as memories_router
from app.api.v1.api_keys import router as api_keys_router
from app.api.v1.health import router as health_router
from app.api.v1.metrics import router as metrics_router
from app.middleware.rate_limit_redis import RedisRateLimitMiddleware, RedisAPIKeyRateLimitMiddleware
from app.middleware.logging import LoggingMiddleware
from app.middleware.security import SecurityHeadersMiddleware, RequestIDMiddleware
from app.core.redis_client import close_redis_client
from app.exceptions import (
    BaseAPIException,
    NotFoundError,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    RateLimitError,
    InternalServerError
)
from app.core.logging import setup_logging

# Set up logging
logger = setup_logging()
logger.info("Application starting", extra={"environment": settings.environment})


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown tasks.
    
    Yields:
        None: Application is ready to serve requests
    """
    # Startup
    logger.info("Application startup", extra={"version": settings.app_version})
    try:
        await create_tables()
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.error("Failed to create database tables", exc_info=True)
        raise
    
    yield
    
    # Shutdown
    logger.info("Application shutdown")
    try:
        await close_redis_client()
        logger.info("Redis client closed")
    except Exception as e:
        logger.error("Error closing Redis client", exc_info=True)


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Universal Memory Layer - AXON",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Exception handlers
@app.exception_handler(BaseAPIException)
async def custom_exception_handler(request: Request, exc: BaseAPIException):
    """
    Global exception handler for custom API exceptions.
    
    Args:
        request: FastAPI request object
        exc: Exception instance
    
    Returns:
        JSONResponse with error details
    """
    logger.warning(
        "API exception raised",
        extra={
            "exception_type": exc.__class__.__name__,
            "status_code": exc.status_code,
            "detail": exc.detail,
            "path": request.url.path,
            "method": request.method,
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.__class__.__name__,
            "detail": exc.detail,
            "path": request.url.path,
        },
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unexpected exceptions.
    
    Args:
        request: FastAPI request object
        exc: Exception instance
    
    Returns:
        JSONResponse with generic error message
    """
    logger.error(
        "Unhandled exception",
        extra={
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "path": request.url.path,
            "method": request.method,
        },
        exc_info=True
    )
    
    # Don't expose internal errors in production
    if settings.environment == "production":
        detail = "An internal error occurred"
    else:
        detail = str(exc)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "detail": detail,
            "path": request.url.path,
        }
    )


# Middleware order matters - add in reverse order of execution
# Security headers (outermost)
app.add_middleware(SecurityHeadersMiddleware)

# Request ID for tracing
app.add_middleware(RequestIDMiddleware)

# Logging middleware (runs first, logs last)
app.add_middleware(LoggingMiddleware)

# Redis-based rate limiting middleware
app.add_middleware(RedisAPIKeyRateLimitMiddleware, requests_per_minute=100)  # API key requests
app.add_middleware(RedisRateLimitMiddleware, requests_per_minute=60)  # General requests

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(
    auth_router,
    prefix="/auth",
    tags=["authentication"]
)

app.include_router(
    memories_router,
    prefix="/api/v1/memories",
    tags=["memories"]
)

app.include_router(
    api_keys_router,
    prefix="/api/v1/api-keys",
    tags=["api-keys"]
)

app.include_router(
    health_router,
    prefix="/health",
    tags=["health"]
)

app.include_router(
    metrics_router,
    prefix="/api/v1/metrics",
    tags=["metrics"]
)


@app.get("/")
async def root():
    """
    Root endpoint with API information.
    
    Returns:
        dict: API information and available endpoints
    """
    return {
        "message": "Welcome to AXON - Universal Memory Layer",
        "version": settings.app_version,
        "environment": settings.environment,
        "docs": "/docs" if settings.debug else None,
        "redoc": "/redoc" if settings.debug else None,
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring and load balancers.
    
    Returns:
        dict: Health status information
    """
    return {
        "status": "healthy",
        "service": "axon-memory",
        "version": settings.app_version,
    }
