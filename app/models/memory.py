from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, JSON, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Memory(Base):
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Content
    content = Column(Text, nullable=False)
    title = Column(String(500))
    summary = Column(Text)  # AI-generated summary

    # Metadata
    extra_metadata = Column(JSON)  # Flexible JSON field for additional metadata
    tags = Column(JSON)  # Array of tags as JSON

    # Importance and priority
    importance_score = Column(Float, default=0.5)  # 0-1 scale
    priority = Column(String(20), default="medium")  # low, medium, high

    # Temporal information
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_accessed = Column(DateTime(timezone=True))

    # Clustering and relationships
    cluster_id = Column(String(100))  # For episodic clustering
    parent_memory_id = Column(Integer, ForeignKey("memories.id"))  # For hierarchical memories

    # Status flags
    is_compressed = Column(Boolean, default=False)  # Whether this memory has been summarized
    is_deleted = Column(Boolean, default=False)

    # Vector embeddings (stored as JSON for simplicity, can be moved to vector DB later)
    embedding = Column(JSON)  # Store embedding vector

    # Relationships
    user = relationship("User", back_populates="memories")
    child_memories = relationship("Memory", back_populates="parent_memory")

    parent_memory = relationship("Memory", back_populates="child_memories", remote_side=[id])


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    memory_id = Column(Integer, ForeignKey("memories.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Feedback types
    feedback_type = Column(String(50), nullable=False)  # thumbs_up, thumbs_down, relevance_score
    feedback_value = Column(Float)  # For numeric scores
    feedback_text = Column(Text)  # Optional text feedback

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    memory = relationship("Memory")
    user = relationship("User", back_populates="feedbacks")


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # API Key details
    key = Column(String, unique=True, index=True, nullable=False)  # The actual API key
    name = Column(String(100), nullable=False)  # User-friendly name
    description = Column(String(500))  # Optional description

    # Permissions/Roles
    permissions = Column(JSON, default=list)  # List of permissions like ["read", "write", "delete"]

    # Status
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime(timezone=True))  # Optional expiration

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True))
    usage_count = Column(Integer, default=0)

    # Relationships
    user = relationship("User", back_populates="api_keys")
