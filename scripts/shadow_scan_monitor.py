#!/usr/bin/env python3
"""
Shadow Scan Monitor
Monitors scan_history table and creates shadow variations for new scans
This is a temporary solution until full integration is complete
"""

import asyncio
import sys
from datetime import datetime, timedelta
from loguru import logger

sys.path.append(".")

from src.data.supabase_client import SupabaseClient
from src.analysis.shadow_logger import ShadowLogger


class ShadowScanMonitor:
    """Monitors scans and creates shadow variations"""

    def __init__(self):
        self.supabase_client = SupabaseClient()
        self.shadow_logger = ShadowLogger(self.supabase_client)
        self.last_scan_id = None

    async def get_unprocessed_scans(self):
        """Get scans that don't have shadow variations yet"""
        try:
            # Get recent scans (last 10 minutes)
            cutoff = (datetime.utcnow() - timedelta(minutes=10)).isoformat()

            # Get all recent scans
            scans_result = (
                self.supabase_client.client.table("scan_history")
                .select("*")
                .gte("timestamp", cutoff)
                .order("scan_id", desc=False)
                .execute()
            )

            if not scans_result.data:
                return []

            scan_ids = [s["scan_id"] for s in scans_result.data]

            # Check which ones already have shadows
            shadows_result = (
                self.supabase_client.client.table("shadow_variations")
                .select("scan_id")
                .in_("scan_id", scan_ids)
                .execute()
            )

            processed_ids = (
                {s["scan_id"] for s in shadows_result.data}
                if shadows_result.data
                else set()
            )

            # Return unprocessed scans
            unprocessed = [
                s for s in scans_result.data if s["scan_id"] not in processed_ids
            ]

            if unprocessed:
                logger.info(f"Found {len(unprocessed)} unprocessed scans")

            return unprocessed

        except Exception as e:
            logger.error(f"Error getting unprocessed scans: {e}")
            return []

    async def create_shadows_for_scan(self, scan):
        """Create shadow variations for a single scan"""
        try:
            # Parse features and predictions
            import json

            features = (
                json.loads(scan.get("features", "{}")) if scan.get("features") else {}
            )
            ml_predictions = (
                json.loads(scan.get("ml_predictions", "{}"))
                if scan.get("ml_predictions")
                else {}
            )

            # Get current price from features
            current_price = features.get("close", 0)

            # Base parameters (use defaults)
            base_parameters = {
                "confidence_threshold": 0.60,
                "position_size_multiplier": 1.0,
                "stop_loss": 0.05,
                "take_profit": ml_predictions.get("take_profit", 0.10),
            }

            # Log shadow decisions
            # Ensure ml_confidence is never None
            ml_confidence = scan.get("ml_confidence")
            if ml_confidence is None:
                ml_confidence = 0.0

            await self.shadow_logger.log_shadow_decisions(
                scan_id=scan["scan_id"],
                symbol=scan["symbol"],
                strategy_name=scan["strategy_name"],
                features=features,
                ml_predictions=ml_predictions,
                ml_confidence=float(ml_confidence),
                current_price=current_price,
                base_parameters=base_parameters,
            )

            logger.debug(
                f"Created shadows for scan {scan['scan_id']} - {scan['symbol']} {scan['strategy_name']}"
            )

        except Exception as e:
            logger.error(f"Error creating shadows for scan {scan['scan_id']}: {e}")

    async def monitor_loop(self):
        """Main monitoring loop"""
        logger.info("Starting Shadow Scan Monitor")
        logger.info("Will check for new scans every 30 seconds")

        while True:
            try:
                # Get unprocessed scans
                unprocessed = await self.get_unprocessed_scans()

                # Create shadows for each
                for scan in unprocessed:
                    await self.create_shadows_for_scan(scan)
                    await asyncio.sleep(0.1)  # Small delay between scans

                # Flush any pending shadows
                if self.shadow_logger.batch:
                    count = len(self.shadow_logger.batch)
                    logger.info(f"About to flush {count} shadow variations")
                    await self.shadow_logger.flush()
                    logger.info(f"Flushed {count} shadow variations")
                else:
                    logger.debug("No shadows to flush")

            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")

            # Wait before next check
            await asyncio.sleep(30)

    async def run(self):
        """Run the monitor"""
        try:
            await self.monitor_loop()
        except KeyboardInterrupt:
            logger.info("Shadow Scan Monitor stopped by user")
        except Exception as e:
            logger.error(f"Fatal error: {e}")


async def main():
    """Main entry point"""
    monitor = ShadowScanMonitor()
    await monitor.run()


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("SHADOW SCAN MONITOR")
    logger.info("Monitoring scan_history and creating shadow variations")
    logger.info("=" * 60)

    asyncio.run(main())
