#!/usr/bin/env python3
"""
Check Polygon.io account limits and capabilities
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from src.config.settings import Settings

settings = Settings()
from loguru import logger


def check_polygon_account():
    """Check Polygon account status and limits"""
    api_key = settings.polygon_api_key

    # Check account status
    url = f"https://api.polygon.io/v1/meta/conditions/{api_key}"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            logger.info("✅ Polygon API key is valid")
        else:
            logger.error(f"❌ Polygon API response: {response.status_code}")
            logger.error(f"Response: {response.text}")
    except Exception as e:
        logger.error(f"Failed to check Polygon account: {e}")

    # Get a sample quote to verify crypto access
    symbol_url = f"https://api.polygon.io/v2/aggs/ticker/X:BTCUSD/prev?apiKey={api_key}"

    try:
        response = requests.get(symbol_url)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "OK":
                logger.info("✅ Crypto data access confirmed")
                logger.info(f"Sample BTC price: ${data['results'][0]['c']:,.2f}")
            else:
                logger.error(f"❌ Crypto data error: {data}")
        else:
            logger.error(f"❌ Failed to get crypto data: {response.status_code}")
    except Exception as e:
        logger.error(f"Failed to get crypto quote: {e}")

    logger.info("\n📋 Polygon.io Currencies Starter Plan Limits:")
    logger.info("- Price: $49/month")
    logger.info("- WebSocket: 1 concurrent connection")
    logger.info("- Symbols per connection: Varies by data volume")
    logger.info("- Recommended: Start with 10-20 symbols, monitor stability")
    logger.info("\n💡 To subscribe to more symbols:")
    logger.info("1. Test incrementally (10 → 20 → 40 symbols)")
    logger.info("2. Monitor for disconnections")
    logger.info("3. Consider upgrading plan if needed")


if __name__ == "__main__":
    check_polygon_account()
