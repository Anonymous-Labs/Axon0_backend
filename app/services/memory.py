from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_, desc, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json

from app.models.memory import Memory, Feedback
from app.schemas.memory import (
    MemoryCreate, MemoryUpdate, MemorySearch,
    MemorySearchResponse, FeedbackCreate, MemoryStats
)


class MemoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_memory(self, memory_data: MemoryCreate, user_id: int) -> Memory:
        """Create a new memory."""
        db_memory = Memory(
            user_id=user_id,
            content=memory_data.content,
            title=memory_data.title,
            extra_metadata=memory_data.extra_metadata or {},
            tags=memory_data.tags or [],
            importance_score=memory_data.importance_score,
            priority=memory_data.priority,
        )

        self.db.add(db_memory)
        await self.db.commit()
        await self.db.refresh(db_memory)
        return db_memory

    async def get_memory(self, memory_id: int, user_id: int) -> Optional[Memory]:
        """Get a specific memory by ID."""
        result = await self.db.execute(
            select(Memory).where(
                and_(Memory.id == memory_id, Memory.user_id == user_id, Memory.is_deleted == False)
            )
        )
        memory = result.scalars().first()
        if memory:
            # Update last accessed time
            memory.last_accessed = datetime.utcnow()
            await self.db.commit()
        return memory

    async def update_memory(self, memory_id: int, memory_data: MemoryUpdate, user_id: int) -> Optional[Memory]:
        """Update a memory."""
        result = await self.db.execute(
            select(Memory).where(
                and_(Memory.id == memory_id, Memory.user_id == user_id, Memory.is_deleted == False)
            )
        )
        memory = result.scalars().first()

        if not memory:
            return None

        # Update fields
        for field, value in memory_data.dict(exclude_unset=True).items():
            if value is not None:
                setattr(memory, field, value)

        memory.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(memory)
        return memory

    async def delete_memory(self, memory_id: int, user_id: int) -> bool:
        """Soft delete a memory."""
        result = await self.db.execute(
            select(Memory).where(
                and_(Memory.id == memory_id, Memory.user_id == user_id)
            )
        )
        memory = result.scalars().first()

        if not memory:
            return False

        memory.is_deleted = True
        memory.updated_at = datetime.utcnow()
        await self.db.commit()
        return True

    async def search_memories(self, search_params: MemorySearch, user_id: int) -> MemorySearchResponse:
        """Search memories with various filters."""
        query = select(Memory).where(
            and_(Memory.user_id == user_id, Memory.is_deleted == False)
        )

        # Apply filters
        if search_params.tags:
            # Filter by tags (JSON array contains)
            query = query.where(
                func.json_extract(Memory.tags, '$').contains(search_params.tags)
            )

        if search_params.priority:
            query = query.where(Memory.priority == search_params.priority)

        if search_params.min_importance is not None:
            query = query.where(Memory.importance_score >= search_params.min_importance)

        if search_params.cluster_id:
            query = query.where(Memory.cluster_id == search_params.cluster_id)

        # Simple text search in content and title
        if search_params.query:
            search_term = f"%{search_params.query}%"
            query = query.where(
                or_(
                    Memory.content.ilike(search_term),
                    Memory.title.ilike(search_term)
                )
            )

        # Order by importance and recency
        query = query.order_by(desc(Memory.importance_score), desc(Memory.created_at))

        # Apply pagination
        total_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total_count = total_result.scalar()

        query = query.offset(search_params.offset).limit(search_params.limit)
        result = await self.db.execute(query)
        memories = result.scalars().all()

        return MemorySearchResponse(
            memories=memories,
            total_count=total_count,
            search_score=None  # Would be calculated with semantic search
        )

    async def get_user_memories(self, user_id: int, limit: int = 50, offset: int = 0) -> List[Memory]:
        """Get all memories for a user."""
        result = await self.db.execute(
            select(Memory).where(
                and_(Memory.user_id == user_id, Memory.is_deleted == False)
            ).order_by(desc(Memory.created_at)).offset(offset).limit(limit)
        )
        return result.scalars().all()

    async def add_feedback(self, feedback_data: FeedbackCreate, user_id: int) -> Feedback:
        """Add feedback to a memory."""
        # Verify memory ownership
        result = await self.db.execute(
            select(Memory).where(
                and_(Memory.id == feedback_data.memory_id, Memory.user_id == user_id)
            )
        )
        memory = result.scalars().first()
        if not memory:
            raise ValueError("Memory not found or access denied")

        db_feedback = Feedback(
            memory_id=feedback_data.memory_id,
            user_id=user_id,
            feedback_type=feedback_data.feedback_type,
            feedback_value=feedback_data.feedback_value,
            feedback_text=feedback_data.feedback_text,
        )

        self.db.add(db_feedback)
        await self.db.commit()
        await self.db.refresh(db_feedback)
        return db_feedback

    async def get_memory_stats(self, user_id: int) -> MemoryStats:
        """Get memory statistics for a user."""
        # Total memories
        total_result = await self.db.execute(
            select(func.count(Memory.id)).where(
                and_(Memory.user_id == user_id, Memory.is_deleted == False)
            )
        )
        total_memories = total_result.scalar()

        # Active (non-compressed) memories
        active_result = await self.db.execute(
            select(func.count(Memory.id)).where(
                and_(Memory.user_id == user_id, Memory.is_deleted == False, Memory.is_compressed == False)
            )
        )
        active_memories = active_result.scalar()

        # Compressed memories
        compressed_result = await self.db.execute(
            select(func.count(Memory.id)).where(
                and_(Memory.user_id == user_id, Memory.is_deleted == False, Memory.is_compressed == True)
            )
        )
        compressed_memories = compressed_result.scalar()

        # Total clusters
        cluster_result = await self.db.execute(
            select(func.count(func.distinct(Memory.cluster_id))).where(
                and_(Memory.user_id == user_id, Memory.cluster_id.isnot(None))
            )
        )
        total_clusters = cluster_result.scalar()

        # Average importance
        avg_result = await self.db.execute(
            select(func.avg(Memory.importance_score)).where(
                and_(Memory.user_id == user_id, Memory.is_deleted == False)
            )
        )
        average_importance = avg_result.scalar() or 0.0

        # Memories by priority
        priority_result = await self.db.execute(
            select(Memory.priority, func.count(Memory.id)).where(
                and_(Memory.user_id == user_id, Memory.is_deleted == False)
            ).group_by(Memory.priority)
        )
        priorities = priority_result.all()
        memories_by_priority = {priority: count for priority, count in priorities}

        return MemoryStats(
            total_memories=total_memories,
            active_memories=active_memories,
            compressed_memories=compressed_memories,
            total_clusters=total_clusters,
            average_importance=round(average_importance, 2),
            memories_by_priority=memories_by_priority
        )


# Dependency function for getting memory service
async def get_memory_service(db: AsyncSession) -> MemoryService:
    return MemoryService(db)
