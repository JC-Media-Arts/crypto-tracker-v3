"""
Data collector for crypto prices.
Manages Polygon WebSocket connection and saves data to Supabase.
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Dict
from loguru import logger
from collections import defaultdict

from src.config import get_settings
from src.data.polygon_client import PolygonWebSocketClient
from src.data.supabase_client import SupabaseClient


class DataCollector:
    """Collects real-time crypto data and stores in Supabase."""

    def __init__(self):
        """Initialize the data collector."""
        self.settings = get_settings()
        self.polygon_client = PolygonWebSocketClient(
            on_message_callback=self._on_price_update
        )
        self.db_client = SupabaseClient()

        # Batch processing
        self.price_buffer = []
        self.buffer_size = 100  # Insert in batches of 100
        self.last_db_flush = time.time()
        self.db_flush_interval = 5.0  # Flush every 5 seconds

        # Price tracking for deduplication
        self.last_prices = {}  # symbol -> (price, timestamp)
        self.price_change_threshold = 0.0001  # 0.01% change threshold

        # Stats
        self.stats = defaultdict(int)
        self.start_time = None

    def _on_price_update(self, data: Dict):
        """Handle incoming price updates from Polygon."""
        symbol = data["symbol"]
        price = data["price"]
        timestamp = data["timestamp"]

        # Check if price changed significantly
        if self._should_store_price(symbol, price, timestamp):
            # Add to buffer
            self.price_buffer.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "symbol": symbol,
                    "price": price,
                    "volume": data.get("volume", 0),
                }
            )

            # Update last price
            self.last_prices[symbol] = (price, timestamp)
            self.stats["prices_buffered"] += 1

            # Check if we should flush
            if len(self.price_buffer) >= self.buffer_size:
                self._flush_to_database()

    def _should_store_price(
        self, symbol: str, price: float, timestamp: datetime
    ) -> bool:
        """Determine if price should be stored (avoid storing unchanged prices)."""
        if symbol not in self.last_prices:
            return True

        last_price, last_time = self.last_prices[symbol]

        # Always store if more than 1 minute has passed
        if (timestamp - last_time).total_seconds() > 60:
            return True

        # Store if price changed significantly
        price_change = abs(price - last_price) / last_price
        return price_change > self.price_change_threshold

    def _flush_to_database(self):
        """Flush price buffer to database."""
        if not self.price_buffer:
            return

        try:
            # Insert batch to Supabase
            num_records = len(self.price_buffer)
            self.db_client.insert_price_data(self.price_buffer)

            self.stats["prices_saved"] += num_records
            self.stats["db_flushes"] += 1

            logger.info(f"Saved {num_records} price records to database")

            # Clear buffer
            self.price_buffer.clear()
            self.last_db_flush = time.time()

        except Exception as e:
            # Only count as error if it's not a duplicate key issue
            if "duplicate key value" not in str(e):
                logger.error(f"Failed to save prices to database: {e}")
                self.stats["db_errors"] += 1

                # Keep data in buffer to retry later
                if len(self.price_buffer) > 1000:
                    # Prevent memory issues - keep only recent data
                    self.price_buffer = self.price_buffer[-500:]
            else:
                # Duplicates are normal, just clear the buffer
                self.price_buffer.clear()
                self.last_db_flush = time.time()

    async def _periodic_flush(self):
        """Periodically flush data to database."""
        while True:
            await asyncio.sleep(self.db_flush_interval)

            # Flush if enough time has passed
            if time.time() - self.last_db_flush > self.db_flush_interval:
                self._flush_to_database()

            # Also get any buffered data from Polygon client
            buffered_data = self.polygon_client.get_buffer_data()
            for data in buffered_data:
                self._on_price_update(data)

    async def _periodic_stats(self):
        """Log statistics periodically."""
        while True:
            await asyncio.sleep(60)  # Every minute

            if self.start_time:
                runtime = (datetime.now(timezone.utc) - self.start_time).total_seconds()

                polygon_stats = self.polygon_client.get_stats()

                logger.info(
                    f"Data Collector Stats - "
                    f"Runtime: {runtime/60:.1f}m, "
                    f"Prices Buffered: {self.stats['prices_buffered']}, "
                    f"Prices Saved: {self.stats['prices_saved']}, "
                    f"DB Flushes: {self.stats['db_flushes']}, "
                    f"DB Errors: {self.stats['db_errors']}, "
                    f"Polygon Connected: {polygon_stats['is_connected']}, "
                    f"Polygon Messages: {polygon_stats['messages_received']}"
                )

    async def _health_check(self):
        """Monitor system health and save to database."""
        while True:
            await asyncio.sleep(30)  # Every 30 seconds

            try:
                polygon_stats = self.polygon_client.get_stats()

                # Check if we're receiving data
                if polygon_stats["last_message_time"]:
                    seconds_since_last = (
                        datetime.now(timezone.utc) - polygon_stats["last_message_time"]
                    ).total_seconds()

                    if seconds_since_last > 60:
                        # No data for 1 minute - warning
                        await self.db_client.save_health_metric(
                            "data_flow",
                            "warning" if seconds_since_last < 300 else "critical",
                            seconds_since_last,
                            {
                                "issue": "No data received",
                                "seconds": seconds_since_last,
                            },
                        )
                    else:
                        # Data flowing normally
                        await self.db_client.save_health_metric(
                            "data_flow",
                            "healthy",
                            seconds_since_last,
                            {"status": "Data flowing normally"},
                        )

            except Exception as e:
                logger.error(f"Health check failed: {e}")

    async def start(self):
        """Start data collection."""
        logger.info("Starting data collector")
        self.start_time = datetime.now(timezone.utc)

        # Start Polygon WebSocket
        self.polygon_client.start()

        # Wait a bit for connection
        await asyncio.sleep(2)

        # Start background tasks
        tasks = [
            asyncio.create_task(self._periodic_flush()),
            asyncio.create_task(self._periodic_stats()),
            asyncio.create_task(self._health_check()),
        ]

        try:
            # Run until cancelled
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Data collector shutting down")
            # Final flush
            self._flush_to_database()
            # Stop Polygon client
            self.polygon_client.stop()
            raise

    def get_stats(self) -> Dict:
        """Get collector statistics."""
        polygon_stats = self.polygon_client.get_stats()

        return {
            "collector": dict(self.stats),
            "polygon": polygon_stats,
            "buffer_size": len(self.price_buffer),
            "symbols_tracked": len(self.last_prices),
            "uptime_seconds": (
                (datetime.now(timezone.utc) - self.start_time).total_seconds()
                if self.start_time
                else 0
            ),
        }
