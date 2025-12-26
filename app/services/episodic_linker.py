import networkx as nx
from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime, timedelta
from collections import defaultdict
import uuid
import numpy as np

from app.models.memory import EpisodicCluster, Memory, MemoryGraph, MemoryChunk
from app.services.vector_service import vector_service
from app.services.gemini_service import gemini_service
from app.config import settings


class EpisodicLinker:
    """Service for creating episodic clusters and memory relationships."""

    def __init__(self):
        self.similarity_threshold = settings.similarity_threshold

    def create_episodic_cluster(self, user_id: int, memory_ids: List[int],
                               cluster_type: str = "episodic") -> EpisodicCluster:
        """Create a new episodic cluster from memories."""
        cluster_id = str(uuid.uuid4())

        # Get memory data (this would come from database)
        # For now, using mock data structure
        memories = []  # Would fetch from DB

        # Calculate cluster properties
        cluster_name = gemini_service.generate_cluster_name(memories)
        description = self._generate_cluster_description(memories)

        # Calculate temporal bounds
        created_dates = [datetime.fromisoformat(mem.get("created_at", datetime.now().isoformat()))
                        for mem in memories]
        start_date = min(created_dates) if created_dates else None
        end_date = max(created_dates) if created_dates else None

        duration = None
        if start_date and end_date:
            duration = int((end_date - start_date).total_seconds() / 60)

        # Calculate centroid embedding
        embeddings = [mem.get("embedding", []) for mem in memories if mem.get("embedding")]
        centroid = self._calculate_centroid(embeddings) if embeddings else None

        # Create cluster
        cluster = EpisodicCluster(
            id=cluster_id,
            user_id=user_id,
            name=cluster_name,
            description=description,
            cluster_type=cluster_type,
            start_date=start_date,
            end_date=end_date,
            duration_minutes=duration,
            centroid_embedding=centroid,
            key_memories=memory_ids[:10],  # Top 10 memories
            importance_score=self._calculate_cluster_importance(memories)
        )

        return cluster

    def _generate_cluster_description(self, memories: List[Dict]) -> str:
        """Generate description for cluster."""
        if not memories:
            return "Empty cluster"

        summaries = [mem.get("summary", "") for mem in memories[:5]]
        combined = " ".join(summaries)

        return gemini_service.generate_memory_summary(combined, [])

    def _calculate_centroid(self, embeddings: List[List[float]]) -> List[float]:
        """Calculate centroid of embeddings."""
        if not embeddings:
            return []

        embeddings_array = np.array(embeddings)
        centroid = np.mean(embeddings_array, axis=0)
        # Normalize
        centroid = centroid / np.linalg.norm(centroid)
        return centroid.tolist()

    def _calculate_cluster_importance(self, memories: List[Dict]) -> float:
        """Calculate overall importance of cluster."""
        if not memories:
            return 0.5

        importance_scores = [mem.get("importance_score", 0.5) for mem in memories]
        return float(np.mean(importance_scores))

    def find_similar_memories(self, user_id: int, memory_embedding: List[float],
                             exclude_ids: Set[int] = None) -> List[Tuple[int, float]]:
        """Find memories similar to the given embedding."""
        exclude_ids = exclude_ids or set()

        # Search vector database
        similar_results = vector_service.search_similar(user_id, memory_embedding, top_k=20)

        # Filter out excluded IDs and low similarity
        filtered_results = [
            (mem_id, score) for mem_id, score in similar_results
            if mem_id not in exclude_ids and score >= self.similarity_threshold
        ]

        return filtered_results

    def create_memory_relationships(self, user_id: int, memory_id: int,
                                  related_memories: List[Tuple[int, float]]) -> List[Dict[str, Any]]:
        """Create relationships between memories."""
        relationships = []

        for related_id, similarity_score in related_memories:
            relationship = {
                "memory_id": memory_id,
                "related_memory_id": related_id,
                "relationship_type": self._classify_relationship(similarity_score),
                "strength": similarity_score
            }
            relationships.append(relationship)

        return relationships

    def _classify_relationship(self, similarity: float) -> str:
        """Classify relationship type based on similarity score."""
        if similarity >= 0.9:
            return "nearly_identical"
        elif similarity >= 0.8:
            return "very_similar"
        elif similarity >= 0.7:
            return "similar"
        elif similarity >= 0.6:
            return "related"
        else:
            return "loosely_related"

    def build_memory_graph(self, user_id: int, memory_ids: List[int],
                          graph_type: str = "semantic") -> MemoryGraph:
        """Build a graph representation of memory relationships."""
        # Create graph
        G = nx.Graph()

        # Add nodes (memories)
        for mem_id in memory_ids:
            G.add_node(mem_id, type="memory")

        # Add edges based on relationships
        for i, mem_id1 in enumerate(memory_ids):
            for mem_id2 in memory_ids[i+1:]:
                # Check if relationship exists (would query database)
                # For now, add edge if similarity is high enough
                embedding1 = []  # Would fetch from DB
                embedding2 = []  # Would fetch from DB

                if embedding1 and embedding2:
                    similarity = vector_service.calculate_similarity(embedding1, embedding2)
                    if similarity >= self.similarity_threshold:
                        G.add_edge(mem_id1, mem_id2, weight=similarity, type="similarity")

        # Calculate centrality
        centrality = nx.degree_centrality(G)

        # Detect communities
        communities = self._detect_communities(G)

        # Create graph object
        graph = MemoryGraph(
            user_id=user_id,
            name=f"{graph_type.title()} Graph",
            description=f"Graph of {len(memory_ids)} memories",
            graph_type=graph_type,
            nodes=list(G.nodes()),
            edges=[{"source": u, "target": v, "weight": d.get("weight", 1.0)}
                  for u, v, d in G.edges(data=True)],
            centrality_scores=centrality,
            clusters=communities
        )

        return graph

    def _detect_communities(self, G: nx.Graph) -> List[List[int]]:
        """Detect communities in the memory graph."""
        try:
            from networkx.algorithms.community import greedy_modularity_communities
            communities = greedy_modularity_communities(G)
            return [list(community) for community in communities]
        except ImportError:
            # Fallback if community detection not available
            return [list(G.nodes())]

    def find_episodic_clusters(self, user_id: int, time_window_hours: int = 24) -> List[EpisodicCluster]:
        """Find and create episodic clusters based on temporal proximity."""
        # This would query memories within time windows
        # For now, return empty list
        return []

    def link_decision_trail(self, user_id: int, decision_memory_id: int) -> Dict[str, Any]:
        """Create a decision trail linking related memories around a decision."""
        # Find memories that led to this decision
        # Find memories that resulted from this decision

        trail = {
            "decision_memory": decision_memory_id,
            "preceding_memories": [],  # Context before decision
            "resulting_memories": [],  # Outcomes after decision
            "related_decisions": [],   # Similar decisions
            "lessons_learned": []      # Reflections on this decision
        }

        return trail

    def update_cluster_with_new_memory(self, cluster_id: str, new_memory: Dict[str, Any]) -> bool:
        """Update an existing cluster with a new memory."""
        # Check if memory fits the cluster
        # Update cluster properties if it does

        # This would involve:
        # 1. Checking temporal fit
        # 2. Checking semantic similarity to cluster centroid
        # 3. Updating cluster properties

        return True  # Placeholder

    def merge_clusters(self, cluster_ids: List[str]) -> Optional[str]:
        """Merge multiple clusters into one."""
        if len(cluster_ids) < 2:
            return None

        # Create new merged cluster
        # Move all memories to new cluster
        # Delete old clusters

        merged_id = str(uuid.uuid4())
        return merged_id

    def split_cluster(self, cluster_id: str, split_criteria: Dict[str, Any]) -> List[str]:
        """Split a cluster based on criteria."""
        # Analyze cluster contents
        # Identify natural divisions
        # Create new clusters

        return [str(uuid.uuid4()), str(uuid.uuid4())]  # Placeholder


# Global episodic linker instance
episodic_linker = EpisodicLinker()
