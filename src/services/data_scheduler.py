#!/usr/bin/env python3
"""
Data Scheduler Service for Railway
Runs continuously and manages all OHLC data updates
"""

import os
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.schedule_updates import OHLCScheduler
from loguru import logger

def main():
    """Main entry point for Railway scheduler service"""
    logger.info("Starting Data Scheduler Service on Railway")
    logger.info(f"Environment: {os.getenv('RAILWAY_ENVIRONMENT', 'unknown')}")
    logger.info(f"Service: {os.getenv('RAILWAY_SERVICE_NAME', 'unknown')}")
    
    # Create and run scheduler in daemon mode
    scheduler = OHLCScheduler(mode='daemon')
    
    try:
        # This will run forever, handling all scheduled updates
        scheduler.run_daemon()
    except Exception as e:
        logger.error(f"Scheduler crashed: {e}")
        # Railway will automatically restart the service
        sys.exit(1)

if __name__ == "__main__":
    main()
