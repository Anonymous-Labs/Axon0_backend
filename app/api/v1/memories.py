from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.database import get_db
from app.models.user import User as UserModel
from app.schemas.memory import (
    Memory, MemoryCreate, MemoryUpdate, MemorySearch,
    MemorySearchResponse, FeedbackCreate, MemoryStats
)
from app.schemas.user import User as UserSchema
from app.services.memory import MemoryService
from app.core.dependencies import get_memory_service
from app.core.decorators import cache_result
from app.core.redis_client import cache_service
from app.utils.auth import verify_token
from sqlalchemy import select

security = HTTPBearer()


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

router = APIRouter()


@router.post("/", response_model=Memory)
async def create_memory(
    memory_data: MemoryCreate,
    current_user: UserSchema = Depends(get_current_user),
    memory_service: MemoryService = Depends(get_memory_service),
    db: AsyncSession = Depends(get_db)
):
    """Create a new memory."""
    try:
        memory = await memory_service.create_memory(memory_data, current_user.id)
        
        # Invalidate user's memory list cache (non-blocking)
        try:
            await cache_service.delete(f"memories:list:{current_user.id}")
        except Exception:
            # Cache unavailable, continue without invalidation
            pass
        
        return memory
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create memory: {str(e)}"
        )


@router.get("/{memory_id}", response_model=Memory)
async def get_memory(
    memory_id: int,
    current_user: UserSchema = Depends(get_current_user),
    memory_service: MemoryService = Depends(get_memory_service),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific memory by ID."""
    # Check cache first (gracefully handle Redis unavailability)
    try:
        cache_key = f"memory:{current_user.id}:{memory_id}"
        cached_memory = await cache_service.get(cache_key)
        if cached_memory:
            # Return the Memory object, not the dict
            # The cache returns a dict, but we need to return the actual Memory model
            # For now, just fetch from DB to ensure consistency
            pass
    except Exception:
        # Cache unavailable, continue with DB lookup
        pass
    
    memory = await memory_service.get_memory(memory_id, current_user.id)
    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found"
        )
    
    # Cache the result (non-blocking)
    try:
        cache_key = f"memory:{current_user.id}:{memory_id}"
        memory_dict = {
            "id": memory.id,
            "user_id": memory.user_id,
            "content": memory.content,
            "title": memory.title,
            "summary": memory.summary,
            "tags": memory.tags,
            "importance_score": memory.importance_score,
            "priority": memory.priority,
            "created_at": memory.created_at.isoformat() if memory.created_at else None,
            "updated_at": memory.updated_at.isoformat() if memory.updated_at else None,
        }
        await cache_service.set(cache_key, memory_dict, ttl=300)  # Cache for 5 minutes
    except Exception:
        # Cache unavailable, continue without caching
        pass
    
    return memory


@router.put("/{memory_id}", response_model=Memory)
async def update_memory(
    memory_id: int,
    memory_data: MemoryUpdate,
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a memory."""
    memory_service = MemoryService(db)
    memory = await memory_service.update_memory(memory_id, memory_data, current_user.id)
    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found"
        )
    return memory


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: int,
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a memory (soft delete)."""
    memory_service = MemoryService(db)
    deleted = await memory_service.delete_memory(memory_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found"
        )
    return {"message": "Memory deleted successfully"}


@router.get("/", response_model=List[Memory])
async def get_memories(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: UserSchema = Depends(get_current_user),
    memory_service: MemoryService = Depends(get_memory_service),
    db: AsyncSession = Depends(get_db)
):
    """Get all memories for the current user."""
    # Try to get from cache (gracefully handle Redis unavailability)
    try:
        cache_key = f"memories:list:{current_user.id}:{limit}:{offset}"
        cached_memories = await cache_service.get(cache_key)
        # Note: We still fetch from DB to ensure we return Memory objects, not dicts
        # Cache is mainly for performance optimization
    except Exception:
        # Cache unavailable, continue with DB lookup
        pass
    
    memories = await memory_service.get_user_memories(current_user.id, limit, offset)
    
    # Cache the result (non-blocking)
    try:
        cache_key = f"memories:list:{current_user.id}:{limit}:{offset}"
        memories_list = [
            {
                "id": m.id,
                "user_id": m.user_id,
                "content": m.content,
                "title": m.title,
                "summary": m.summary,
                "tags": m.tags,
                "importance_score": m.importance_score,
                "priority": m.priority,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in memories
        ]
        await cache_service.set(cache_key, memories_list, ttl=180)  # Cache for 3 minutes
    except Exception:
        # Cache unavailable, continue without caching
        pass
    
    return memories


@router.post("/search", response_model=MemorySearchResponse)
async def search_memories(
    search_params: MemorySearch,
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Search memories with filters."""
    memory_service = MemoryService(db)
    try:
        result = await memory_service.search_memories(search_params, current_user.id)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.post("/{memory_id}/feedback")
async def add_feedback(
    memory_id: int,
    feedback_data: FeedbackCreate,
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Add feedback to a memory."""
    memory_service = MemoryService(db)
    try:
        feedback = await memory_service.add_feedback(feedback_data, current_user.id)
        return {"message": "Feedback added successfully", "feedback_id": feedback.id}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add feedback: {str(e)}"
        )


@router.get("/stats/overview", response_model=MemoryStats)
async def get_memory_stats(
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get memory statistics for the current user."""
    memory_service = MemoryService(db)
    try:
        stats = await memory_service.get_memory_stats(current_user.id)
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        )
