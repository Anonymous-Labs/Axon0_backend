"""
Redis client for caching and rate limiting.
"""
import redis.asyncio as redis
import logging
import asyncio
from typing import Optional, Any
import json
from app.config import settings

logger = logging.getLogger(__name__)

# Global Redis client instance
_redis_client: Optional[redis.Redis] = None


async def get_redis_client() -> Optional[redis.Redis]:
    """
    Get or create Redis client instance.
    
    Returns:
        Redis client instance or None if connection fails
    
    Note:
        Returns None instead of raising exception to allow graceful degradation
    """
    global _redis_client
    
    if _redis_client is None:
        try:
            _redis_client = await redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=False,
            )
            # Test connection with short timeout
            await asyncio.wait_for(_redis_client.ping(), timeout=2.0)
            logger.info("Redis client connected successfully")
        except Exception as e:
            logger.warning("Redis connection failed, continuing without Redis", extra={"error": str(e)})
            _redis_client = None
            return None
    
    return _redis_client


async def close_redis_client() -> None:
    """Close Redis client connection."""
    global _redis_client
    
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis client closed")


class CacheService:
    """Service for caching data in Redis."""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self._client = redis_client
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
        
        Returns:
            Cached value or None if not found
        """
        try:
            client = self._client or await get_redis_client()
            if client is None:
                return None
            value = await client.get(key)
            if value:
                return json.loads(value)
            return None
        except (ConnectionError, Exception) as e:
            # Fail gracefully if Redis is unavailable
            logger.debug("Cache get failed (Redis unavailable)", extra={"key": key, "error": str(e)})
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """
        Set value in cache with TTL.
        
        Args:
            key: Cache key
            value: Value to cache (must be JSON serializable)
            ttl: Time to live in seconds (default: 1 hour)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            client = self._client or await get_redis_client()
            if client is None:
                return False
            serialized = json.dumps(value)
            await client.setex(key, ttl, serialized)
            return True
        except (ConnectionError, Exception) as e:
            # Fail gracefully if Redis is unavailable
            logger.debug("Cache set failed (Redis unavailable)", extra={"key": key, "error": str(e)})
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Delete value from cache.
        
        Args:
            key: Cache key
        
        Returns:
            True if successful, False otherwise
        """
        try:
            client = self._client or await get_redis_client()
            if client is None:
                return False
            await client.delete(key)
            return True
        except (ConnectionError, Exception) as e:
            # Fail gracefully if Redis is unavailable
            logger.debug("Cache delete failed (Redis unavailable)", extra={"key": key, "error": str(e)})
            return False
    
    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key
        
        Returns:
            True if key exists, False otherwise
        """
        try:
            client = self._client or await get_redis_client()
            result = await client.exists(key)
            return bool(result)
        except Exception as e:
            logger.error("Cache exists check failed", extra={"key": key, "error": str(e)})
            return False
    
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Increment a counter in cache.
        
        Args:
            key: Cache key
            amount: Amount to increment by
        
        Returns:
            New value or None if failed
        """
        try:
            client = self._client or await get_redis_client()
            return await client.incrby(key, amount)
        except Exception as e:
            logger.error("Cache increment failed", extra={"key": key, "error": str(e)})
            return None
    
    async def expire(self, key: str, ttl: int) -> bool:
        """
        Set expiration time for a key.
        
        Args:
            key: Cache key
            ttl: Time to live in seconds
        
        Returns:
            True if successful, False otherwise
        """
        try:
            client = self._client or await get_redis_client()
            return await client.expire(key, ttl)
        except Exception as e:
            logger.error("Cache expire failed", extra={"key": key, "error": str(e)})
            return False


# Global cache service instance
cache_service = CacheService()

