"""
Decorators for caching and performance optimization.
"""
import functools
import hashlib
import json
import logging
from typing import Callable, Any, Optional
from app.core.redis_client import cache_service

logger = logging.getLogger(__name__)


def cache_result(ttl: int = 3600, key_prefix: str = "cache"):
    """
    Decorator to cache function results in Redis.
    
    Args:
        ttl: Time to live in seconds (default: 1 hour)
        key_prefix: Prefix for cache keys
    
    Usage:
        @cache_result(ttl=1800, key_prefix="memory")
        async def get_memory(memory_id: int):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key = _generate_cache_key(key_prefix, func.__name__, *args, **kwargs)
            
            # Try to get from cache
            cached_result = await cache_service.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}", extra={"cache_key": cache_key})
                return cached_result
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Store in cache
            await cache_service.set(cache_key, result, ttl)
            logger.debug(f"Cache miss for {func.__name__}, stored result", extra={"cache_key": cache_key})
            
            return result
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For synchronous functions, we can't use async cache
            # Just execute the function
            return func(*args, **kwargs)
        
        # Return appropriate wrapper based on function type
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def invalidate_cache(key_pattern: str):
    """
    Decorator to invalidate cache entries matching a pattern.
    
    Args:
        key_pattern: Cache key pattern to invalidate
    
    Usage:
        @invalidate_cache("memory:*")
        async def update_memory(memory_id: int):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Execute function first
            result = await func(*args, **kwargs)
            
            # Invalidate cache (this would need pattern matching support in Redis)
            # For now, we'll use a simple key-based approach
            logger.debug(f"Invalidating cache for pattern: {key_pattern}")
            # TODO: Implement pattern-based cache invalidation
            
            return result
        
        return async_wrapper
    
    return decorator


def _generate_cache_key(prefix: str, func_name: str, *args, **kwargs) -> str:
    """
    Generate a cache key from function name and arguments.
    
    Args:
        prefix: Key prefix
        func_name: Function name
        *args: Positional arguments
        **kwargs: Keyword arguments
    
    Returns:
        str: Cache key
    """
    # Create a hash of the arguments
    key_data = {
        "func": func_name,
        "args": args,
        "kwargs": kwargs,
    }
    
    # Convert to JSON string and hash
    key_string = json.dumps(key_data, sort_keys=True, default=str)
    key_hash = hashlib.md5(key_string.encode()).hexdigest()
    
    return f"{prefix}:{func_name}:{key_hash}"


def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Decorator to retry a function on failure.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay on each retry
    
    Usage:
        @retry_on_failure(max_retries=3, delay=1.0)
        async def external_api_call():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            import asyncio
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Attempt {attempt + 1} failed for {func.__name__}, retrying in {current_delay}s",
                            extra={"error": str(e), "attempt": attempt + 1}
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"All {max_retries} attempts failed for {func.__name__}",
                            extra={"error": str(e)},
                            exc_info=True
                        )
            
            raise last_exception
        
        return async_wrapper
    
    return decorator

