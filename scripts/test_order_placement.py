#!/usr/bin/env python3
"""Test the correct way to place orders"""

import asyncio
from hummingbot_api_client import HummingbotAPIClient
import inspect


async def test():
    client = HummingbotAPIClient(base_url="http://localhost:8000", username="admin", password="admin")

    await client.init()

    # Check the place_order signature
    if hasattr(client.trading, "place_order"):
        sig = inspect.signature(client.trading.place_order)
        print("place_order signature:")
        print(f"  {sig}")

        # Get parameter names
        params = sig.parameters
        print("\nParameters:")
        for name, param in params.items():
            print(f"  - {name}: {param.annotation if param.annotation != inspect.Parameter.empty else 'Any'}")

    # Try to check what bots are available
    if hasattr(client, "bot_orchestration"):
        try:
            bots = await client.bot_orchestration.get_bots()
            print(f"\nAvailable bots: {bots}")
        except Exception as e:
            print(f"\nCouldn't get bots: {e}")


asyncio.run(test())
