from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import json
import logging

from app.services.gemini_service import gemini_service
from app.models.gemini_models import ImprovementSuggestions
from app.services.vector_service import vector_service
from app.services.context_composer import context_composer
from app.models.memory import Feedback, Memory
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, select, func, desc

logger = logging.getLogger(__name__)


class FeedbackLoop:
    """Service for processing feedback and improving memory retrieval."""

    def __init__(self):
        self.feedback_window_days = 30  # Analyze feedback over last 30 days
        self.min_feedback_threshold = 3  # Minimum feedback items to trigger analysis

    async def process_feedback(self, db: AsyncSession, feedback: Feedback) -> Dict[str, Any]:
        """Process new feedback and potentially trigger improvements."""

        improvements = {
            "memory_adjustments": [],
            "new_chunks_created": [],
            "relationship_updates": [],
            "retraining_suggestions": []
        }

        # Check if we have enough feedback for this memory to analyze
        memory_feedback = await self._get_memory_feedback(db, feedback.memory_id)

        if len(memory_feedback) >= self.min_feedback_threshold:
            # Analyze feedback patterns
            feedback_analysis = await self._analyze_feedback_patterns(memory_feedback)

            if feedback_analysis.get("needs_improvement"):
                # Generate improvement suggestions
                suggestions_response = gemini_service.suggest_improvements(memory_feedback)
                suggestions = suggestions_response.data if suggestions_response.success else None

                if suggestions:
                    # Implement improvements
                    improvements = await self._implement_improvements(
                        db, feedback.memory_id, suggestions
                    )

        # Update memory feedback score
        await self._update_memory_feedback_score(db, feedback.memory_id)

        return improvements

    async def _get_memory_feedback(self, db: AsyncSession, memory_id: int) -> List[Dict[str, Any]]:
        """Get all feedback for a memory."""
        result = await db.execute(
            select(Feedback).where(Feedback.memory_id == memory_id)
        )
        feedback_items = result.scalars().all()

        return [
            {
                "type": f.feedback_type,
                "value": f.feedback_value,
                "text": f.feedback_text,
                "created_at": f.created_at.isoformat()
            }
            for f in feedback_items
        ]

    async def _analyze_feedback_patterns(self, feedback_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze feedback patterns to identify issues."""

        analysis = {
            "needs_improvement": False,
            "average_rating": 0.0,
            "common_issues": [],
            "positive_aspects": [],
            "missing_context_count": 0,
            "relevance_issues": 0
        }

        if not feedback_list:
            return analysis

        # Calculate average rating
        ratings = [f.get("value", 0) for f in feedback_list if f.get("value") is not None]
        if ratings:
            analysis["average_rating"] = sum(ratings) / len(ratings)

        # Analyze text feedback for common patterns
        text_feedback = [f.get("text", "") for f in feedback_list if f.get("text")]

        missing_context_indicators = ["missing", "forgot", "should include", "context"]
        relevance_indicators = ["irrelevant", "not relevant", "wrong", "incorrect"]

        for text in text_feedback:
            text_lower = text.lower()

            # Check for missing context
            if any(indicator in text_lower for indicator in missing_context_indicators):
                analysis["missing_context_count"] += 1

            # Check for relevance issues
            if any(indicator in text_lower for indicator in relevance_indicators):
                analysis["relevance_issues"] += 1

        # Determine if improvement is needed
        low_rating_threshold = 0.6
        high_issue_threshold = len(feedback_list) * 0.3  # 30% of feedback mentions issues

        analysis["needs_improvement"] = (
            analysis["average_rating"] < low_rating_threshold or
            analysis["missing_context_count"] > high_issue_threshold or
            analysis["relevance_issues"] > high_issue_threshold
        )

        return analysis

    async def _implement_improvements(self, db: AsyncSession, memory_id: int,
                                    suggestions: ImprovementSuggestions) -> Dict[str, Any]:
        """Implement improvements based on feedback analysis."""

        improvements = {
            "memory_adjustments": [],
            "new_chunks_created": [],
            "relationship_updates": [],
            "retraining_suggestions": []
        }

        # Get the memory
        result = await db.execute(select(Memory).where(Memory.id == memory_id))
        memory = result.scalars().first()

        if not memory:
            return improvements

        # Create new chunks for missing context
        missing_context = suggestions.missing_context
        if missing_context:
            new_chunks = await self._create_missing_context_chunks(
                db, memory, missing_context
            )
            improvements["new_chunks_created"] = new_chunks

        # Update relationships
        relationship_updates = suggestions.relationship_updates
        if relationship_updates:
            updates = await self._update_relationships(db, memory_id, relationship_updates)
            improvements["relationship_updates"] = updates

        # Adjust memory metadata
        if suggestions.improvement_suggestions:
            adjustments = await self._adjust_memory_metadata(db, memory, suggestions)
            improvements["memory_adjustments"] = adjustments

        return improvements

    async def _create_missing_context_chunks(self, db: AsyncSession, memory: Memory,
                                           missing_context: List[str]) -> List[Dict[str, Any]]:
        """Create new chunks for missing context."""

        created_chunks = []

        for context_item in missing_context[:3]:  # Limit to 3 new chunks
            # Generate content for missing context using Gemini
            prompt = f"""
            Generate additional context for a memory based on this missing information:
            Original memory: {memory.content[:500]}

            Missing context: {context_item}

            Provide a brief, relevant addition that fills this contextual gap.
            """

            if gemini_service.model:
                try:
                    response = gemini_service.model.generate_content(prompt)
                    new_content = response.text.strip()

                    # Create new chunk
                    from app.models.memory import MemoryChunk
                    chunk_embedding = vector_service.generate_embedding(new_content)

                    new_chunk = MemoryChunk(
                        memory_id=memory.id,
                        user_id=memory.user_id,
                        content=new_content,
                        chunk_index=999,  # Special index for feedback-generated chunks
                        chunk_type="feedback_supplement",
                        embedding=chunk_embedding,
                        token_count=len(new_content.split()),
                        importance_score=0.7  # Higher importance for feedback-driven content
                    )

                    db.add(new_chunk)
                    created_chunks.append({
                        "content": new_content,
                        "type": "feedback_supplement",
                        "reason": context_item
                    })

                except Exception as e:
                    logger.error("Failed to create context chunk", extra={"error": str(e)}, exc_info=True)

        return created_chunks

    async def _update_relationships(self, db: AsyncSession, memory_id: int,
                                  relationship_updates: List[str]) -> List[str]:
        """Update memory relationships based on feedback."""
        # This would analyze and update the memory_relationships table
        # For now, just return the suggestions
        return relationship_updates

    async def _adjust_memory_metadata(self, db: AsyncSession, memory: Memory,
                                    suggestions: ImprovementSuggestions) -> List[str]:
        """Adjust memory metadata based on feedback."""

        adjustments = []

        # Update importance score if feedback indicates it's more/less important
        avg_feedback = await self._calculate_average_feedback_score(db, memory.id)
        if avg_feedback < 0.5:
            memory.importance_score = max(0.1, memory.importance_score * 0.8)
            adjustments.append("decreased_importance")
        elif avg_feedback > 0.8:
            memory.importance_score = min(1.0, memory.importance_score * 1.2)
            adjustments.append("increased_importance")

        # Update tags if suggestions include new tags
        new_tags = suggestions.get("suggested_tags", [])
        if new_tags:
            current_tags = set(memory.tags or [])
            current_tags.update(new_tags)
            memory.tags = list(current_tags)
            adjustments.append(f"added_tags: {', '.join(new_tags)}")

        return adjustments

    async def _calculate_average_feedback_score(self, db: AsyncSession, memory_id: int) -> float:
        """Calculate average feedback score for a memory."""
        result = await db.execute(
            select(func.avg(Feedback.feedback_value)).where(
                and_(Feedback.memory_id == memory_id, Feedback.feedback_value.isnot(None))
            )
        )
        avg_score = result.scalar()
        return avg_score or 0.5

    async def _update_memory_feedback_score(self, db: AsyncSession, memory_id: int):
        """Update the cached feedback score on the memory."""
        avg_score = await self._calculate_average_feedback_score(db, memory_id)

        # This would update a feedback_score field on the Memory model
        # For now, we'll store it in extra_metadata
        result = await db.execute(select(Memory).where(Memory.id == memory_id))
        memory = result.scalars().first()

        if memory:
            metadata = memory.extra_metadata or {}
            metadata["feedback_score"] = avg_score
            memory.extra_metadata = metadata

    async def get_feedback_insights(self, db: AsyncSession, user_id: int,
                                  time_period_days: int = 30) -> Dict[str, Any]:
        """Get insights from user feedback over a time period."""

        since_date = datetime.now() - timedelta(days=time_period_days)

        # Get feedback with memory info
        result = await db.execute(
            select(Feedback, Memory.content, Memory.title).join(Memory).where(
                and_(
                    Feedback.user_id == user_id,
                    Feedback.created_at >= since_date
                )
            ).order_by(desc(Feedback.created_at))
        )

        feedback_data = result.all()

        insights = {
            "total_feedback": len(feedback_data),
            "average_rating": 0.0,
            "common_themes": [],
            "improvement_areas": [],
            "positive_trends": []
        }

        if feedback_data:
            # Calculate average rating
            ratings = [f.Feedback.feedback_value for f in feedback_data if f.Feedback.feedback_value]
            if ratings:
                insights["average_rating"] = sum(ratings) / len(ratings)

            # Analyze common themes in feedback text
            feedback_texts = [f.Feedback.feedback_text for f in feedback_data if f.Feedback.feedback_text]
            insights["common_themes"] = self._extract_common_themes(feedback_texts)

        return insights

    def _extract_common_themes(self, feedback_texts: List[str]) -> List[str]:
        """Extract common themes from feedback texts."""
        # Simple keyword-based theme extraction
        themes = defaultdict(int)

        theme_keywords = {
            "missing_context": ["missing", "forgot", "context", "additional"],
            "irrelevant": ["irrelevant", "wrong", "incorrect", "not useful"],
            "incomplete": ["incomplete", "partial", "cut off"],
            "timing": ["time", "date", "when", "recent"],
            "quality": ["quality", "clear", "unclear", "detailed"]
        }

        for text in feedback_texts:
            text_lower = text.lower()
            for theme, keywords in theme_keywords.items():
                if any(keyword in text_lower for keyword in keywords):
                    themes[theme] += 1

        # Return top themes
        sorted_themes = sorted(themes.items(), key=lambda x: x[1], reverse=True)
        return [theme for theme, count in sorted_themes[:5]]

    async def recommend_improvements(self, db: AsyncSession, user_id: int) -> List[Dict[str, Any]]:
        """Recommend system-wide improvements based on feedback patterns."""

        insights = await self.get_feedback_insights(db, user_id)

        recommendations = []

        if insights["average_rating"] < 0.7:
            recommendations.append({
                "type": "general",
                "priority": "high",
                "description": "Overall memory relevance is low. Consider improving content chunking and embedding quality.",
                "action_items": ["Review embedding model", "Improve content preprocessing"]
            })

        common_issues = insights.get("common_themes", [])
        if "missing_context" in common_issues:
            recommendations.append({
                "type": "context",
                "priority": "medium",
                "description": "Users frequently report missing context. Consider expanding memory chunks.",
                "action_items": ["Increase chunk overlap", "Add context expansion prompts"]
            })

        return recommendations


# Global feedback loop instance
feedback_loop = FeedbackLoop()
