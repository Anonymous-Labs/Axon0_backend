import google.generativeai as genai
from typing import List, Dict, Any, Optional, Tuple
import json
import re
from app.config import settings
from app.models.gemini_models import (
    RestructuredContent,
    MemoryChunk,
    ChunkType,
    MemoryRelationship,
    RelationshipType,
    ImprovementSuggestions,
    RestructuredContentResponse,
    RelationshipsResponse,
    SuggestionsResponse,
    ClusterNameResponse
)


class GeminiService:
    """Service for interacting with Google Gemini AI for content processing."""

    def __init__(self):
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash')
        else:
            self.model = None

    def restructure_content(self, content: str, context: Optional[str] = None) -> RestructuredContentResponse:
        """Restructure content into meaningful chunks using Gemini."""
        if not self.model:
            # Fallback to simple chunking if no API key
            simple_result = self._simple_chunking(content)
            return RestructuredContentResponse(
                success=True,
                data=RestructuredContent(**simple_result)
            )

        prompt = f"""
        Please analyze and restructure the following content into meaningful chunks for memory storage.
        Focus on:
        1. Breaking down into logical, self-contained chunks
        2. Identifying key concepts, actions, and decisions
        3. Preserving temporal and causal relationships
        4. Extracting metadata like topics, importance, and relationships

        Content: {content}

        {f'Context: {context}' if context else ''}

        Please respond in JSON format with the following structure:
        {{
            "chunks": [
                {{
                    "content": "chunk text",
                    "type": "concept|action|decision|fact|relationship",
                    "importance": 0.0-1.0,
                    "topics": ["topic1", "topic2"],
                    "temporal_info": "when this occurred or is relevant",
                    "relationships": ["connects to other chunks or concepts"]
                }}
            ],
            "summary": "brief overall summary",
            "key_concepts": ["concept1", "concept2"],
            "suggested_tags": ["tag1", "tag2"],
            "episodic_markers": ["marker1", "marker2"]
        }}
        """

        try:
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()

            # Clean up response (remove markdown code blocks if present)
            if result_text.startswith('```json'):
                result_text = result_text[7:]
            if result_text.endswith('```'):
                result_text = result_text[:-3]

            result_dict = json.loads(result_text)

            # Validate and parse with Pydantic
            restructured_content = RestructuredContent(**result_dict)

            return RestructuredContentResponse(
                success=True,
                data=restructured_content,
                raw_response=result_text
            )
        except Exception as e:
            print(f"Gemini restructuring failed: {e}")
            simple_result = self._simple_chunking(content)
            return RestructuredContentResponse(
                success=False,
                error_message=str(e),
                data=RestructuredContent(**simple_result)
            )

    def _simple_chunking(self, content: str) -> Dict[str, Any]:
        """Fallback simple chunking when Gemini is not available."""
        # Split by sentences and group into chunks
        sentences = re.split(r'(?<=[.!?])\s+', content.strip())

        chunks = []
        current_chunk = ""
        max_chunk_size = settings.max_chunk_size

        for sentence in sentences:
            if len(current_chunk + sentence) <= max_chunk_size:
                current_chunk += sentence + " "
            else:
                if current_chunk:
                    chunks.append(MemoryChunk(
                        content=current_chunk.strip(),
                        type=ChunkType.TEXT,
                        importance=0.5,
                        topics=[],
                        temporal_info=None,
                        relationships=[]
                    ))
                current_chunk = sentence + " "

        if current_chunk:
            chunks.append(MemoryChunk(
                content=current_chunk.strip(),
                type=ChunkType.TEXT,
                importance=0.5,
                topics=[],
                temporal_info=None,
                relationships=[]
            ))

        return {
            "chunks": [chunk.dict() for chunk in chunks],
            "summary": content[:200] + "..." if len(content) > 200 else content,
            "key_concepts": [],
            "suggested_tags": [],
            "episodic_markers": []
        }

    def generate_memory_summary(self, content: str, chunks: List[Dict]) -> str:
        """Generate a comprehensive summary of memory content."""
        if not self.model:
            return content[:500] + "..." if len(content) > 500 else content

        chunk_summaries = [chunk.get("content", "")[:100] for chunk in chunks[:5]]  # First 5 chunks

        prompt = f"""
        Generate a concise but comprehensive summary of this memory content.
        Focus on key information, decisions, and insights.

        Original content: {content[:1000]}

        Key chunks: {chunk_summaries}

        Provide a summary in 2-3 sentences that captures the essence.
        """

        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"Summary generation failed: {e}")
            return content[:300] + "..." if len(content) > 300 else content

    def analyze_relationships(self, memory_content: str, existing_memories: List[Dict]) -> RelationshipsResponse:
        """Analyze relationships between new memory and existing ones."""
        if not self.model or not existing_memories:
            return RelationshipsResponse(success=True, data=[])

        existing_summaries = [mem.get("summary", "")[:200] for mem in existing_memories[:10]]

        prompt = f"""
        Analyze how this new memory relates to existing memories.
        Identify connections, contradictions, or follow-ups.

        New memory: {memory_content[:800]}

        Existing memories: {existing_summaries}

        Respond with JSON array of relationships:
        [
            {{
                "memory_id": "existing_memory_id",
                "relationship_type": "follows|contradicts|expands|similar|references",
                "strength": 0.0-1.0,
                "description": "brief explanation"
            }}
        ]
        """

        try:
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()

            if result_text.startswith('```json'):
                result_text = result_text[7:]
            if result_text.endswith('```'):
                result_text = result_text[:-3]

            relationships_dict = json.loads(result_text)

            # Validate and parse with Pydantic
            relationships = [MemoryRelationship(**rel) for rel in relationships_dict]

            return RelationshipsResponse(
                success=True,
                data=relationships,
                raw_response=result_text
            )
        except Exception as e:
            print(f"Relationship analysis failed: {e}")
            return RelationshipsResponse(
                success=False,
                error_message=str(e),
                data=[]
            )

    def suggest_improvements(self, feedback_data: List[Dict]) -> SuggestionsResponse:
        """Analyze feedback to suggest memory improvements."""
        if not self.model or not feedback_data:
            return SuggestionsResponse(success=True, data=ImprovementSuggestions())

        feedback_text = "\n".join([f"{f.get('type', '')}: {f.get('text', '')}" for f in feedback_data])

        prompt = f"""
        Analyze user feedback on memory retrieval and suggest improvements.

        Feedback: {feedback_text}

        Provide suggestions in JSON format:
        {{
            "missing_context": ["what context was missing"],
            "improvement_suggestions": ["specific improvements"],
            "new_chunks_needed": ["additional chunks to create"],
            "relationship_updates": ["relationship changes needed"]
        }}
        """

        try:
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()

            if result_text.startswith('```json'):
                result_text = result_text[7:]
            if result_text.endswith('```'):
                result_text = result_text[:-3]

            suggestions_dict = json.loads(result_text)

            # Validate and parse with Pydantic
            suggestions = ImprovementSuggestions(**suggestions_dict)

            return SuggestionsResponse(
                success=True,
                data=suggestions,
                raw_response=result_text
            )
        except Exception as e:
            print(f"Improvement suggestions failed: {e}")
            return SuggestionsResponse(
                success=False,
                error_message=str(e),
                data=ImprovementSuggestions()
            )

    def generate_cluster_name(self, memories: List[Dict]) -> ClusterNameResponse:
        """Generate a meaningful name for an episodic cluster."""
        if not self.model:
            default_name = f"Cluster of {len(memories)} memories"
            return ClusterNameResponse(success=True, data=default_name)

        memory_summaries = [mem.get("summary", "")[:150] for mem in memories[:5]]

        prompt = f"""
        Generate a concise, meaningful name for this cluster of memories.
        The name should capture what these memories have in common.

        Memory summaries: {memory_summaries}

        Provide just the name, no quotes or extra text.
        """

        try:
            response = self.model.generate_content(prompt)
            cluster_name = response.text.strip().strip('"')
            return ClusterNameResponse(
                success=True,
                data=cluster_name,
                raw_response=response.text
            )
        except Exception as e:
            default_name = f"Memory Cluster {len(memories)}"
            return ClusterNameResponse(
                success=False,
                error_message=str(e),
                data=default_name
            )


# Global Gemini service instance
gemini_service = GeminiService()
