"""
Polygon.io WebSocket client for real-time crypto data.
Handles connection, reconnection, and data streaming.
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable
from collections import deque
import websocket
import threading
from loguru import logger

from src.config import get_settings


class PolygonWebSocketClient:
    """Handles real-time crypto data from Polygon.io WebSocket."""

    def __init__(self, on_message_callback: Optional[Callable] = None):
        """Initialize the WebSocket client."""
        self.settings = get_settings()
        self.ws_url = "wss://socket.polygon.io/crypto"
        self.ws = None
        self.is_running = False
        self.reconnect_delay = 5  # seconds
        self.max_reconnect_delay = 300  # 5 minutes
        self.reconnect_attempts = 0
        self.on_message_callback = on_message_callback

        # Supported symbols from MASTER_PLAN.md
        self.symbols = self._get_supported_symbols()

        # Message buffer for batch processing
        self.message_buffer = deque(maxlen=1000)
        self.last_flush_time = time.time()
        self.flush_interval = 1.0  # Flush every second

        # Stats tracking
        self.stats = {
            "messages_received": 0,
            "messages_processed": 0,
            "connection_errors": 0,
            "last_message_time": None,
            "connected_since": None,
        }

    def _get_supported_symbols(self) -> List[str]:
        """Get list of supported symbols from config."""
        # Tier 1: Core coins (20)
        tier1 = [
            "BTC",
            "ETH",
            "SOL",
            "BNB",
            "XRP",
            "ADA",
            "AVAX",
            "DOGE",
            "DOT",
            "POL",
            "LINK",
            "TON",
            "SHIB",
            "TRX",
            "UNI",
            "ATOM",
            "BCH",
            "APT",
            "NEAR",
            "ICP",
        ]

        # Tier 2: DeFi/Layer 2 (20)
        tier2 = [
            "ARB",
            "OP",
            "AAVE",
            "CRV",
            "MKR",
            "LDO",
            "SUSHI",
            "COMP",
            "SNX",
            "BAL",
            "INJ",
            "SEI",
            "PENDLE",
            "BLUR",
            "ENS",
            "GRT",
            "RENDER",
            "FET",
            "RPL",
            "SAND",
        ]

        # Tier 3: Trending/Memecoins (20)
        tier3 = [
            "PEPE",
            "WIF",
            "BONK",
            "FLOKI",
            "MEME",
            "POPCAT",
            "MEW",
            "TURBO",
            "NEIRO",
            "PNUT",
            "GOAT",
            "ACT",
            "TRUMP",
            "FARTCOIN",
            "MOG",
            "PONKE",
            "TREMP",
            "BRETT",
            "GIGA",
            "HIPPO",
        ]

        # Tier 4: Solid Mid-Caps (40)
        tier4 = [
            "FIL",
            "RUNE",
            "IMX",
            "FLOW",
            "MANA",
            "AXS",
            "CHZ",
            "GALA",
            "LRC",
            "OCEAN",
            "QNT",
            "ALGO",
            "XLM",
            "XMR",
            "ZEC",
            "DASH",
            "HBAR",
            "VET",
            "THETA",
            "EOS",
            "KSM",
            "STX",
            "KAS",
            "TIA",
            "JTO",
            "JUP",
            "PYTH",
            "DYM",
            "STRK",
            "ALT",
            "PORTAL",
            "BEAM",
            "MASK",
            "API3",
            "ANKR",
            "CTSI",
            "YFI",
            "AUDIO",
            "ENJ",
        ]

        # Note: BLUR appears in both Tier 2 and Tier 4 in the master plan, keeping it in Tier 2 only

        # Combine all tiers and remove duplicates
        all_symbols = list(set(tier1 + tier2 + tier3 + tier4))
        all_symbols.sort()  # Sort alphabetically for consistency

        logger.info(f"Subscribing to ALL {len(all_symbols)} crypto symbols")
        logger.info(
            "Polygon confirmed: no symbol limit within a single WebSocket connection"
        )
        return all_symbols

    def _on_open(self, ws):
        """Handle WebSocket connection open."""
        logger.info("WebSocket connection opened")
        self.stats["connected_since"] = datetime.now(timezone.utc)
        self.reconnect_attempts = 0

        # Authenticate
        auth_message = {"action": "auth", "params": self.settings.polygon_api_key}
        ws.send(json.dumps(auth_message))

        # Wait a bit for authentication to complete
        time.sleep(1)

        # Subscribe to all symbols in one message as Polygon recommends
        # Format: "XA.BTC-USD,XA.ETH-USD,..."
        subscriptions = ",".join([f"XA.{symbol}-USD" for symbol in self.symbols])

        subscribe_message = {"action": "subscribe", "params": subscriptions}

        try:
            ws.send(json.dumps(subscribe_message))
            logger.info(
                f"Subscribed to {len(self.symbols)} symbols: {', '.join(self.symbols)}"
            )
        except Exception as e:
            logger.error(f"Failed to subscribe: {e}")

    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(message)

            # Handle different message types
            if isinstance(data, list):
                for msg in data:
                    self._process_message(msg)
            else:
                self._process_message(data)

            self.stats["messages_received"] += 1
            self.stats["last_message_time"] = datetime.now(timezone.utc)

            # Check if we should flush the buffer
            if time.time() - self.last_flush_time > self.flush_interval:
                self._flush_buffer()

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def _process_message(self, msg: Dict):
        """Process individual message."""
        if msg.get("ev") == "XA":  # Crypto aggregate
            # Extract relevant data
            processed_data = {
                "timestamp": datetime.fromtimestamp(msg["s"] / 1000, tz=timezone.utc),
                "symbol": msg["pair"].replace("-USD", ""),
                "price": float(msg["c"]),  # Close price
                "volume": float(msg["v"]),  # Volume
                "high": float(msg["h"]),
                "low": float(msg["l"]),
                "open": float(msg["o"]),
                "vwap": float(msg.get("vw", 0)),  # Volume weighted average
                "trades": msg.get("z", 0),  # Number of trades
            }

            # Add to buffer
            self.message_buffer.append(processed_data)

            # Call callback if provided
            if self.on_message_callback:
                self.on_message_callback(processed_data)

        elif msg.get("status") == "auth_success":
            logger.info("Successfully authenticated with Polygon")
        elif msg.get("status") == "error":
            error_msg = msg.get("message", "Unknown error")
            logger.error(f"Polygon error: {error_msg}")
            if "Maximum number of websocket connections exceeded" in error_msg:
                logger.error(
                    "Connection limit reached! Check for other running instances."
                )
        elif msg.get("message"):
            # Log any messages from Polygon
            logger.info(f"Polygon message: {msg.get('message')}")

    def _flush_buffer(self):
        """Flush message buffer - to be implemented by data collector."""
        if not self.message_buffer:
            return

        # This will be called by the DataCollector to save to database
        buffer_copy = list(self.message_buffer)
        self.message_buffer.clear()
        self.last_flush_time = time.time()

        logger.debug(f"Flushing {len(buffer_copy)} messages from buffer")
        # The DataCollector will handle the actual database insertion

    def _on_error(self, ws, error):
        """Handle WebSocket errors."""
        logger.error(f"WebSocket error: {error}")
        self.stats["connection_errors"] += 1

    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close."""
        logger.warning(f"WebSocket closed: {close_status_code} - {close_msg}")
        self.stats["connected_since"] = None

        if self.is_running:
            # Attempt to reconnect
            self._schedule_reconnect()

    def _schedule_reconnect(self):
        """Schedule a reconnection attempt."""
        self.reconnect_attempts += 1
        # Start with 5 seconds, then 10, 20, 40, etc. up to 5 minutes
        delay = min(
            self.reconnect_delay * (2 ** (self.reconnect_attempts - 1)),
            self.max_reconnect_delay,
        )

        logger.info(
            f"Reconnecting in {delay} seconds... (attempt {self.reconnect_attempts})"
        )
        time.sleep(delay)

        if self.is_running:
            self.connect()

    def connect(self):
        """Connect to Polygon WebSocket."""
        try:
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
            )

            # Run in a separate thread
            wst = threading.Thread(target=self.ws.run_forever)
            wst.daemon = True
            wst.start()

            logger.info("WebSocket client started")

        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            if self.is_running:
                self._schedule_reconnect()

    def start(self):
        """Start the WebSocket client."""
        logger.info("Starting Polygon WebSocket client")
        self.is_running = True
        self.connect()

    def stop(self):
        """Stop the WebSocket client."""
        logger.info("Stopping Polygon WebSocket client")
        self.is_running = False
        if self.ws:
            self.ws.close()

    def get_stats(self) -> Dict:
        """Get client statistics."""
        return {
            **self.stats,
            "buffer_size": len(self.message_buffer),
            "is_connected": self.ws is not None
            and self.stats["connected_since"] is not None,
        }

    def get_buffer_data(self) -> List[Dict]:
        """Get and clear the message buffer."""
        data = list(self.message_buffer)
        self.message_buffer.clear()
        return data
