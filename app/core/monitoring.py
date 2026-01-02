"""
Monitoring and metrics for production.
"""
import time
import logging
from typing import Dict, Any, Optional
from functools import wraps
from fastapi import Request
from app.core.redis_client import cache_service

logger = logging.getLogger(__name__)

# In-memory metrics (can be moved to Redis for distributed systems)
_metrics = {
    "requests_total": 0,
    "requests_by_endpoint": {},
    "requests_by_status": {},
    "response_times": [],
    "errors_total": 0,
    "errors_by_type": {},
}


def track_request_metrics(endpoint: str, status_code: int, response_time: float):
    """
    Track request metrics.
    
    Args:
        endpoint: API endpoint
        status_code: HTTP status code
        response_time: Response time in seconds
    """
    _metrics["requests_total"] += 1
    
    # Track by endpoint
    if endpoint not in _metrics["requests_by_endpoint"]:
        _metrics["requests_by_endpoint"][endpoint] = 0
    _metrics["requests_by_endpoint"][endpoint] += 1
    
    # Track by status code
    status_category = f"{status_code // 100}xx"
    if status_category not in _metrics["requests_by_status"]:
        _metrics["requests_by_status"][status_category] = 0
    _metrics["requests_by_status"][status_category] += 1
    
    # Track response times (keep last 1000)
    _metrics["response_times"].append(response_time)
    if len(_metrics["response_times"]) > 1000:
        _metrics["response_times"] = _metrics["response_times"][-1000:]
    
    # Track errors
    if status_code >= 400:
        _metrics["errors_total"] += 1
        error_type = f"{status_code}"
        if error_type not in _metrics["errors_by_type"]:
            _metrics["errors_by_type"][error_type] = 0
        _metrics["errors_by_type"][error_type] += 1


def get_metrics() -> Dict[str, Any]:
    """
    Get current metrics.
    
    Returns:
        Dictionary of metrics
    """
    response_times = _metrics["response_times"]
    avg_response_time = sum(response_times) / len(response_times) if response_times else 0
    
    return {
        "requests_total": _metrics["requests_total"],
        "requests_by_endpoint": _metrics["requests_by_endpoint"],
        "requests_by_status": _metrics["requests_by_status"],
        "errors_total": _metrics["errors_total"],
        "errors_by_type": _metrics["errors_by_type"],
        "average_response_time_ms": round(avg_response_time * 1000, 2),
        "p95_response_time_ms": round(
            sorted(response_times)[int(len(response_times) * 0.95)] * 1000, 2
        ) if len(response_times) > 20 else 0,
        "p99_response_time_ms": round(
            sorted(response_times)[int(len(response_times) * 0.99)] * 1000, 2
        ) if len(response_times) > 20 else 0,
    }


def reset_metrics():
    """Reset all metrics."""
    global _metrics
    _metrics = {
        "requests_total": 0,
        "requests_by_endpoint": {},
        "requests_by_status": {},
        "response_times": [],
        "errors_total": 0,
        "errors_by_type": {},
    }

