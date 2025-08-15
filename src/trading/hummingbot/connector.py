"""
Connector module for Hummingbot integration.
Handles communication between ML system and Hummingbot.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from loguru import logger

from src.config import Settings
from src.data.supabase_client import SupabaseClient


class HummingbotConnector:
    """Connects ML predictions to Hummingbot strategies."""

    def __init__(self, settings: Settings):
        """Initialize Hummingbot connector."""
        self.settings = settings
        self.db_client: Optional[SupabaseClient] = None
        self.signal_file = Path("hummingbot/data/ml_signals.json")
        self.running = False

    async def initialize(self):
        """Initialize the connector."""
        logger.info("Initializing Hummingbot connector...")

        # Initialize database client
        self.db_client = SupabaseClient(self.settings)
        await self.db_client.initialize()

        # Ensure signal file directory exists
        self.signal_file.parent.mkdir(parents=True, exist_ok=True)

        logger.success("Hummingbot connector initialized")

    async def start(self):
        """Start monitoring for ML signals."""
        logger.info("Starting Hummingbot signal monitor...")
        self.running = True

        # Start signal monitoring loop
        asyncio.create_task(self._signal_loop())

    async def _signal_loop(self):
        """Main loop to fetch ML predictions and write signals."""
        while self.running:
            try:
                # Get latest ML predictions
                signals = await self._get_ml_signals()

                if signals:
                    # Write signals to file for Hummingbot to read
                    await self._write_signals(signals)
                    logger.info(f"Wrote {len(signals)} signals to Hummingbot")

                # Wait before next check
                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception as e:
                logger.error(f"Error in signal loop: {e}")
                await asyncio.sleep(60)

    async def _get_ml_signals(self) -> List[Dict]:
        """Fetch latest ML predictions from database."""
        try:
            # Query for recent predictions with high confidence
            # This is a placeholder - implement actual query
            signals = []

            # Get predictions from last 5 minutes with confidence > 60%
            # signals = await self.db_client.get_recent_predictions(
            #     minutes=5,
            #     min_confidence=0.60
            # )

            return signals

        except Exception as e:
            logger.error(f"Failed to get ML signals: {e}")
            return []

    async def _write_signals(self, signals: List[Dict]):
        """Write signals to file for Hummingbot."""
        try:
            # Format signals for Hummingbot
            formatted_signals = {
                "timestamp": datetime.utcnow().isoformat(),
                "signals": [],
            }

            for signal in signals:
                formatted_signals["signals"].append(
                    {
                        "symbol": signal["symbol"],
                        "action": signal["prediction"],  # UP or DOWN
                        "confidence": signal["confidence"],
                        "timestamp": signal["timestamp"],
                    }
                )

            # Write to file
            with open(self.signal_file, "w") as f:
                json.dump(formatted_signals, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to write signals: {e}")

    async def stop(self):
        """Stop the connector."""
        logger.info("Stopping Hummingbot connector...")
        self.running = False
