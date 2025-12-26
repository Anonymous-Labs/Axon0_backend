from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, JSON, Boolean, Table
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


# Association table for memory relationships (many-to-many) - must be defined before classes that use it
memory_relationships = Table(
    'memory_relationships',
    Base.metadata,
    Column('memory_id', Integer, ForeignKey('memories.id'), primary_key=True),
    Column('related_memory_id', Integer, ForeignKey('memories.id'), primary_key=True),
    Column('relationship_type', String(50), nullable=False),  # 'similar', 'follows', 'contradicts', etc.
    Column('strength', Float, default=1.0),  # Relationship strength 0-1
    Column('created_at', DateTime(timezone=True), server_default=func.now())
)


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
    cluster_id = Column(String(100), ForeignKey("episodic_clusters.id"))  # For episodic clustering
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

    # New episodic relationships
    episodic_cluster = relationship("EpisodicCluster", back_populates="memories")
    chunks = relationship("MemoryChunk", back_populates="memory")

    # Many-to-many relationships
    related_memories = relationship(
        "Memory",
        secondary=memory_relationships,
        primaryjoin=id == memory_relationships.c.memory_id,
        secondaryjoin=id == memory_relationships.c.related_memory_id,
        backref="related_to"
    )


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




class EpisodicCluster(Base):
    """Episodic clusters group related memories by time, context, or topic."""
    __tablename__ = "episodic_clusters"

    id = Column(String(100), primary_key=True)  # UUID-like cluster identifier
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Cluster metadata
    name = Column(String(500))  # Auto-generated or user-defined name
    description = Column(Text)  # AI-generated description
    cluster_type = Column(String(50), default="episodic")  # episodic, semantic, temporal

    # Temporal information
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))
    duration_minutes = Column(Integer)  # Total duration of the episode

    # Importance and priority
    importance_score = Column(Float, default=0.5)
    priority = Column(String(20), default="medium")

    # Content summary
    summary = Column(Text)  # AI-generated summary of the cluster
    key_memories = Column(JSON)  # List of most important memory IDs in cluster

    # Vector representation (centroid of cluster)
    centroid_embedding = Column(JSON)

    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="episodic_clusters")
    memories = relationship("Memory", back_populates="episodic_cluster")


class MemoryChunk(Base):
    """Chunks of memory content for better retrieval and processing."""
    __tablename__ = "memory_chunks"

    id = Column(Integer, primary_key=True, index=True)
    memory_id = Column(Integer, ForeignKey("memories.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Chunk content
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)  # Position in original memory
    chunk_type = Column(String(50), default="text")  # text, code, structured_data

    # Embedding for this chunk
    embedding = Column(JSON)

    # Metadata
    token_count = Column(Integer)
    importance_score = Column(Float, default=0.5)

    # Relationships
    memory = relationship("Memory", back_populates="chunks")
    user = relationship("User")


class MemoryGraph(Base):
    """Graph representation of memory relationships and connections."""
    __tablename__ = "memory_graphs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Graph metadata
    name = Column(String(500))
    description = Column(Text)
    graph_type = Column(String(50), default="semantic")  # semantic, temporal, contextual

    # Graph structure (stored as adjacency list in JSON)
    nodes = Column(JSON)  # List of memory IDs or cluster IDs
    edges = Column(JSON)  # List of relationships between nodes

    # Analysis results
    centrality_scores = Column(JSON)  # PageRank or other centrality measures
    clusters = Column(JSON)  # Detected communities/clusters

    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="memory_graphs")


class ContextComposition(Base):
    """Context compositions for restructuring and ranking memories."""
    __tablename__ = "context_compositions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Composition details
    name = Column(String(500))
    query = Column(Text)  # Original query or context request
    composition_type = Column(String(50), default="search")  # search, recommendation, summary

    # Composed content
    memory_ids = Column(JSON)  # Ordered list of memory IDs
    composed_content = Column(Text)  # AI-generated composed response
    ranking_scores = Column(JSON)  # Scores for each memory in composition

    # Metadata
    total_memories = Column(Integer)
    relevance_score = Column(Float)

    # Feedback integration
    feedback_count = Column(Integer, default=0)
    average_feedback = Column(Float, default=0.0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User")
