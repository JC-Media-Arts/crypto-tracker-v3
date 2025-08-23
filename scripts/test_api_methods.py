#!/usr/bin/env python3
"""Test available methods in HummingbotAPIClient"""

import asyncio
from hummingbot_api_client import HummingbotAPIClient
from loguru import logger


async def test_methods():
    """Test and list available methods"""

    # Initialize client
    client = HummingbotAPIClient(host="localhost", port=8000, username="admin", password="admin")

    # Initialize the client
    await client.init()
    logger.info("Client initialized")

    # Get available methods
    methods = [m for m in dir(client) if not m.startswith("_") and callable(getattr(client, m))]
    logger.info(f"Available methods ({len(methods)}):")
    for method in sorted(methods):
        logger.info(f"  - {method}")

    # Test some basic calls
    try:
        # Try to get accounts
        if hasattr(client, "accounts"):
            accounts = client.accounts
            logger.info(f"Accounts property: {accounts}")

        # Try to create an order (method signature)
        if hasattr(client, "create_order"):
            logger.info("✅ create_order method exists")

        # Try to get balances
        if hasattr(client, "balances"):
            balances = client.balances
            logger.info(f"Balances: {balances}")

    except Exception as e:
        logger.error(f"Error testing methods: {e}")

    return client


if __name__ == "__main__":
    asyncio.run(test_methods())
