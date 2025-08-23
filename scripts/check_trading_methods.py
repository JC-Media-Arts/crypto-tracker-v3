#!/usr/bin/env python3
"""Check trading methods in Hummingbot API"""

import asyncio
from hummingbot_api_client import HummingbotAPIClient

async def check():
    client = HummingbotAPIClient(
        base_url="http://localhost:8000",
        username="admin",
        password="admin"
    )
    
    await client.init()
    
    # Check trading object
    if hasattr(client, 'trading'):
        trading = client.trading
        print("Trading methods:")
        methods = [m for m in dir(trading) if not m.startswith('_')]
        for method in sorted(methods):
            print(f"  - {method}")
        
        # Try to get method signatures
        if hasattr(trading, 'create_order'):
            print("\n✅ Has create_order method!")
        if hasattr(trading, 'start'):
            print("✅ Has start method!")
        if hasattr(trading, 'stop'):
            print("✅ Has stop method!")
    
    # Also check if we can make direct POST calls
    print("\n\nDirect API call test:")
    try:
        # Try to get active orders (safe read-only operation)
        response = await client.session.get(
            f"{client.base_url}/bots/orders",
            auth=client.auth
        )
        print(f"Direct API call status: {response.status}")
        
        # Show the create order endpoint
        print("\nTo create orders, POST to: /bots/{bot_name}/orders")
        print("Payload format: {")
        print('  "market": "kraken",')
        print('  "trading_pair": "BTC-USD",')
        print('  "order_type": "market",')
        print('  "side": "buy",')
        print('  "amount": "0.001",')
        print('  "price": null  // for market orders')
        print("}")
        
    except Exception as e:
        print(f"Error: {e}")
    
    await client.session.close()

asyncio.run(check())
