from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
from collections import defaultdict

from app.services.vector_service import vector_service
from app.services.gemini_service import gemini_service
from app.models.memory import ContextComposition
from app.config import settings


class ContextComposer:
    """Service for composing and ranking memory contexts based on queries and usage."""

    def __init__(self):
        self.max_composition_size = 20  # Maximum memories in a composition
        self.relevance_decay_factor = 0.8  # How much relevance decays over time

    def compose_context(self, user_id: int, query: str, context_type: str = "search",
                       limit: int = 10) -> ContextComposition:
        """Compose a context from relevant memories based on query."""

        # Generate query embedding
        query_embedding = vector_service.generate_embedding(query)

        # Find semantically similar memories
        semantic_results = vector_service.search_similar(user_id, query_embedding, top_k=50)

        # Get memory data (would fetch from database)
        memories = []  # Would be fetched from DB based on semantic_results

        # Rank and filter memories
        ranked_memories = self._rank_memories(query, memories, semantic_results)

        # Select top memories for composition
        selected_memories = ranked_memories[:limit]
        selected_ids = [mem["id"] for mem in selected_memories]

        # Generate composed content
        composed_content = self._generate_composed_content(query, selected_memories)

        # Calculate ranking scores
        ranking_scores = {mem["id"]: mem["final_score"] for mem in selected_memories}

        # Create composition
        composition = ContextComposition(
            user_id=user_id,
            name=f"Context for: {query[:50]}",
            query=query,
            composition_type=context_type,
            memory_ids=selected_ids,
            composed_content=composed_content,
            ranking_scores=ranking_scores,
            total_memories=len(selected_memories),
            relevance_score=self._calculate_composition_relevance(selected_memories)
        )

        return composition

    def _rank_memories(self, query: str, memories: List[Dict[str, Any]],
                      semantic_results: List[Tuple[int, float]]) -> List[Dict[str, Any]]:
        """Rank memories based on multiple factors."""

        # Create lookup for semantic scores
        semantic_scores = {mem_id: score for mem_id, score in semantic_results}

        ranked_memories = []

        for memory in memories:
            mem_id = memory["id"]

            # Base semantic similarity
            semantic_score = semantic_scores.get(mem_id, 0.0)

            # Text-based relevance (keyword matching)
            text_relevance = self._calculate_text_relevance(query, memory)

            # Usage-based recency boost
            recency_score = self._calculate_recency_score(memory)

            # Tag-based relevance
            tag_relevance = self._calculate_tag_relevance(query, memory)

            # Importance boost
            importance_boost = memory.get("importance_score", 0.5)

            # Feedback-based adjustment
            feedback_adjustment = self._calculate_feedback_adjustment(memory)

            # Combine scores with weights
            final_score = (
                semantic_score * 0.4 +          # 40% semantic similarity
                text_relevance * 0.2 +          # 20% text matching
                recency_score * 0.15 +          # 15% recency
                tag_relevance * 0.1 +           # 10% tag relevance
                importance_boost * 0.1 +        # 10% importance
                feedback_adjustment * 0.05      # 5% feedback adjustment
            )

            memory_copy = memory.copy()
            memory_copy["final_score"] = final_score
            memory_copy["score_breakdown"] = {
                "semantic": semantic_score,
                "text": text_relevance,
                "recency": recency_score,
                "tag": tag_relevance,
                "importance": importance_boost,
                "feedback": feedback_adjustment
            }

            ranked_memories.append(memory_copy)

        # Sort by final score descending
        ranked_memories.sort(key=lambda x: x["final_score"], reverse=True)

        return ranked_memories

    def _calculate_text_relevance(self, query: str, memory: Dict[str, Any]) -> float:
        """Calculate text-based relevance score."""
        query_lower = query.lower()
        content = memory.get("content", "").lower()
        title = memory.get("title", "").lower()

        # Simple keyword matching
        query_words = set(query_lower.split())
        content_words = set(content.split())
        title_words = set(title.split())

        # Calculate overlap
        content_overlap = len(query_words.intersection(content_words))
        title_overlap = len(query_words.intersection(title_words))

        # Normalize
        max_content_words = max(len(content_words), len(query_words))
        max_title_words = max(len(title_words), len(query_words))

        content_score = content_overlap / max_content_words if max_content_words > 0 else 0
        title_score = title_overlap / max_title_words if max_title_words > 0 else 0

        # Title matches are more important
        return min(1.0, content_score * 0.7 + title_score * 0.3)

    def _calculate_recency_score(self, memory: Dict[str, Any]) -> float:
        """Calculate recency score based on last access and creation time."""
        now = datetime.now()

        # Last accessed time
        last_accessed = memory.get("last_accessed")
        if last_accessed:
            if isinstance(last_accessed, str):
                last_accessed = datetime.fromisoformat(last_accessed.replace('Z', '+00:00'))
            days_since_access = (now - last_accessed).days
            access_score = max(0, 1.0 - (days_since_access / 30.0))  # Decay over 30 days
        else:
            access_score = 0.5

        # Creation time (older memories get slightly lower score)
        created_at = memory.get("created_at")
        if created_at:
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            days_since_creation = (now - created_at).days
            creation_score = max(0, 1.0 - (days_since_creation / 365.0))  # Decay over a year
        else:
            creation_score = 0.5

        return (access_score * 0.7 + creation_score * 0.3)

    def _calculate_tag_relevance(self, query: str, memory: Dict[str, Any]) -> float:
        """Calculate relevance based on tag matching."""
        query_lower = query.lower()
        tags = memory.get("tags", [])

        if not tags:
            return 0.0

        # Check if query contains tag words or vice versa
        query_words = set(query_lower.split())
        tag_words = set(tag.lower() for tag in tags)

        overlap = len(query_words.intersection(tag_words))
        union = len(query_words.union(tag_words))

        return overlap / union if union > 0 else 0.0

    def _calculate_feedback_adjustment(self, memory: Dict[str, Any]) -> float:
        """Calculate adjustment based on user feedback."""
        # This would analyze feedback data
        # Positive feedback increases score, negative decreases
        feedback_score = memory.get("feedback_score", 0.0)  # Would be calculated from feedback table

        # Normalize to -0.5 to +0.5 range
        return max(-0.5, min(0.5, feedback_score))

    def _generate_composed_content(self, query: str, memories: List[Dict[str, Any]]) -> str:
        """Generate composed content from selected memories."""
        if not memories:
            return "No relevant memories found."

        if len(memories) == 1:
            return memories[0].get("content", "")

        # Use Gemini to compose if available
        if gemini_service.model:
            memory_texts = [mem.get("content", "")[:300] for mem in memories[:5]]

            prompt = f"""
            Compose a coherent response to the query using the following memory excerpts.
            Organize the information logically and eliminate redundancy.

            Query: {query}

            Memory excerpts: {memory_texts}

            Provide a well-structured response that answers the query comprehensively.
            """

            try:
                response = gemini_service.model.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                print(f"Composition generation failed: {e}")

        # Fallback: simple concatenation with summaries
        summaries = [mem.get("summary", mem.get("content", "")[:200]) for mem in memories]
        return " ".join(summaries)

    def _calculate_composition_relevance(self, memories: List[Dict[str, Any]]) -> float:
        """Calculate overall relevance score for the composition."""
        if not memories:
            return 0.0

        scores = [mem.get("final_score", 0.0) for mem in memories]
        return float(np.mean(scores))

    def get_recommendations(self, user_id: int, context: str = "general",
                           limit: int = 5) -> List[Dict[str, Any]]:
        """Get recommended memories based on usage patterns."""
        # This would analyze usage patterns and recommend memories
        # For now, return empty list
        return []

    def restructure_for_purpose(self, memories: List[Dict[str, Any]],
                               purpose: str) -> Dict[str, Any]:
        """Restructure memories for a specific purpose (learning, decision-making, etc.)."""
        if not memories:
            return {"restructured_content": "", "structure": []}

        # Use Gemini to restructure for purpose
        memory_content = "\n".join([mem.get("content", "") for mem in memories])

        prompt = f"""
        Restructure the following memories for {purpose}.
        Organize them in a way that best serves this purpose.

        Memories: {memory_content[:2000]}

        Provide restructured content and explain the organization.
        """

        if gemini_service.model:
            try:
                response = gemini_service.model.generate_content(prompt)
                return {
                    "restructured_content": response.text.strip(),
                    "purpose": purpose,
                    "original_memories": len(memories)
                }
            except Exception as e:
                pass

        # Fallback
        return {
            "restructured_content": memory_content,
            "purpose": purpose,
            "original_memories": len(memories)
        }

    def optimize_composition(self, composition: ContextComposition,
                           feedback: Dict[str, Any]) -> ContextComposition:
        """Optimize composition based on feedback."""
        # Analyze feedback and adjust future compositions
        # This would update ranking weights, etc.

        return composition


# Global context composer instance
context_composer = ContextComposer()
