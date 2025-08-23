"""
Singleton WebSocket Manager to ensure only ONE connection to Polygon.
Prevents "Maximum number of websocket connections exceeded" error.
"""

import asyncio
import websockets
import json
import os
from typing import Optional, Set, Dict, Any
from datetime import datetime, timezone
import signal
import sys
from loguru import logger


class SingletonWebSocket:
    """Ensures only ONE WebSocket connection exists globally"""

    _instance: Optional["SingletonWebSocket"] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "initialized"):
            self.connection = None
            self.subscribed_symbols: Set[str] = set()
            self.is_running = False
            self.initialized = True
            self.reconnect_attempts = 0
            self.max_reconnect_attempts = 5
            self.setup_signal_handlers()
            logger.info("SingletonWebSocket initialized")

    def setup_signal_handlers(self):
        """Ensure connection closes on exit"""

        def cleanup(signum, frame):
            logger.info("🛑 Shutting down WebSocket connection...")
            if self.connection:
                asyncio.create_task(self.disconnect())
            sys.exit(0)

        signal.signal(signal.SIGINT, cleanup)
        signal.signal(signal.SIGTERM, cleanup)

    async def connect(self) -> bool:
        """Connect to Polygon WebSocket (only if not already connected)"""
        async with self._lock:
            # Check if already connected
            if self.connection and not self.connection.closed:
                logger.info("✅ Using existing WebSocket connection")
                return True

            # Close any existing connection first
            if self.connection:
                try:
                    await self.connection.close()
                    logger.info("Closed previous connection")
                except:
                    pass
                self.connection = None

            try:
                logger.info("🔄 Creating new WebSocket connection...")

                # Single connection for everything
                self.connection = await websockets.connect(
                    "wss://socket.polygon.io/crypto",
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10,
                )

                # Authenticate
                api_key = os.getenv("POLYGON_API_KEY")
                if not api_key:
                    logger.error("POLYGON_API_KEY not found in environment")
                    return False

                auth_msg = {"action": "auth", "params": api_key}
                await self.connection.send(json.dumps(auth_msg))

                # Wait for auth response
                response = await self.connection.recv()
                auth_data = json.loads(response)

                if auth_data[0]["status"] == "auth_success":
                    logger.info("✅ WebSocket authenticated successfully")
                    self.is_running = True
                    self.reconnect_attempts = 0

                    # Re-subscribe to any previously subscribed symbols
                    if self.subscribed_symbols:
                        await self._resubscribe()

                    return True
                else:
                    logger.error(f"❌ Authentication failed: {auth_data}")
                    return False

            except Exception as e:
                logger.error(f"❌ Connection failed: {e}")
                self.connection = None
                self.reconnect_attempts += 1

                if self.reconnect_attempts < self.max_reconnect_attempts:
                    wait_time = min(60, 5 * self.reconnect_attempts)
                    logger.info(f"Retrying in {wait_time} seconds... (attempt {self.reconnect_attempts})")
                    await asyncio.sleep(wait_time)
                    return await self.connect()
                else:
                    logger.error("Max reconnection attempts reached")
                    return False

    async def subscribe(self, symbols: list) -> bool:
        """Subscribe to symbols through the single connection"""
        if not self.connection or self.connection.closed:
            if not await self.connect():
                return False

        # Filter out already subscribed symbols
        new_symbols = [s for s in symbols if s not in self.subscribed_symbols]

        if not new_symbols:
            logger.info(f"ℹ️ All {len(symbols)} symbols already subscribed")
            return True

        # Polygon allows subscribing to multiple symbols at once
        # But we should batch them to avoid overwhelming the connection
        batch_size = 20
        for i in range(0, len(new_symbols), batch_size):
            batch = new_symbols[i : i + batch_size]
            subscribe_msg = {
                "action": "subscribe",
                "params": ",".join([f"XA.{symbol}-USD" for symbol in batch]),
            }

            try:
                await self.connection.send(json.dumps(subscribe_msg))
                self.subscribed_symbols.update(batch)
                logger.info(f"✅ Subscribed to {len(batch)} symbols (Total: {len(self.subscribed_symbols)})")
                await asyncio.sleep(0.1)  # Small delay between batches
            except Exception as e:
                logger.error(f"❌ Subscribe failed: {e}")
                return False

        return True

    async def _resubscribe(self):
        """Re-subscribe to all symbols after reconnection"""
        if self.subscribed_symbols:
            logger.info(f"Re-subscribing to {len(self.subscribed_symbols)} symbols...")
            symbols_list = list(self.subscribed_symbols)
            self.subscribed_symbols.clear()  # Clear to allow resubscription
            await self.subscribe(symbols_list)

    async def disconnect(self):
        """Properly close the WebSocket connection"""
        if self.connection:
            try:
                await self.connection.close()
                logger.info("✅ WebSocket connection closed cleanly")
            except:
                pass
            finally:
                self.connection = None
                self.is_running = False

    async def receive_data(self):
        """Receive data from the single connection"""
        if not self.connection:
            return None

        try:
            data = await self.connection.recv()
            return json.loads(data)
        except websockets.ConnectionClosed:
            logger.warning("⚠️ Connection closed, attempting reconnect...")
            self.connection = None
            await self.connect()
            return None
        except Exception as e:
            logger.error(f"❌ Error receiving data: {e}")
            return None

    @classmethod
    def get_instance(cls) -> "SingletonWebSocket":
        """Get the singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


# Global singleton instance
websocket_manager = SingletonWebSocket()
