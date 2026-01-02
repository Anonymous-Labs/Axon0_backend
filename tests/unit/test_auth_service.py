"""
Unit tests for authentication service.
"""
import pytest
from app.services.auth import AuthService
from app.schemas.user import UserCreate
from app.exceptions import AuthenticationError


@pytest.mark.asyncio
async def test_authenticate_user_success(db_session, test_user):
    """Test successful user authentication."""
    auth_service = AuthService(db_session)
    
    user = await auth_service.authenticate_user("testuser", "testpassword123")
    
    assert user is not None
    assert user.id == test_user.id
    assert user.username == test_user.username
    assert user.email == test_user.email


@pytest.mark.asyncio
async def test_authenticate_user_wrong_password(db_session, test_user):
    """Test authentication with wrong password."""
    auth_service = AuthService(db_session)
    
    user = await auth_service.authenticate_user("testuser", "wrongpassword")
    
    assert user is None


@pytest.mark.asyncio
async def test_authenticate_user_not_found(db_session):
    """Test authentication with non-existent user."""
    auth_service = AuthService(db_session)
    
    user = await auth_service.authenticate_user("nonexistent", "password")
    
    assert user is None


@pytest.mark.asyncio
async def test_authenticate_user_by_email(db_session, test_user):
    """Test authentication using email instead of username."""
    auth_service = AuthService(db_session)
    
    user = await auth_service.authenticate_user("test@example.com", "testpassword123")
    
    assert user is not None
    assert user.id == test_user.id


@pytest.mark.asyncio
async def test_create_user_success(db_session):
    """Test successful user creation."""
    auth_service = AuthService(db_session)
    
    user_data = UserCreate(
        email="newuser@example.com",
        username="newuser",
        password="securepassword123",
        full_name="New User"
    )
    
    user = await auth_service.create_user(user_data)
    
    assert user is not None
    assert user.email == "newuser@example.com"
    assert user.username == "newuser"
    assert user.full_name == "New User"
    assert user.hashed_password != "securepassword123"  # Should be hashed


@pytest.mark.asyncio
async def test_create_user_duplicate_email(db_session, test_user):
    """Test user creation with duplicate email."""
    auth_service = AuthService(db_session)
    
    user_data = UserCreate(
        email=test_user.email,
        username="differentuser",
        password="password123",
    )
    
    with pytest.raises(Exception):  # Should raise HTTPException
        await auth_service.create_user(user_data)


@pytest.mark.asyncio
async def test_create_user_duplicate_username(db_session, test_user):
    """Test user creation with duplicate username."""
    auth_service = AuthService(db_session)
    
    user_data = UserCreate(
        email="different@example.com",
        username=test_user.username,
        password="password123",
    )
    
    with pytest.raises(Exception):  # Should raise HTTPException
        await auth_service.create_user(user_data)

