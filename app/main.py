from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.database import create_tables
from app.api.auth.routes import router as auth_router
from app.api.v1.memories import router as memories_router
from app.api.v1.api_keys import router as api_keys_router
from app.middleware.rate_limit import RateLimitMiddleware, APIKeyRateLimitMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await create_tables()
    yield
    # Shutdown
    # Add cleanup code here if needed


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Universal Memory Layer - AXON",
    lifespan=lifespan
)

# Rate limiting middleware
app.add_middleware(APIKeyRateLimitMiddleware, requests_per_minute=100)  # API key requests
app.add_middleware(RateLimitMiddleware, requests_per_minute=60)  # General requests

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


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Welcome to AXON - Universal Memory Layer",
        "version": settings.app_version,
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "axon-memory"}
