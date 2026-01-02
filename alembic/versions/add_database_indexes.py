"""Add database indexes for frequently queried columns

Revision ID: add_indexes_001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_indexes_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Add indexes to improve query performance."""
    
    # Indexes for memories table
    op.create_index(
        'idx_memories_user_id_created_at',
        'memories',
        ['user_id', 'created_at'],
        unique=False
    )
    op.create_index(
        'idx_memories_user_id_deleted',
        'memories',
        ['user_id', 'is_deleted'],
        unique=False
    )
    op.create_index(
        'idx_memories_cluster_id',
        'memories',
        ['cluster_id'],
        unique=False
    )
    op.create_index(
        'idx_memories_priority',
        'memories',
        ['priority'],
        unique=False
    )
    op.create_index(
        'idx_memories_importance',
        'memories',
        ['importance_score'],
        unique=False
    )
    op.create_index(
        'idx_memories_last_accessed',
        'memories',
        ['last_accessed'],
        unique=False
    )
    
    # Indexes for feedback table
    op.create_index(
        'idx_feedback_memory_id',
        'feedback',
        ['memory_id'],
        unique=False
    )
    op.create_index(
        'idx_feedback_user_id',
        'feedback',
        ['user_id'],
        unique=False
    )
    op.create_index(
        'idx_feedback_created_at',
        'feedback',
        ['created_at'],
        unique=False
    )
    
    # Indexes for api_keys table
    op.create_index(
        'idx_api_keys_user_id_active',
        'api_keys',
        ['user_id', 'is_active'],
        unique=False
    )
    op.create_index(
        'idx_api_keys_expires_at',
        'api_keys',
        ['expires_at'],
        unique=False
    )
    
    # Indexes for episodic_clusters table
    op.create_index(
        'idx_episodic_clusters_user_id',
        'episodic_clusters',
        ['user_id'],
        unique=False
    )
    op.create_index(
        'idx_episodic_clusters_start_date',
        'episodic_clusters',
        ['start_date'],
        unique=False
    )
    
    # Indexes for memory_chunks table
    op.create_index(
        'idx_memory_chunks_memory_id',
        'memory_chunks',
        ['memory_id'],
        unique=False
    )
    op.create_index(
        'idx_memory_chunks_user_id',
        'memory_chunks',
        ['user_id'],
        unique=False
    )


def downgrade():
    """Remove indexes."""
    
    # Drop indexes in reverse order
    op.drop_index('idx_memory_chunks_user_id', table_name='memory_chunks')
    op.drop_index('idx_memory_chunks_memory_id', table_name='memory_chunks')
    op.drop_index('idx_episodic_clusters_start_date', table_name='episodic_clusters')
    op.drop_index('idx_episodic_clusters_user_id', table_name='episodic_clusters')
    op.drop_index('idx_api_keys_expires_at', table_name='api_keys')
    op.drop_index('idx_api_keys_user_id_active', table_name='api_keys')
    op.drop_index('idx_feedback_created_at', table_name='feedback')
    op.drop_index('idx_feedback_user_id', table_name='feedback')
    op.drop_index('idx_feedback_memory_id', table_name='feedback')
    op.drop_index('idx_memories_last_accessed', table_name='memories')
    op.drop_index('idx_memories_importance', table_name='memories')
    op.drop_index('idx_memories_priority', table_name='memories')
    op.drop_index('idx_memories_cluster_id', table_name='memories')
    op.drop_index('idx_memories_user_id_deleted', table_name='memories')
    op.drop_index('idx_memories_user_id_created_at', table_name='memories')

