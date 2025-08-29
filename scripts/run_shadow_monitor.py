#!/usr/bin/env python3
"""
Shadow Monitor Service - Continuous Runner
Monitors scan_history and creates shadow variations for R&D analysis
Part of the modular Research & Development system
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from loguru import logger
import signal

sys.path.append(".")

from src.data.supabase_client import SupabaseClient
from scripts.shadow_scan_monitor import ShadowScanMonitor


class ShadowMonitorService:
    """Continuous shadow monitor service for Railway deployment"""
    
    def __init__(self):
        self.monitor = ShadowScanMonitor()
        self.running = True
        self.check_interval = 30  # Check for new scans every 30 seconds
        self.stats = {
            "scans_processed": 0,
            "shadows_created": 0,
            "errors": 0,
            "start_time": datetime.utcnow()
        }
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
    
    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info("Shutdown signal received, stopping monitor...")
        self.running = False
    
    async def log_stats(self):
        """Log statistics periodically"""
        runtime = datetime.utcnow() - self.stats["start_time"]
        hours = runtime.total_seconds() / 3600
        
        logger.info("=" * 60)
        logger.info("SHADOW MONITOR STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Runtime: {hours:.1f} hours")
        logger.info(f"Scans processed: {self.stats['scans_processed']:,}")
        logger.info(f"Shadow variations created: {self.stats['shadows_created']:,}")
        logger.info(f"Errors encountered: {self.stats['errors']}")
        
        if self.stats['scans_processed'] > 0:
            avg_shadows = self.stats['shadows_created'] / self.stats['scans_processed']
            logger.info(f"Average shadows per scan: {avg_shadows:.1f}")
        
        logger.info("=" * 60)
    
    async def process_scans(self):
        """Main processing loop"""
        logger.info("Starting scan processing...")
        
        while self.running:
            try:
                # Get unprocessed scans
                unprocessed = await self.monitor.get_unprocessed_scans()
                
                if unprocessed:
                    logger.info(f"Processing {len(unprocessed)} new scans...")
                    
                    for scan in unprocessed:
                        if not self.running:
                            break
                            
                        try:
                            # Create shadow variations
                            success = await self.monitor.create_shadows_for_scan(scan)
                            
                            if success:
                                self.stats['scans_processed'] += 1
                                # Assuming 8 variations per scan (based on shadow config)
                                self.stats['shadows_created'] += 8
                                
                                # Log progress every 10 scans
                                if self.stats['scans_processed'] % 10 == 0:
                                    logger.info(
                                        f"Progress: {self.stats['scans_processed']} scans, "
                                        f"{self.stats['shadows_created']} shadows created"
                                    )
                        
                        except Exception as e:
                            logger.error(f"Error processing scan {scan.get('scan_id')}: {e}")
                            self.stats['errors'] += 1
                
                # Wait before next check
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
                self.stats['errors'] += 1
                await asyncio.sleep(60)  # Wait longer on error
    
    async def periodic_stats(self):
        """Log statistics every hour"""
        while self.running:
            await asyncio.sleep(3600)  # Every hour
            if self.running:
                await self.log_stats()
    
    async def heartbeat(self):
        """Update heartbeat in database"""
        supabase = SupabaseClient()
        
        while self.running:
            try:
                # Update heartbeat
                supabase.client.table("system_heartbeat").upsert({
                    "service_name": "shadow_monitor",
                    "status": "running",
                    "last_heartbeat": datetime.utcnow().isoformat(),
                    "metadata": {
                        "scans_processed": self.stats['scans_processed'],
                        "shadows_created": self.stats['shadows_created'],
                        "check_interval": self.check_interval
                    }
                }).execute()
                
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
            
            await asyncio.sleep(60)  # Update every minute
    
    async def run(self):
        """Run all services"""
        logger.info("=" * 60)
        logger.info("SHADOW MONITOR SERVICE STARTING")
        logger.info("=" * 60)
        logger.info(f"Check interval: {self.check_interval} seconds")
        logger.info(f"Environment: {os.getenv('RAILWAY_ENVIRONMENT', 'local')}")
        logger.info("This is a READ-ONLY Research & Development service")
        logger.info("Purpose: Create shadow variations for strategy analysis")
        logger.info("=" * 60)
        
        # Start all tasks
        tasks = [
            asyncio.create_task(self.process_scans()),
            asyncio.create_task(self.periodic_stats()),
            asyncio.create_task(self.heartbeat())
        ]
        
        try:
            # Wait for all tasks
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Tasks cancelled, shutting down...")
        finally:
            # Final stats
            await self.log_stats()
            logger.info("Shadow Monitor Service stopped")


async def main():
    """Main entry point"""
    # Configure logging
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=os.getenv("LOG_LEVEL", "INFO")
    )
    
    # Check if shadow testing is enabled
    if os.getenv("ENABLE_SHADOW_TESTING", "true").lower() != "true":
        logger.warning("Shadow Testing is disabled via ENABLE_SHADOW_TESTING environment variable")
        logger.info("Set ENABLE_SHADOW_TESTING=true to enable")
        return
    
    # Create and run service
    service = ShadowMonitorService()
    await service.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Service interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
