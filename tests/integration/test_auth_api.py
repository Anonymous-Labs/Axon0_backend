"""
Integration tests for authentication API endpoints.
"""
import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient
from app.main import app


@pytest.mark.asyncio
async def test_register_user_success():
    """Test successful user registration."""
    client = TestClient(app)
    
    response = client.post(
        "/auth/register",
        json={
            "email": "newuser@test.com",
            "username": "newuser",
            "password": "securepassword123",
            "full_name": "New User"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "newuser@test.com"
    assert data["username"] == "newuser"
    assert "hashed_password" not in data  # Should not return password


@pytest.mark.asyncio
async def test_register_user_duplicate_email():
    """Test registration with duplicate email."""
    client = TestClient(app)
    
    # First registration
    client.post(
        "/auth/register",
        json={
            "email": "duplicate@test.com",
            "username": "user1",
            "password": "password123"
        }
    )
    
    # Second registration with same email
    response = client.post(
        "/auth/register",
        json={
            "email": "duplicate@test.com",
            "username": "user2",
            "password": "password123"
        }
    )
    
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_login_success():
    """Test successful login."""
    client = TestClient(app)
    
    # First register
    client.post(
        "/auth/register",
        json={
            "email": "login@test.com",
            "username": "loginuser",
            "password": "password123"
        }
    )
    
    # Then login
    response = client.post(
        "/auth/login",
        data={
            "username": "loginuser",
            "password": "password123"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password():
    """Test login with wrong password."""
    client = TestClient(app)
    
    # Register user
    client.post(
        "/auth/register",
        json={
            "email": "wrongpass@test.com",
            "username": "wrongpass",
            "password": "correctpassword"
        }
    )
    
    # Try to login with wrong password
    response = client.post(
        "/auth/login",
        data={
            "username": "wrongpass",
            "password": "wrongpassword"
        }
    )
    
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_with_token():
    """Test getting current user with valid token."""
    client = TestClient(app)
    
    # Register and login
    client.post(
        "/auth/register",
        json={
            "email": "me@test.com",
            "username": "meuser",
            "password": "password123"
        }
    )
    
    login_response = client.post(
        "/auth/login",
        data={
            "username": "meuser",
            "password": "password123"
        }
    )
    
    token = login_response.json()["access_token"]
    
    # Get current user
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "meuser"
    assert data["email"] == "me@test.com"


@pytest.mark.asyncio
async def test_get_current_user_invalid_token():
    """Test getting current user with invalid token."""
    client = TestClient(app)
    
    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid_token"}
    )
    
    assert response.status_code == 401

