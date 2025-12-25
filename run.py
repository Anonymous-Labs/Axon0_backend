#!/usr/bin/env python3
"""
AXON Backend Server Runner
"""
import uvicorn
from app.config import settings


def main():
    """Run the FastAPI server with uvicorn."""
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info" if settings.debug else "warning",
    )


if __name__ == "__main__":
    main()
