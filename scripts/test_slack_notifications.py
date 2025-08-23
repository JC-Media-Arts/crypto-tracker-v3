#!/usr/bin/env python3
"""
Test Slack Notifications for Paper Trading System
Sends test messages to each configured channel
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from loguru import logger

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.notifications.paper_trading_notifier import PaperTradingNotifier


async def test_notifications():
    """Test all notification types"""

    logger.info("=" * 80)
    logger.info("🧪 TESTING SLACK NOTIFICATIONS")
    logger.info("=" * 80)

    # Initialize notifier
    notifier = PaperTradingNotifier()

    if not notifier.enabled:
        logger.error("❌ No Slack webhooks configured!")
        logger.info("Run: bash scripts/setup_slack_webhooks.sh")
        return False

    logger.info("Configured channels:")
    for channel, url in notifier.webhook_urls.items():
        if url:
            logger.info(f"  ✅ {channel}: Configured")
        else:
            logger.info(f"  ❌ {channel}: Not configured")

    print("\n")

    # Test 1: Position Opened (goes to #trades)
    logger.info("Test 1: Sending position opened notification to #trades...")
    await notifier.notify_position_opened(
        symbol="BTC",
        strategy="swing",
        entry_price=43250.50,
        position_size=50.0,
        stop_loss=41087.98,
        take_profit=45412.53,
        trailing_stop_pct=0.02,
        market_cap_tier="large_cap",
    )
    logger.info("✅ Position opened notification sent")

    await asyncio.sleep(1)

    # Test 2: Position Closed - Win (goes to #trades)
    logger.info("\nTest 2: Sending winning position closed notification to #trades...")
    await notifier.notify_position_closed(
        symbol="ETH",
        strategy="dca",
        entry_price=2250.00,
        exit_price=2340.00,
        pnl_usd=45.00,
        pnl_percent=4.0,
        exit_reason="take_profit",
        duration_hours=18.5,
        highest_price=2350.00,
    )
    logger.info("✅ Winning position closed notification sent")

    await asyncio.sleep(1)

    # Test 3: Position Closed - Loss with trailing stop (goes to #trades)
    logger.info("\nTest 3: Sending losing position closed (trailing stop) notification to #trades...")
    await notifier.notify_position_closed(
        symbol="SOL",
        strategy="channel",
        entry_price=95.50,
        exit_price=92.00,
        pnl_usd=-17.50,
        pnl_percent=-3.66,
        exit_reason="trailing_stop",
        duration_hours=6.2,
        highest_price=98.75,
    )
    logger.info("✅ Losing position closed notification sent")

    await asyncio.sleep(1)

    # Test 4: Daily Report (goes to #reports)
    logger.info("\nTest 4: Sending daily report to #reports...")

    test_stats = {
        "balance": 985.50,
        "positions": 3,
        "positions_value": 150.00,
        "total_value": 1135.50,
        "total_pnl": 135.50,
        "total_pnl_pct": 13.55,
        "total_trades": 25,
        "winning_trades": 18,
        "win_rate": 72.0,
        "total_fees": 8.45,
        "total_slippage": 3.20,
        "max_positions": 30,
    }

    test_trades_today = [
        {
            "symbol": "BTC",
            "pnl_usd": 45.00,
            "pnl_percent": 2.5,
            "strategy": "swing",
            "exit_reason": "take_profit",
        },
        {
            "symbol": "ETH",
            "pnl_usd": -12.00,
            "pnl_percent": -1.2,
            "strategy": "dca",
            "exit_reason": "stop_loss",
        },
        {
            "symbol": "SOL",
            "pnl_usd": 28.00,
            "pnl_percent": 3.8,
            "strategy": "channel",
            "exit_reason": "take_profit",
        },
    ]

    test_open_positions = [
        {
            "symbol": "LINK",
            "entry_price": 14.50,
            "usd_value": 50.0,
            "strategy": "swing",
            "entry_time": datetime.now(),
        },
        {
            "symbol": "AVAX",
            "entry_price": 35.20,
            "usd_value": 50.0,
            "strategy": "dca",
            "entry_time": datetime.now(),
        },
        {
            "symbol": "MATIC",
            "entry_price": 0.85,
            "usd_value": 50.0,
            "strategy": "channel",
            "entry_time": datetime.now(),
        },
    ]

    await notifier.send_daily_report(
        stats=test_stats,
        trades_today=test_trades_today,
        open_positions=test_open_positions,
    )
    logger.info("✅ Daily report sent")

    await asyncio.sleep(1)

    # Test 5: System Error (goes to #system-alerts)
    logger.info("\nTest 5: Sending system error notification to #system-alerts...")
    await notifier.notify_system_error(
        error_type="Data Fetch Failure",
        error_message="Failed to fetch market data from Polygon API - rate limit exceeded",
        details={
            "Component": "HybridDataFetcher",
            "Symbols Affected": "All 90 symbols",
            "Retry In": "60 seconds",
        },
    )
    logger.info("✅ System error notification sent")

    logger.info("\n" + "=" * 80)
    logger.info("✅ ALL TEST NOTIFICATIONS SENT SUCCESSFULLY")
    logger.info("=" * 80)
    logger.info("\nPlease check your Slack channels:")
    logger.info("  📊 #trades - Should have 3 trade notifications")
    logger.info("  📈 #reports - Should have 1 daily report")
    logger.info("  🚨 #system-alerts - Should have 1 error notification")
    logger.info("")

    return True


async def main():
    """Main entry point"""
    success = await test_notifications()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
