"""
Unit tests for memory service.
"""
import pytest
from app.services.memory import MemoryService
from app.schemas.memory import MemoryCreate, MemoryUpdate
from app.exceptions import NotFoundError


@pytest.mark.asyncio
async def test_create_memory_success(db_session, test_user):
    """Test successful memory creation."""
    memory_service = MemoryService(db_session)
    
    memory_data = MemoryCreate(
        content="This is a test memory content",
        title="Test Memory",
        importance_score=0.8,
        priority="high",
        tags=["test", "memory"]
    )
    
    memory = await memory_service.create_memory(memory_data, test_user.id)
    
    assert memory is not None
    assert memory.content == "This is a test memory content"
    assert memory.title == "Test Memory"
    assert memory.user_id == test_user.id
    assert memory.importance_score == 0.8
    assert memory.priority == "high"


@pytest.mark.asyncio
async def test_get_memory_success(db_session, test_user, test_memory):
    """Test successful memory retrieval."""
    memory_service = MemoryService(db_session)
    
    memory = await memory_service.get_memory(test_memory.id, test_user.id)
    
    assert memory is not None
    assert memory.id == test_memory.id
    assert memory.content == test_memory.content


@pytest.mark.asyncio
async def test_get_memory_not_found(db_session, test_user):
    """Test memory retrieval with non-existent ID."""
    memory_service = MemoryService(db_session)
    
    memory = await memory_service.get_memory(99999, test_user.id)
    
    assert memory is None


@pytest.mark.asyncio
async def test_get_memory_wrong_user(db_session, test_user, test_memory):
    """Test memory retrieval with wrong user ID."""
    memory_service = MemoryService(db_session)
    
    # Create another user
    from app.models.user import User
    from app.utils.auth import get_password_hash
    other_user = User(
        email="other@example.com",
        username="otheruser",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)
    
    memory = await memory_service.get_memory(test_memory.id, other_user.id)
    
    assert memory is None


@pytest.mark.asyncio
async def test_update_memory_success(db_session, test_user, test_memory):
    """Test successful memory update."""
    memory_service = MemoryService(db_session)
    
    update_data = MemoryUpdate(
        title="Updated Title",
        importance_score=0.9
    )
    
    updated_memory = await memory_service.update_memory(
        test_memory.id,
        update_data,
        test_user.id
    )
    
    assert updated_memory is not None
    assert updated_memory.title == "Updated Title"
    assert updated_memory.importance_score == 0.9
    assert updated_memory.content == test_memory.content  # Unchanged


@pytest.mark.asyncio
async def test_delete_memory_success(db_session, test_user, test_memory):
    """Test successful memory deletion (soft delete)."""
    memory_service = MemoryService(db_session)
    
    deleted = await memory_service.delete_memory(test_memory.id, test_user.id)
    
    assert deleted is True
    
    # Verify memory is soft deleted
    memory = await memory_service.get_memory(test_memory.id, test_user.id)
    assert memory is None  # Should not return soft-deleted memories


@pytest.mark.asyncio
async def test_get_user_memories(db_session, test_user):
    """Test retrieving all memories for a user."""
    memory_service = MemoryService(db_session)
    
    # Create multiple memories
    for i in range(5):
        memory_data = MemoryCreate(
            content=f"Memory {i}",
            title=f"Title {i}"
        )
        await memory_service.create_memory(memory_data, test_user.id)
    
    memories = await memory_service.get_user_memories(test_user.id, limit=10, offset=0)
    
    assert len(memories) >= 5
    assert all(memory.user_id == test_user.id for memory in memories)

