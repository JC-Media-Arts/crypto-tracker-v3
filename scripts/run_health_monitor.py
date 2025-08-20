#!/usr/bin/env python3
"""
Run the health monitoring service.
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

import uvicorn
from src.monitoring.health import app
from src.config.settings import get_settings
from loguru import logger


def main():
    """Run the health monitoring service."""
    settings = get_settings()

    # Configure logging
    logger.add(
        f"{settings.logs_dir}/health_monitor.log",
        rotation="1 day",
        retention="7 days",
        level=settings.log_level,
    )

    logger.info("Starting Health Monitoring Service")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Port: 8080")

    # Run the FastAPI app
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level=settings.log_level.lower(),
        reload=settings.is_development,
    )


if __name__ == "__main__":
    main()
