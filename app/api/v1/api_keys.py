from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.database import get_db
from app.schemas.memory import APIKey as APIKeySchema, APIKeyCreate, APIKeyList
from app.schemas.user import User as UserSchema
from app.models.user import User as UserModel
from app.services.api_key import APIKeyService
from app.utils.auth import verify_token

security = HTTPBearer()

router = APIRouter()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> UserSchema:
    """Get current authenticated user from JWT token."""
    token = credentials.credentials
    username = verify_token(token)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(UserModel).where(UserModel.username == username))
    user = result.scalars().first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


@router.post("/", response_model=APIKeySchema)
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new API key."""
    api_key_service = APIKeyService(db)
    try:
        api_key = await api_key_service.create_api_key(key_data, current_user.id)
        return api_key
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create API key: {str(e)}"
        )


@router.get("/", response_model=List[APIKeyList])
async def get_api_keys(
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all API keys for the current user."""
    api_key_service = APIKeyService(db)
    try:
        api_keys = await api_key_service.get_user_api_keys(current_user.id)
        return api_keys
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve API keys: {str(e)}"
        )


@router.delete("/{key_id}")
async def delete_api_key(
    key_id: int,
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete an API key."""
    api_key_service = APIKeyService(db)
    deleted = await api_key_service.delete_api_key(key_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )

    return {"message": "API key deleted successfully"}


@router.put("/{key_id}/regenerate")
async def regenerate_api_key(
    key_id: int,
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Regenerate an API key (create new key value)."""
    api_key_service = APIKeyService(db)
    # First get the existing key
    api_keys = await api_key_service.get_user_api_keys(current_user.id)
    existing_key = next((k for k in api_keys if k.id == key_id), None)

    if not existing_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )

    # Delete the old key
    await api_key_service.delete_api_key(key_id, current_user.id)

    # Create a new key with same settings
    new_key_data = APIKeyCreate(
        name=f"{existing_key.name} (regenerated)",
        description=existing_key.description,
        permissions=existing_key.permissions,
        expires_at=existing_key.expires_at,
    )

    new_api_key = await api_key_service.create_api_key(new_key_data, current_user.id)
    return {
        "message": "API key regenerated successfully",
        "api_key": new_api_key
    }
