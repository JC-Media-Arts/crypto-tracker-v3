#!/usr/bin/env python3
"""
Test that new trades are automatically logged to the database
"""

import asyncio
from datetime import datetime
from src.trading.simple_paper_trader_v2 import SimplePaperTraderV2
from src.data.supabase_client import SupabaseClient
from loguru import logger


async def test_auto_logging():
    """Test automatic trade logging to database"""

    # Initialize paper trader (it should have DB client)
    trader = SimplePaperTraderV2(initial_balance=1000.0)

    # Check initial trades count
    db = SupabaseClient()
    initial_trades = db.client.table("paper_trades").select("*").execute()
    initial_count = len(initial_trades.data)

    logger.info(f"Initial trades in database: {initial_count}")

    # Simulate opening a test position
    test_symbol = "TEST"
    test_price = 100.0
    test_usd_amount = 100.0  # $100 position
    test_strategy = "DCA"

    logger.info(f"Opening test position: {test_symbol} @ ${test_price}")

    position = await trader.open_position(
        symbol=test_symbol,
        usd_amount=test_usd_amount,
        market_price=test_price,
        strategy=test_strategy,
        use_adaptive=True,
    )

    if position:
        logger.info(f"✅ Position opened: {test_symbol}")

        # Check if it was saved to DB
        await asyncio.sleep(1)  # Give it a moment

        after_open = db.client.table("paper_trades").select("*").eq("symbol", test_symbol).execute()

        if after_open.data:
            logger.info(f"✅ OPEN position automatically saved to DB!")
            logger.info(f"   - Symbol: {after_open.data[0]['symbol']}")
            logger.info(f"   - Price: ${after_open.data[0]['price']}")
            logger.info(f"   - Engine: {after_open.data[0]['trading_engine']}")
        else:
            logger.warning("❌ Position NOT found in database after opening")

        # Now close the position to test exit logging
        logger.info(f"Closing test position with profit...")

        # Simulate price increase
        new_price = test_price * 1.05  # 5% profit

        closed_trade = await trader.close_position(
            symbol=test_symbol, current_price=new_price, exit_reason="take_profit"
        )

        if closed_trade:
            logger.info(f"✅ Position closed: P&L ${closed_trade.pnl_usd:.2f}")

            # Check if exit was saved to DB
            await asyncio.sleep(1)  # Give it a moment

            after_close = (
                db.client.table("paper_trades").select("*").eq("symbol", test_symbol).eq("side", "SELL").execute()
            )

            if after_close.data:
                logger.info(f"✅ CLOSE trade automatically saved to DB!")
                logger.info(f"   - Exit Price: ${after_close.data[0]['price']}")
                logger.info(f"   - P&L: ${after_close.data[0]['pnl']}")
                logger.info(f"   - Exit Reason: {after_close.data[0]['exit_reason']}")
            else:
                logger.warning("❌ Close trade NOT found in database")
        else:
            logger.error("Failed to close position")
    else:
        logger.error("Failed to open position")

    # Final count
    final_trades = db.client.table("paper_trades").select("*").execute()
    final_count = len(final_trades.data)

    logger.info(f"\n{'='*60}")
    logger.info("TEST RESULTS:")
    logger.info(f"{'='*60}")
    logger.info(f"Initial trades: {initial_count}")
    logger.info(f"Final trades: {final_count}")
    logger.info(f"New trades added: {final_count - initial_count}")

    if final_count > initial_count:
        logger.info("✅ AUTOMATIC TRADE LOGGING IS WORKING!")
    else:
        logger.warning("⚠️  No new trades were logged - check the implementation")

    # Clean up test trades
    logger.info("\nCleaning up test trades...")
    try:
        db.client.table("paper_trades").delete().eq("symbol", "TEST").execute()
        logger.info("✅ Test trades cleaned up")
    except Exception as e:
        logger.warning(f"Could not clean up test trades: {e}")


if __name__ == "__main__":
    asyncio.run(test_auto_logging())
