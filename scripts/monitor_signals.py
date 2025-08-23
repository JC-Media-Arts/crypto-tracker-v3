#!/usr/bin/env python3
"""Monitor the trading system for signals"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from src.data.supabase_client import SupabaseClient
from loguru import logger


async def monitor():
    """Monitor for recent signals and trades"""

    db = SupabaseClient()

    logger.info("=" * 60)
    logger.info("MONITORING TRADING SYSTEM")
    logger.info("=" * 60)

    # Check recent scan history
    try:
        recent_scans = db.client.table("scan_history").select("*").order("timestamp", desc=True).limit(10).execute()

        if recent_scans.data:
            logger.info(f"\n📊 Recent Scans (last 10):")
            for scan in recent_scans.data[:5]:
                logger.info(
                    f"   {scan['timestamp']}: {scan['strategy']} - {scan['symbol']} - {scan.get('decision', 'N/A')}"
                )
        else:
            logger.warning("❌ No recent scans found")

    except Exception as e:
        logger.error(f"Error checking scans: {e}")

    # Check recent trades
    try:
        recent_trades = db.client.table("trade_logs").select("*").order("timestamp", desc=True).limit(10).execute()

        if recent_trades.data:
            logger.info(f"\n💰 Recent Trades (last 10):")
            for trade in recent_trades.data[:5]:
                logger.info(
                    f"   {trade['timestamp']}: {trade['symbol']} - {trade['action']} - ${trade.get('amount', 'N/A')}"
                )
        else:
            logger.info("ℹ️ No trades executed yet")

    except Exception as e:
        logger.info(f"ℹ️ Trade logs table may not exist: {e}")

    # Check data availability
    try:
        btc_data = (
            db.client.table("ohlc_data")
            .select("timestamp, close")
            .eq("symbol", "BTC")
            .eq("timeframe", "15m")
            .order("timestamp", desc=True)
            .limit(5)
            .execute()
        )

        if btc_data.data:
            logger.info(f"\n📈 Latest BTC Data:")
            for d in btc_data.data:
                logger.info(f"   {d['timestamp']}: ${d['close']:,.2f}")
        else:
            logger.warning("❌ No BTC data found")

    except Exception as e:
        logger.error(f"Error checking data: {e}")

    logger.info("\n" + "=" * 60)
    logger.info("Monitor complete. System should be scanning every 60 seconds.")
    logger.info("If no scans appear, check that data is being fetched correctly.")


if __name__ == "__main__":
    asyncio.run(monitor())
