"""
Metrics endpoint for monitoring (admin only in production).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User as UserModel
from app.core.monitoring import get_metrics
from app.utils.auth import verify_token
from app.config import settings

router = APIRouter()
security = HTTPBearer()


async def get_admin_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """Get current user and verify admin access."""
    token = credentials.credentials
    username = verify_token(token)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    result = await db.execute(select(UserModel).where(UserModel.username == username))
    user = result.scalars().first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    # In production, require superuser for metrics
    if settings.environment == "production" and not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    
    return user


@router.get("/")
async def get_application_metrics(
    current_user = Depends(get_admin_user)
):
    """
    Get application metrics (admin only in production).
    
    Returns:
        dict: Application metrics
    """
    return get_metrics()

