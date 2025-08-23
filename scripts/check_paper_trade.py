#!/usr/bin/env python3
"""Check if kraken_paper_trade connector is available"""

import asyncio
import os
from hummingbot_api_client import HummingbotAPIClient
from loguru import logger


async def check():
    """Check paper trade connectors"""

    # Initialize client
    base_url = os.getenv("HUMMINGBOT_API_URL", "http://localhost:8000")
    username = os.getenv("HUMMINGBOT_USERNAME", "admin")
    password = os.getenv("HUMMINGBOT_PASSWORD", "admin")

    client = HummingbotAPIClient(base_url, username, password)

    try:
        await client.init()

        # Try to place a test order with kraken_paper_trade
        logger.info("Testing kraken_paper_trade connector...")

        # Just try to see if the connector is recognized
        # We'll use a dummy order that should fail but tell us if connector exists
        try:
            result = await client.trading.place_order(
                account_name="master_account",
                connector_name="kraken_paper_trade",
                trading_pair="BTC-USDT",
                trade_type="BUY",
                amount=0.0001,
                order_type="MARKET",
                price=None,
            )
            logger.info(f"Order result: {result}")
        except Exception as e:
            logger.info(f"Order attempt response: {e}")
            # Check if error mentions connector not found vs other errors
            if "not found" in str(e).lower():
                logger.error("❌ kraken_paper_trade connector NOT available")
            else:
                logger.success(
                    "✅ kraken_paper_trade connector seems available (got different error)"
                )

    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(check())
