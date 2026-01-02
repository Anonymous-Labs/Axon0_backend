"""
Pytest configuration and fixtures for testing.
"""
import pytest
import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.core.config import settings
from app.models.user import User
from app.models.memory import Memory, APIKey
from app.utils.auth import get_password_hash


# Test database URL (in-memory SQLite for testing)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Create a test database session.
    
    Yields:
        AsyncSession: Test database session
    """
    # Create all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async with TestSessionLocal() as session:
        yield session
    
    # Clean up
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """
    Create a test user.
    
    Args:
        db_session: Database session
    
    Returns:
        User: Test user instance
    """
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=get_password_hash("testpassword123"),
        full_name="Test User",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_memory(db_session: AsyncSession, test_user: User) -> Memory:
    """
    Create a test memory.
    
    Args:
        db_session: Database session
        test_user: Test user instance
    
    Returns:
        Memory: Test memory instance
    """
    memory = Memory(
        user_id=test_user.id,
        content="This is a test memory",
        title="Test Memory",
        importance_score=0.7,
        priority="high",
    )
    db_session.add(memory)
    await db_session.commit()
    await db_session.refresh(memory)
    return memory


@pytest.fixture
async def test_api_key(db_session: AsyncSession, test_user: User) -> APIKey:
    """
    Create a test API key.
    
    Args:
        db_session: Database session
        test_user: Test user instance
    
    Returns:
        APIKey: Test API key instance
    """
    import secrets
    api_key = APIKey(
        user_id=test_user.id,
        key=secrets.token_urlsafe(64),
        name="Test API Key",
        description="Test API key for testing",
        permissions=["read", "write"],
        is_active=True,
    )
    db_session.add(api_key)
    await db_session.commit()
    await db_session.refresh(api_key)
    return api_key


@pytest.fixture
def override_get_db(db_session: AsyncSession):
    """
    Override get_db dependency for testing.
    
    Args:
        db_session: Test database session
    
    Yields:
        AsyncSession: Test database session
    """
    async def _get_db():
        yield db_session
    
    return _get_db

