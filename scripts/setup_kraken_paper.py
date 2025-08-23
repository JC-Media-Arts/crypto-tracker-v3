#!/usr/bin/env python3
"""
Set up Kraken paper trading account in Hummingbot API
"""

import asyncio
import aiohttp
import json
from loguru import logger


async def setup_kraken_paper_trading():
    """Set up Kraken paper trading configuration"""

    logger.info("=" * 60)
    logger.info("SETTING UP KRAKEN PAPER TRADING")
    logger.info("=" * 60)

    # API configuration
    base_url = "http://localhost:8000"
    username = "admin"
    password = "admin"  # Change this if you updated it

    async with aiohttp.ClientSession() as session:
        # First, let's authenticate
        auth = aiohttp.BasicAuth(username, password)

        # Test connection
        logger.info("Testing API connection...")
        async with session.get(f"{base_url}/", auth=auth) as resp:
            if resp.status == 200:
                data = await resp.json()
                logger.info(f"✅ Connected to {data['name']} v{data['version']}")
            else:
                logger.error(f"❌ Connection failed: {resp.status}")
                return

        # Check available connectors
        logger.info("\nChecking available connectors...")
        async with session.get(f"{base_url}/connectors", auth=auth) as resp:
            if resp.status == 200:
                connectors = await resp.json()
                # Check if kraken is available
                kraken_connectors = [c for c in connectors if "kraken" in c.lower()]
                if kraken_connectors:
                    logger.info(f"✅ Found Kraken connectors: {kraken_connectors[:3]}")
                else:
                    logger.warning("⚠️ No Kraken connectors found in available list")
            else:
                logger.warning(f"Could not get connectors: {resp.status}")

        # Create a Kraken paper trading account
        logger.info("\nSetting up Kraken paper trading account...")

        # For paper trading, we don't need real API keys
        account_data = {
            "name": "kraken_paper",
            "connector": "kraken",
            "paper_trade": True,
            "config": {
                "kraken_api_key": "PAPER_TRADING_KEY",
                "kraken_api_secret": "PAPER_TRADING_SECRET",
            },
        }

        async with session.post(f"{base_url}/accounts", auth=auth, json=account_data) as resp:
            if resp.status in [200, 201]:
                logger.info("✅ Kraken paper trading account created!")
            elif resp.status == 409:
                logger.info("ℹ️ Kraken paper trading account already exists")
            else:
                text = await resp.text()
                logger.warning(f"Account creation response ({resp.status}): {text}")

        # Get current accounts
        logger.info("\nChecking configured accounts...")
        async with session.get(f"{base_url}/accounts", auth=auth) as resp:
            if resp.status == 200:
                accounts = await resp.json()
                if accounts:
                    logger.info(f"✅ Found {len(accounts)} configured accounts:")
                    for acc in accounts:
                        if isinstance(acc, dict):
                            logger.info(f"   - {acc.get('name', 'Unknown')}")
                        else:
                            logger.info(f"   - {acc}")
                else:
                    logger.info("ℹ️ No accounts configured yet")
            else:
                logger.warning(f"Could not get accounts: {resp.status}")

        # Test market data access
        logger.info("\nTesting market data access...")
        async with session.get(
            f"{base_url}/market-data/ticker/BTC-USD",
            auth=auth,
            params={"connector": "kraken"},
        ) as resp:
            if resp.status == 200:
                ticker = await resp.json()
                logger.info(f"✅ Market data working! BTC-USD: ${ticker.get('last', 'N/A')}")
            else:
                logger.info(f"ℹ️ Market data endpoint returned: {resp.status}")

        logger.info("\n" + "=" * 60)
        logger.info("SETUP COMPLETE!")
        logger.info("=" * 60)
        logger.info("\nYou can now:")
        logger.info("1. Access the dashboard at http://localhost:8501")
        logger.info("2. Run the simplified trading system")
        logger.info("3. Monitor for signals and paper trades")

        return True


if __name__ == "__main__":
    try:
        asyncio.run(setup_kraken_paper_trading())
    except Exception as e:
        logger.error(f"Setup failed: {e}")
        import traceback

        traceback.print_exc()
