#!/usr/bin/env python3
"""
Start Shadow Testing locally for debugging and testing.
This will monitor scan_history and create shadow variations.
"""

import asyncio
import sys
import os
from dotenv import load_dotenv
from loguru import logger

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the shadow scan monitor
from scripts.shadow_scan_monitor import ShadowScanMonitor

async def main():
    """Main entry point"""
    # Load environment variables
    load_dotenv()
    
    # Check if shadow testing is enabled
    enable_shadow = os.getenv("ENABLE_SHADOW_TESTING", "true").lower() == "true"
    
    if not enable_shadow:
        logger.warning("Shadow Testing is disabled in environment variables")
        logger.info("Set ENABLE_SHADOW_TESTING=true to enable")
        return
    
    logger.info("="*60)
    logger.info("STARTING SHADOW TESTING MONITOR")
    logger.info("="*60)
    logger.info("This will:")
    logger.info("1. Monitor scan_history table for new scans")
    logger.info("2. Create shadow variations for each scan")
    logger.info("3. Store variations in shadow_variations table")
    logger.info("4. Shadow evaluator will then evaluate outcomes")
    logger.info("="*60)
    
    # Create and start monitor
    monitor = ShadowScanMonitor()
    
    try:
        await monitor.monitor_loop()
    except KeyboardInterrupt:
        logger.info("\nShutting down Shadow Testing Monitor...")
    except Exception as e:
        logger.error(f"Error in shadow testing: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
