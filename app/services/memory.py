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
    """
    Enhanced memory service with intelligent clustering and optimization.

    New Features:
    - Smart clustering: Merges similar memories into single clusters
    - Memory deduplication: Removes near-duplicate memories to save space
    - Cluster consolidation: Merges similar clusters automatically
    - Relationship enhancement: Strengthens connections based on usage patterns
    """

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
        if restructured_data.success and restructured_data.data:
            chunks_data = restructured_data.data.chunks
            suggested_tags = restructured_data.data.suggested_tags
            key_concepts = restructured_data.data.key_concepts
            episodic_markers = restructured_data.data.episodic_markers
            summary = restructured_data.data.summary
        else:
            # Fallback if restructuring failed
            chunks_data = []
            suggested_tags = []
            key_concepts = []
            episodic_markers = []
            summary = memory_data.content[:200] + "..." if len(memory_data.content) > 200 else memory_data.content

        # Combine user tags with suggested tags
        all_tags = list(set((memory_data.tags or []) + suggested_tags))

        # Step 2: Generate embedding for the full content
        content_embedding = vector_service.generate_embedding(memory_data.content)

        # Step 3: Create memory record
        db_memory = Memory(
            user_id=user_id,
            content=memory_data.content,
            title=memory_data.title,
            summary=summary,
            extra_metadata={
                **(memory_data.extra_metadata or {}),
                "key_concepts": key_concepts,
                "episodic_markers": episodic_markers,
                "restructured_data": restructured_data.dict() if restructured_data.success else {}
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

    async def _create_memory_chunks(self, memory_id: int, user_id: int, chunks_data):
        """Create memory chunks from restructured data."""
        # Handle both Pydantic objects and dictionaries for backward compatibility
        for i, chunk_data in enumerate(chunks_data):
            if hasattr(chunk_data, 'content'):  # Pydantic object
                content = chunk_data.content
                chunk_type = chunk_data.type
                importance = chunk_data.importance
            else:  # Dictionary (fallback)
                content = chunk_data.get("content", "")
                chunk_type = chunk_data.get("type", "text")
                importance = chunk_data.get("importance", 0.5)

            # Generate embedding for chunk
            chunk_embedding = vector_service.generate_embedding(content)

            chunk = MemoryChunk(
                memory_id=memory_id,
                user_id=user_id,
                content=content,
                chunk_index=i,
                chunk_type=chunk_type,
                embedding=chunk_embedding,
                token_count=len(content.split()),
                importance_score=importance
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
        from app.models.memory import EpisodicCluster

        # First, try to find an existing cluster that this memory should join
        existing_cluster_id = await self._find_existing_cluster_for_memory(user_id, memory, similar_memories)
        if existing_cluster_id:
            # Update the existing cluster with this new memory
            await self._add_memory_to_cluster(existing_cluster_id, memory.id, user_id)
            return existing_cluster_id

        # If no suitable existing cluster, check for temporal clustering
        recent_memories_result = await self.db.execute(
            select(Memory).where(
                and_(
                    Memory.user_id == user_id,
                    Memory.created_at >= memory.created_at - timedelta(hours=24),
                    Memory.created_at <= memory.created_at + timedelta(hours=24),
                    Memory.id != memory.id,
                    Memory.cluster_id.is_(None)  # Only cluster unclustered memories
                )
            ).order_by(desc(Memory.created_at)).limit(5)  # Reduced limit for tighter clustering
        )

        recent_memories = recent_memories_result.scalars().all()

        # Need at least 2 similar recent memories for a new cluster
        if len(recent_memories) >= 2:
            # Calculate semantic similarity among recent memories
            memory_ids = [mem.id for mem in recent_memories] + [memory.id]

            # Check if these memories are semantically related
            if await self._are_memories_related(user_id, memory_ids):
                cluster = episodic_linker.create_episodic_cluster(user_id, memory_ids)
                self.db.add(cluster)
                return cluster.id

        return None

    async def _find_existing_cluster_for_memory(self, user_id: int, memory: Memory,
                                              similar_memories: List[Tuple[int, float]]) -> Optional[str]:
        """Find an existing cluster that this memory should join."""
        from app.models.memory import EpisodicCluster

        if not similar_memories:
            return None

        # Get clusters of similar memories
        similar_memory_ids = [mem_id for mem_id, _ in similar_memories[:5]]  # Top 5 similar

        # Get all active clusters for the user (we'll filter in Python due to JSON column)
        cluster_result = await self.db.execute(
            select(EpisodicCluster).where(
                EpisodicCluster.user_id == user_id
            ).order_by(desc(EpisodicCluster.importance_score)).limit(10)  # Get more to filter
        )

        all_clusters = cluster_result.scalars().all()

        # Filter clusters that have overlapping key memories
        candidate_clusters = []
        for cluster in all_clusters:
            cluster_memories = cluster.key_memories or []
            if any(mem_id in cluster_memories for mem_id in similar_memory_ids):
                candidate_clusters.append(cluster)
                if len(candidate_clusters) >= 3:  # Limit to top 3
                    break

        # Find best cluster based on:
        # 1. Number of overlapping similar memories
        # 2. Temporal proximity
        # 3. Cluster size (prefer smaller clusters for tighter grouping)
        best_cluster = None
        best_score = 0

        for cluster in candidate_clusters:
            overlap_count = len(set(cluster.key_memories or []) & set(similar_memory_ids))
            temporal_score = 1.0 if cluster.start_date and abs((cluster.start_date - memory.created_at).days) <= 7 else 0.5
            size_score = max(0.1, 1.0 - (len(cluster.key_memories or []) / 50))  # Prefer smaller clusters

            total_score = overlap_count * temporal_score * size_score

            if total_score > best_score and overlap_count >= 1:
                best_score = total_score
                best_cluster = cluster

        return best_cluster.id if best_cluster else None

    async def _add_memory_to_cluster(self, cluster_id: str, memory_id: int, user_id: int):
        """Add a memory to an existing cluster and update cluster properties."""
        from app.models.memory import EpisodicCluster

        # Update memory's cluster_id
        update_stmt = (
            Memory.__table__.update()
            .where(and_(Memory.id == memory_id, Memory.user_id == user_id))
            .values(cluster_id=cluster_id)
        )
        await self.db.execute(update_stmt)

        # Get cluster and update its properties
        cluster_result = await self.db.execute(
            select(EpisodicCluster).where(EpisodicCluster.id == cluster_id)
        )
        cluster = cluster_result.scalars().first()

        if cluster:
            # Add memory to key_memories if not already there
            key_memories = cluster.key_memories or []
            if memory_id not in key_memories:
                key_memories.append(memory_id)
                cluster.key_memories = key_memories[:20]  # Keep top 20

            # Update temporal bounds
            memory_result = await self.db.execute(select(Memory).where(Memory.id == memory_id))
            memory_obj = memory_result.scalars().first()

            if memory_obj:
                if not cluster.start_date or memory_obj.created_at < cluster.start_date:
                    cluster.start_date = memory_obj.created_at
                if not cluster.end_date or memory_obj.created_at > cluster.end_date:
                    cluster.end_date = memory_obj.created_at

                # Recalculate duration
                if cluster.start_date and cluster.end_date:
                    cluster.duration_minutes = int((cluster.end_date - cluster.start_date).total_seconds() / 60)

    async def _are_memories_related(self, user_id: int, memory_ids: List[int]) -> bool:
        """Check if a group of memories are semantically related."""
        if len(memory_ids) < 2:
            return False

        # Get memory embeddings and calculate pairwise similarities
        embeddings = {}
        for mem_id in memory_ids:
            mem_result = await self.db.execute(
                select(Memory.embedding).where(
                    and_(Memory.id == mem_id, Memory.user_id == user_id)
                )
            )
            embedding = mem_result.scalars().first()
            if embedding:
                embeddings[mem_id] = embedding

        if len(embeddings) < 2:
            return False

        # Calculate average similarity
        similarities = []
        mem_id_list = list(embeddings.keys())

        for i in range(len(mem_id_list)):
            for j in range(i + 1, len(mem_id_list)):
                sim = vector_service.calculate_similarity(
                    embeddings[mem_id_list[i]],
                    embeddings[mem_id_list[j]]
                )
                similarities.append(sim)

        avg_similarity = sum(similarities) / len(similarities) if similarities else 0

        # Consider related if average similarity is above threshold
        return avg_similarity >= 0.65

    async def consolidate_similar_clusters(self, user_id: int) -> Dict[str, int]:
        """Consolidate similar clusters to reduce redundancy."""
        from app.models.memory import EpisodicCluster

        # Get all active clusters for user
        clusters_result = await self.db.execute(
            select(EpisodicCluster).where(EpisodicCluster.user_id == user_id)
        )
        clusters = clusters_result.scalars().all()

        consolidation_stats = {
            "merged_clusters": 0,
            "deleted_clusters": 0,
            "updated_memories": 0
        }

        # Group clusters by semantic similarity
        processed_clusters = set()

        for i, cluster1 in enumerate(clusters):
            if cluster1.id in processed_clusters:
                continue

            for j, cluster2 in enumerate(clusters[i+1:], i+1):
                if cluster2.id in processed_clusters:
                    continue

                # Check if clusters should be merged
                if (cluster1.centroid_embedding and cluster2.centroid_embedding and
                    episodic_linker.should_merge_clusters(
                        cluster1.centroid_embedding,
                        cluster2.centroid_embedding,
                        len(cluster1.key_memories or []),
                        len(cluster2.key_memories or [])
                    )):

                    # Merge cluster2 into cluster1
                    await self._merge_clusters(cluster1.id, cluster2.id, user_id)
                    processed_clusters.add(cluster2.id)

                    consolidation_stats["merged_clusters"] += 1
                    consolidation_stats["deleted_clusters"] += 1

            processed_clusters.add(cluster1.id)

        return consolidation_stats

    async def _merge_clusters(self, target_cluster_id: str, source_cluster_id: str, user_id: int):
        """Merge source cluster into target cluster."""
        from app.models.memory import EpisodicCluster

        # Move all memories from source to target cluster
        update_stmt = (
            Memory.__table__.update()
            .where(and_(Memory.cluster_id == source_cluster_id, Memory.user_id == user_id))
            .values(cluster_id=target_cluster_id)
        )
        result = await self.db.execute(update_stmt)
        memories_moved = result.rowcount

        # Update target cluster properties
        target_result = await self.db.execute(
            select(EpisodicCluster).where(EpisodicCluster.id == target_cluster_id)
        )
        target_cluster = target_result.scalars().first()

        source_result = await self.db.execute(
            select(EpisodicCluster).where(EpisodicCluster.id == source_cluster_id)
        )
        source_cluster = source_result.scalars().first()

        if target_cluster and source_cluster:
            # Merge key memories
            target_memories = set(target_cluster.key_memories or [])
            source_memories = set(source_cluster.key_memories or [])
            merged_memories = list(target_memories | source_memories)[:25]  # Keep top 25
            target_cluster.key_memories = merged_memories

            # Update temporal bounds
            if source_cluster.start_date and (not target_cluster.start_date or source_cluster.start_date < target_cluster.start_date):
                target_cluster.start_date = source_cluster.start_date
            if source_cluster.end_date and (not target_cluster.end_date or source_cluster.end_date > target_cluster.end_date):
                target_cluster.end_date = source_cluster.end_date

            # Recalculate duration and importance
            if target_cluster.start_date and target_cluster.end_date:
                target_cluster.duration_minutes = int((target_cluster.end_date - target_cluster.start_date).total_seconds() / 60)

            # Recalculate centroid (simplified - would need all memory embeddings)
            target_cluster.importance_score = (target_cluster.importance_score + source_cluster.importance_score) / 2

        # Delete source cluster
        await self.db.execute(
            EpisodicCluster.__table__.delete().where(EpisodicCluster.id == source_cluster_id)
        )

        await self.db.commit()

    async def deduplicate_similar_memories(self, user_id: int, similarity_threshold: float = 0.9) -> Dict[str, int]:
        """Find and merge nearly identical memories to reduce redundancy."""
        deduplication_stats = {
            "duplicate_pairs_found": 0,
            "memories_merged": 0,
            "space_saved_bytes": 0
        }

        # Get all memories for user
        memories_result = await self.db.execute(
            select(Memory).where(
                and_(Memory.user_id == user_id, Memory.is_deleted == False)
            ).order_by(Memory.created_at)
        )
        all_memories = memories_result.scalars().all()

        processed_ids = set()

        for memory in all_memories:
            if memory.id in processed_ids:
                continue

            # Find very similar memories
            similar_memories = episodic_linker.find_similar_memories(
                user_id, memory.embedding, exclude_ids=processed_ids
            )

            # Filter for near-duplicates
            near_duplicates = [
                (mem_id, score) for mem_id, score in similar_memories
                if score >= similarity_threshold
            ]

            if near_duplicates:
                # Merge duplicates into this memory
                merged_ids = []
                for dup_id, _ in near_duplicates:
                    merged_ids.append(dup_id)
                    processed_ids.add(dup_id)

                if merged_ids:
                    await self._merge_duplicate_memories(memory.id, merged_ids, user_id)
                    deduplication_stats["duplicate_pairs_found"] += len(merged_ids)
                    deduplication_stats["memories_merged"] += len(merged_ids)

            processed_ids.add(memory.id)

        return deduplication_stats

    async def _merge_duplicate_memories(self, target_memory_id: int, duplicate_ids: List[int], user_id: int):
        """Merge duplicate memories into a target memory."""
        # Get target memory
        target_result = await self.db.execute(
            select(Memory).where(and_(Memory.id == target_memory_id, Memory.user_id == user_id))
        )
        target_memory = target_result.scalars().first()

        if not target_memory:
            return

        # Get duplicate memories
        duplicates_result = await self.db.execute(
            select(Memory).where(
                and_(Memory.id.in_(duplicate_ids), Memory.user_id == user_id)
            )
        )
        duplicate_memories = duplicates_result.scalars().all()

        # Merge content and metadata
        all_contents = [target_memory.content] + [mem.content for mem in duplicate_memories]
        all_summaries = [target_memory.summary or ""] + [mem.summary or "" for mem in duplicate_memories]
        all_tags = (target_memory.tags or []) + [tag for mem in duplicate_memories for tag in (mem.tags or [])]
        all_importance_scores = [target_memory.importance_score] + [mem.importance_score for mem in duplicate_memories]

        # Create merged content using Gemini
        merged_content = await self._create_merged_memory_content(all_contents, target_memory.title)

        # Update target memory
        target_memory.content = merged_content
        target_memory.summary = f"Merged memory from {len(duplicate_ids) + 1} similar memories"
        target_memory.tags = list(set(all_tags))  # Remove duplicates
        target_memory.importance_score = max(all_importance_scores)  # Keep highest importance
        target_memory.last_accessed = max([target_memory.last_accessed] + [mem.last_accessed for mem in duplicate_memories])

        # Generate new embedding for merged content
        new_embedding = vector_service.generate_embedding(merged_content)
        target_memory.embedding = new_embedding

        # Update extra metadata
        extra_metadata = target_memory.extra_metadata or {}
        extra_metadata["merged_from"] = duplicate_ids
        extra_metadata["merge_timestamp"] = datetime.utcnow().isoformat()
        target_memory.extra_metadata = extra_metadata

        # Mark duplicates as deleted
        for dup_id in duplicate_ids:
            update_stmt = (
                Memory.__table__.update()
                .where(and_(Memory.id == dup_id, Memory.user_id == user_id))
                .values(is_deleted=True)
            )
            await self.db.execute(update_stmt)

        await self.db.commit()

    async def _create_merged_memory_content(self, contents: List[str], title: Optional[str] = None) -> str:
        """Create merged content from multiple similar memories."""
        if len(contents) <= 1:
            return contents[0] if contents else ""

        # Prepare the separator string outside the f-string to avoid backslash issues
        separator = "\n\n---\n\n"
        merged_contents = separator.join(contents)

        # Use Gemini to intelligently merge the contents
        merge_prompt = f"""
        Merge the following similar memory contents into a single, coherent memory.
        Remove redundancy while preserving all unique and important details.

        Title: {title or "Merged Memory"}

        Contents to merge:
        {merged_contents}

        Provide a single, well-structured merged memory content.
        """

        try:
            response = gemini_service.model.generate_content(merge_prompt)
            return response.text.strip()
        except Exception as e:
            # Fallback: concatenate with deduplication
            print(f"Merge failed: {e}")
            return " | ".join(contents)

    async def optimize_memory_storage(self, user_id: int) -> Dict[str, Any]:
        """Run comprehensive memory optimization including clustering and deduplication."""
        optimization_results = {
            "timestamp": datetime.utcnow().isoformat(),
            "clustering": await self.consolidate_similar_clusters(user_id),
            "deduplication": await self.deduplicate_similar_memories(user_id),
            "total_space_saved": 0,
            "clusters_optimized": 0
        }

        # Calculate approximate space saved
        space_saved = (
            optimization_results["clustering"]["deleted_clusters"] * 1024 +  # ~1KB per cluster metadata
            optimization_results["deduplication"]["memories_merged"] * 2048   # ~2KB per merged memory
        )
        optimization_results["total_space_saved"] = space_saved

        return optimization_results

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


# Periodic optimization task
async def run_memory_optimization(db: AsyncSession, user_id: int) -> Dict[str, Any]:
    """Run periodic memory optimization for a user."""
    service = MemoryService(db)
    return await service.optimize_memory_storage(user_id)

# Dependency function for getting memory service
async def get_memory_service(db: AsyncSession) -> MemoryService:
    return MemoryService(db)
