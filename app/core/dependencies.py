"""
Dependency injection for services and database sessions.
"""
from functools import lru_cache
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.memory import MemoryService
from app.services.auth import AuthService
from app.services.api_key import APIKeyService


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting database session.
    
    Yields:
        AsyncSession: Database session
    """
    async for session in get_db():
        yield session


def get_memory_service(db: AsyncSession = None) -> MemoryService:
    """
    Dependency for getting memory service instance.
    
    Args:
        db: Database session (injected by FastAPI)
    
    Returns:
        MemoryService: Memory service instance
    """
    if db is None:
        # This should not happen in normal usage, but handle gracefully
        raise ValueError("Database session is required")
    return MemoryService(db)


def get_auth_service(db: AsyncSession = None) -> AuthService:
    """
    Dependency for getting auth service instance.
    
    Args:
        db: Database session (injected by FastAPI)
    
    Returns:
        AuthService: Auth service instance
    """
    if db is None:
        raise ValueError("Database session is required")
    return AuthService(db)


def get_api_key_service(db: AsyncSession = None) -> APIKeyService:
    """
    Dependency for getting API key service instance.
    
    Args:
        db: Database session (injected by FastAPI)
    
    Returns:
        APIKeyService: API key service instance
    """
    if db is None:
        raise ValueError("Database session is required")
    return APIKeyService(db)

