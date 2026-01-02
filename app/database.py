"""
Database configuration and session management.
"""
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy import text
import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Determine pool class and engine kwargs based on database type
# SQLite doesn't support connection pooling
if "sqlite" in settings.database_url:
    pool_class = NullPool
    connect_args = {"check_same_thread": False}
    # SQLite doesn't support pool_size, max_overflow, or pool_pre_ping
    engine_kwargs = {
        "poolclass": pool_class,
        "connect_args": connect_args,
    }
else:
    pool_class = QueuePool
    connect_args = {}
    engine_kwargs = {
        "poolclass": pool_class,
        "pool_size": settings.database_pool_size,
        "max_overflow": settings.database_max_overflow,
        "pool_pre_ping": True,  # Verify connections before using
        "connect_args": connect_args,
    }

# Create database engine with connection pooling
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    **engine_kwargs
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db() -> AsyncSession:
    """
    Dependency for getting database session.
    
    Yields:
        AsyncSession: Database session
    
    Note:
        Automatically commits on success and rolls back on exception.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            logger.error("Database session rollback due to exception", exc_info=True)
            raise
        finally:
            await session.close()


async def create_tables():
    """
    Create all database tables if they don't exist.
    
    Raises:
        Exception: If table creation fails
    """
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created/verified successfully")
    except Exception as e:
        logger.error("Failed to create database tables", exc_info=True)
        raise


async def check_database_health() -> bool:
    """
    Check if database connection is healthy.
    
    Returns:
        bool: True if database is accessible, False otherwise
    """
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("Database health check failed", extra={"error": str(e)})
        return False
