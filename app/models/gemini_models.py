from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class ChunkType(str, Enum):
    CONCEPT = "concept"
    ACTION = "action"
    DECISION = "decision"
    FACT = "fact"
    RELATIONSHIP = "relationship"
    TEXT = "text"


class MemoryChunk(BaseModel):
    """Represents a chunk of memory content."""
    content: str = Field(..., description="The text content of this chunk")
    type: ChunkType = Field(..., description="The type of chunk")
    importance: float = Field(..., ge=0.0, le=1.0, description="Importance score from 0.0 to 1.0")
    topics: List[str] = Field(default_factory=list, description="Topics related to this chunk")
    temporal_info: Optional[str] = Field(None, description="When this chunk occurred or is relevant")
    relationships: List[str] = Field(default_factory=list, description="Relationships to other chunks or concepts")


class RestructuredContent(BaseModel):
    """Response model for restructured content."""
    chunks: List[MemoryChunk] = Field(..., description="List of memory chunks")
    summary: str = Field(..., description="Overall summary of the content")
    key_concepts: List[str] = Field(default_factory=list, description="Key concepts extracted")
    suggested_tags: List[str] = Field(default_factory=list, description="Suggested tags for the content")
    episodic_markers: List[str] = Field(default_factory=list, description="Episodic markers identified")


class RelationshipType(str, Enum):
    FOLLOWS = "follows"
    CONTRADICTS = "contradicts"
    EXPANDS = "expands"
    SIMILAR = "similar"
    REFERENCES = "references"


class MemoryRelationship(BaseModel):
    """Represents a relationship between memories."""
    memory_id: str = Field(..., description="ID of the related memory")
    relationship_type: RelationshipType = Field(..., description="Type of relationship")
    strength: float = Field(..., ge=0.0, le=1.0, description="Strength of the relationship")
    description: str = Field(..., description="Brief explanation of the relationship")


class ImprovementSuggestions(BaseModel):
    """Suggestions for improving memory retrieval and storage."""
    missing_context: List[str] = Field(default_factory=list, description="Context that was missing")
    improvement_suggestions: List[str] = Field(default_factory=list, description="Specific improvement suggestions")
    new_chunks_needed: List[str] = Field(default_factory=list, description="New chunks that should be created")
    relationship_updates: List[str] = Field(default_factory=list, description="Relationship changes needed")


class GeminiResponse(BaseModel):
    """Base class for Gemini API responses."""
    success: bool = Field(default=True, description="Whether the request was successful")
    error_message: Optional[str] = Field(None, description="Error message if request failed")
    raw_response: Optional[str] = Field(None, description="Raw response from Gemini API")


class RestructuredContentResponse(GeminiResponse):
    """Response for content restructuring."""
    data: Optional[RestructuredContent] = Field(None, description="Restructured content data")


class RelationshipsResponse(GeminiResponse):
    """Response for relationship analysis."""
    data: Optional[List[MemoryRelationship]] = Field(None, description="List of relationships")


class SuggestionsResponse(GeminiResponse):
    """Response for improvement suggestions."""
    data: Optional[ImprovementSuggestions] = Field(None, description="Improvement suggestions")


class ClusterNameResponse(GeminiResponse):
    """Response for cluster naming."""
    data: Optional[str] = Field(None, description="Generated cluster name")
