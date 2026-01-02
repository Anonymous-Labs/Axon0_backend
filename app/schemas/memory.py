from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class MemoryBase(BaseModel):
    content: str = Field(..., min_length=1, max_length=50000)  # Increased for longer content
    title: Optional[str] = Field(None, max_length=500)
    extra_metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = Field(None, max_length=20)  # Limit number of tags
    importance_score: float = Field(0.5, ge=0.0, le=1.0)
    priority: str = Field("medium", pattern="^(low|medium|high)$")
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate and sanitize tags."""
        if v is None:
            return v
        if len(v) > 20:
            raise ValueError("Maximum 20 tags allowed")
        # Sanitize each tag
        from app.core.security import sanitize_input
        return [sanitize_input(tag.strip(), max_length=50) for tag in v if tag.strip()][:20]
    
    @field_validator('title')
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize title."""
        if v is None:
            return v
        from app.core.security import sanitize_input
        return sanitize_input(v.strip(), max_length=500)
    
    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Sanitize content."""
        from app.core.security import sanitize_input
        return sanitize_input(v.strip(), max_length=50000)


class MemoryCreate(MemoryBase):
    pass


class MemoryUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=10000)
    title: Optional[str] = Field(None, max_length=500)
    extra_metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    importance_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    priority: Optional[str] = Field(None, pattern="^(low|medium|high)$")


class Memory(MemoryBase):
    id: int
    user_id: int
    summary: Optional[str] = None
    cluster_id: Optional[str] = None
    parent_memory_id: Optional[int] = None
    is_compressed: bool = False
    is_deleted: bool = False
    created_at: datetime
    updated_at: Optional[datetime]
    last_accessed: Optional[datetime]

    class Config:
        from_attributes = True


class MemorySearch(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(10, ge=1, le=100)
    offset: int = Field(0, ge=0)
    tags: Optional[List[str]] = None
    priority: Optional[str] = Field(None, pattern="^(low|medium|high)$")
    min_importance: Optional[float] = Field(None, ge=0.0, le=1.0)
    cluster_id: Optional[str] = None
    semantic_search: bool = True
    
    @field_validator('query')
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Sanitize search query."""
        from app.core.security import sanitize_input, sanitize_sql_like_pattern
        # Don't HTML escape search queries, but sanitize SQL patterns
        sanitized = sanitize_sql_like_pattern(v.strip())
        return sanitized[:500]  # Limit length
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate and sanitize tags."""
        if v is None:
            return v
        if len(v) > 10:
            raise ValueError("Maximum 10 tags allowed in search")
        from app.core.security import sanitize_input
        return [sanitize_input(tag.strip(), max_length=50) for tag in v if tag.strip()][:10]


class MemorySearchResponse(BaseModel):
    memories: List[Memory]
    total_count: int
    search_score: Optional[float] = None


class FeedbackBase(BaseModel):
    feedback_type: str = Field(..., pattern="^(thumbs_up|thumbs_down|relevance_score)$")
    feedback_value: Optional[float] = None
    feedback_text: Optional[str] = None


class FeedbackCreate(FeedbackBase):
    memory_id: int


class Feedback(FeedbackBase):
    id: int
    memory_id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class MemoryStats(BaseModel):
    total_memories: int
    active_memories: int
    compressed_memories: int
    total_clusters: int
    average_importance: float
    memories_by_priority: Dict[str, int]


class APIKeyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    permissions: List[str] = Field(default_factory=lambda: ["read", "write"])
    expires_at: Optional[datetime] = None


class APIKeyCreate(APIKeyBase):
    pass


class APIKey(APIKeyBase):
    id: int
    user_id: int
    key: str  # Only shown when created, not in listings
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime]
    usage_count: int

    class Config:
        from_attributes = True


class APIKeyList(BaseModel):
    id: int
    name: str
    description: Optional[str]
    permissions: List[str]
    is_active: bool
    expires_at: Optional[datetime]
    created_at: datetime
    last_used_at: Optional[datetime]
    usage_count: int

    class Config:
        from_attributes = True
