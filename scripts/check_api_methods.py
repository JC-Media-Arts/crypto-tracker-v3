#!/usr/bin/env python3
"""Check actual Hummingbot API client methods"""

import asyncio
from hummingbot_api_client import HummingbotAPIClient
import inspect


async def check():
    client = HummingbotAPIClient(base_url="http://localhost:8000", username="admin", password="admin")

    # Initialize
    await client.init()

    # Get all methods
    methods = [m for m in dir(client) if not m.startswith("_")]

    print("Available methods:")
    for method in sorted(methods):
        print(f"  - {method}")

    # Check for order-related methods
    order_methods = [
        m for m in methods if "order" in m.lower() or "trade" in m.lower() or "buy" in m.lower() or "sell" in m.lower()
    ]
    print(f"\nOrder-related methods: {order_methods}")

    # Check if it has a post method for direct API calls
    if hasattr(client, "post"):
        print("\n✅ Has 'post' method for direct API calls")

    # Close the session properly
    if hasattr(client, "session"):
        await client.session.close()


asyncio.run(check())
