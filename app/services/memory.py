from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_, desc, func
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import json
import uuid

from app.models.memory import (
    Memory, Feedback, MemoryChunk, EpisodicCluster,
    ContextComposition, memory_relationships
)
from app.schemas.memory import (
    MemoryCreate, MemoryUpdate, MemorySearch,
    MemorySearchResponse, FeedbackCreate, MemoryStats
)
from app.services.vector_service import vector_service
from app.services.gemini_service import gemini_service
from app.services.episodic_linker import episodic_linker
from app.services.context_composer import context_composer


class MemoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_memory(self, memory_data: MemoryCreate, user_id: int) -> Memory:
        """Create a new memory with full processing pipeline."""
        # Step 1: Restructure content using Gemini
        restructured_data = gemini_service.restructure_content(
            memory_data.content,
            context=memory_data.title
        )

        # Extract metadata from restructuring
        chunks_data = restructured_data.get("chunks", [])
        suggested_tags = restructured_data.get("suggested_tags", [])
        key_concepts = restructured_data.get("key_concepts", [])

        # Combine user tags with suggested tags
        all_tags = list(set((memory_data.tags or []) + suggested_tags))

        # Generate summary
        summary = gemini_service.generate_memory_summary(
            memory_data.content,
            chunks_data
        )

        # Step 2: Generate embedding for the full content
        content_embedding = vector_service.generate_embedding(memory_data.content)

        # Step 3: Create memory record
        db_memory = Memory(
            user_id=user_id,
            content=memory_data.content,
            title=memory_data.title or restructured_data.get("title", ""),
            summary=summary,
            extra_metadata={
                **(memory_data.extra_metadata or {}),
                "key_concepts": key_concepts,
                "episodic_markers": restructured_data.get("episodic_markers", []),
                "restructured_data": restructured_data
            },
            tags=all_tags,
            importance_score=memory_data.importance_score or 0.5,
            priority=memory_data.priority or "medium",
            embedding=content_embedding,
            cluster_id=None  # Will be set by episodic linker
        )

        self.db.add(db_memory)
        await self.db.flush()  # Get the memory ID without committing

        # Step 4: Create memory chunks
        await self._create_memory_chunks(db_memory.id, user_id, chunks_data)

        # Step 5: Find similar memories and create relationships
        similar_memories = episodic_linker.find_similar_memories(
            user_id, content_embedding, exclude_ids={db_memory.id}
        )

        if similar_memories:
            relationships = episodic_linker.create_memory_relationships(
                user_id, db_memory.id, similar_memories
            )
            await self._create_memory_relationships(relationships)

        # Step 6: Check for episodic clustering
        cluster_id = await self._find_or_create_episodic_cluster(
            user_id, db_memory, similar_memories
        )
        if cluster_id:
            db_memory.cluster_id = cluster_id

        # Step 7: Add to vector database
        vector_service.add_memory_embedding(user_id, db_memory.id, content_embedding)

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

    # Helper methods for enhanced memory processing

    async def _create_memory_chunks(self, memory_id: int, user_id: int, chunks_data: List[Dict[str, Any]]):
        """Create memory chunks from restructured data."""
        for i, chunk_data in enumerate(chunks_data):
            # Generate embedding for chunk
            chunk_embedding = vector_service.generate_embedding(chunk_data.get("content", ""))

            chunk = MemoryChunk(
                memory_id=memory_id,
                user_id=user_id,
                content=chunk_data.get("content", ""),
                chunk_index=i,
                chunk_type=chunk_data.get("type", "text"),
                embedding=chunk_embedding,
                token_count=len(chunk_data.get("content", "").split()),
                importance_score=chunk_data.get("importance", 0.5)
            )

            self.db.add(chunk)

    async def _create_memory_relationships(self, relationships: List[Dict[str, Any]]):
        """Create relationships between memories in the database."""
        for rel in relationships:
            # Insert into association table
            await self.db.execute(
                memory_relationships.insert().values(
                    memory_id=rel["memory_id"],
                    related_memory_id=rel["related_memory_id"],
                    relationship_type=rel["relationship_type"],
                    strength=rel["strength"]
                )
            )

    async def _find_or_create_episodic_cluster(self, user_id: int, memory: Memory,
                                             similar_memories: List[Tuple[int, float]]) -> Optional[str]:
        """Find existing cluster or create new one for episodic memory."""
        # Check temporal proximity (memories created within 24 hours)
        recent_memories_result = await self.db.execute(
            select(Memory).where(
                and_(
                    Memory.user_id == user_id,
                    Memory.created_at >= memory.created_at - timedelta(hours=24),
                    Memory.created_at <= memory.created_at + timedelta(hours=24),
                    Memory.id != memory.id
                )
            ).order_by(desc(Memory.created_at)).limit(10)
        )

        recent_memories = recent_memories_result.scalars().all()

        if len(recent_memories) >= 2:  # Need at least 2 memories for a cluster
            # Check semantic similarity
            memory_ids = [mem.id for mem in recent_memories] + [memory.id]
            cluster = episodic_linker.create_episodic_cluster(user_id, memory_ids)
            self.db.add(cluster)
            return cluster.id

        return None

    async def search_memories_enhanced(self, search_params: MemorySearch, user_id: int) -> MemorySearchResponse:
        """Enhanced search using vector similarity and context composition."""
        # If semantic search is requested
        if search_params.semantic_search and search_params.query:
            # Use context composer for enhanced search
            composition = context_composer.compose_context(
                user_id, search_params.query, "search", search_params.limit or 10
            )

            # Get memories by IDs
            memory_ids = composition.memory_ids
            if memory_ids:
                result = await self.db.execute(
                    select(Memory).where(
                        and_(Memory.id.in_(memory_ids), Memory.user_id == user_id)
                    )
                )
                memories = result.scalars().all()

                # Sort by composition ranking
                memory_order = {mem_id: i for i, mem_id in enumerate(memory_ids)}
                memories.sort(key=lambda m: memory_order.get(m.id, 999))

                return MemorySearchResponse(
                    memories=memories,
                    total_count=len(memories),
                    search_score=composition.relevance_score
                )

        # Fall back to original search
        return await self.search_memories(search_params, user_id)


# Dependency function for getting memory service
async def get_memory_service(db: AsyncSession) -> MemoryService:
    return MemoryService(db)
