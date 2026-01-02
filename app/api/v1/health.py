"""
Health check endpoints for monitoring and load balancers.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Dict, Any
import time

from app.database import engine, check_database_health
from app.core.redis_client import get_redis_client, close_redis_client

router = APIRouter()


@router.get("/")
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint.
    
    Returns:
        dict: Health status
    """
    return {
        "status": "healthy",
        "service": "axon-memory",
        "timestamp": time.time(),
    }


@router.get("/db")
async def database_health_check() -> Dict[str, Any]:
    """
    Database health check endpoint.
    
    Returns:
        dict: Database health status with connection test
    """
    start_time = time.time()
    is_healthy = await check_database_health()
    response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
    
    if is_healthy:
        return {
            "status": "healthy",
            "database": "connected",
            "response_time_ms": round(response_time, 2),
        }
    else:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "response_time_ms": round(response_time, 2),
        }


@router.get("/redis")
async def redis_health_check() -> Dict[str, Any]:
    """
    Redis health check endpoint.
    
    Returns:
        dict: Redis health status with connection test
    """
    start_time = time.time()
    
    try:
        redis_client = await get_redis_client()
        await redis_client.ping()
        response_time = (time.time() - start_time) * 1000
        
        return {
            "status": "healthy",
            "redis": "connected",
            "response_time_ms": round(response_time, 2),
        }
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return {
            "status": "unhealthy",
            "redis": "disconnected",
            "error": str(e),
            "response_time_ms": round(response_time, 2),
        }


@router.get("/full")
async def full_health_check() -> Dict[str, Any]:
    """
    Comprehensive health check including all dependencies.
    
    Returns:
        dict: Complete health status of all services
    """
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "services": {},
    }
    
    # Check database
    db_start = time.time()
    db_healthy = await check_database_health()
    db_time = (time.time() - db_start) * 1000
    
    health_status["services"]["database"] = {
        "status": "healthy" if db_healthy else "unhealthy",
        "response_time_ms": round(db_time, 2),
    }
    
    # Check Redis
    redis_start = time.time()
    try:
        redis_client = await get_redis_client()
        await redis_client.ping()
        redis_time = (time.time() - redis_start) * 1000
        health_status["services"]["redis"] = {
            "status": "healthy",
            "response_time_ms": round(redis_time, 2),
        }
    except Exception as e:
        redis_time = (time.time() - redis_start) * 1000
        health_status["services"]["redis"] = {
            "status": "unhealthy",
            "error": str(e),
            "response_time_ms": round(redis_time, 2),
        }
    
    # Determine overall status
    all_healthy = all(
        service["status"] == "healthy"
        for service in health_status["services"].values()
    )
    
    if not all_healthy:
        health_status["status"] = "degraded"
    
    return health_status

