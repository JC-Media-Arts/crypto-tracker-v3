#!/usr/bin/env python3
"""
Test Polygon WebSocket symbol subscription limits
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import websocket
import json
import time
from loguru import logger
from src.config.settings import Settings

settings = Settings()


class SymbolLimitTester:
    def __init__(self):
        self.api_key = settings.polygon_api_key
        self.ws_url = "wss://socket.polygon.io/crypto"
        self.connected = False
        self.message_count = 0
        self.start_time = None
        self.symbols_to_test = []

    def test_incremental_symbols(self):
        """Test with increasing number of symbols"""
        # All 100 symbols from the master plan
        all_symbols = [
            # Tier 1
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
            # Tier 2
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
            # Tier 3
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
            # Tier 4
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

        # Test different symbol counts
        test_counts = [10, 20, 40, 60, 80, 100]

        for count in test_counts:
            logger.info(f"\n{'='*50}")
            logger.info(f"Testing with {count} symbols")
            logger.info(f"{'='*50}")

            self.symbols_to_test = all_symbols[:count]
            self.message_count = 0
            self.start_time = time.time()

            try:
                ws = websocket.WebSocketApp(
                    self.ws_url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )

                # Run for 30 seconds
                ws.run_forever(ping_interval=30, ping_timeout=10)

            except Exception as e:
                logger.error(f"Test failed with {count} symbols: {e}")

            # Wait between tests
            logger.info("Waiting 30 seconds before next test...")
            time.sleep(30)

    def _on_open(self, ws):
        """Handle connection open"""
        logger.info("WebSocket connection opened")

        # Authenticate
        auth_message = {"action": "auth", "params": self.api_key}
        ws.send(json.dumps(auth_message))

        # Subscribe to symbols
        subscriptions = ",".join([f"XA.{symbol}-USD" for symbol in self.symbols_to_test])
        subscribe_message = {"action": "subscribe", "params": subscriptions}

        ws.send(json.dumps(subscribe_message))
        logger.info(f"Subscribed to {len(self.symbols_to_test)} symbols")

        # Schedule disconnect after 20 seconds
        def disconnect():
            time.sleep(20)
            logger.info("Test complete, closing connection")
            ws.close()

        import threading

        threading.Thread(target=disconnect).start()

    def _on_message(self, ws, message):
        """Handle incoming messages"""
        self.message_count += 1

        try:
            data = json.loads(message)

            if isinstance(data, list):
                # Multiple messages
                for msg in data:
                    if msg.get("ev") == "XA":
                        # This is a price update
                        pass
            else:
                # Single message
                if data.get("status") == "auth_success":
                    logger.info("Authentication successful")
                elif data.get("status") == "error":
                    logger.error(f"Error: {data.get('message')}")
                elif "subscribed to" in data.get("message", ""):
                    # Count subscriptions
                    pass

        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def _on_error(self, ws, error):
        """Handle errors"""
        logger.error(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        """Handle connection close"""
        duration = time.time() - self.start_time if self.start_time else 0
        logger.info(f"Connection closed after {duration:.1f}s")
        logger.info(f"Received {self.message_count} messages")
        logger.info(f"Average: {self.message_count/duration:.1f} messages/second")

        if close_status_code == 1008:
            logger.warning("Closed with code 1008 - likely hit a limit")


if __name__ == "__main__":
    tester = SymbolLimitTester()
    tester.test_incremental_symbols()
