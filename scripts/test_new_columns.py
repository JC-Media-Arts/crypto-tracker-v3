#!/usr/bin/env python3
"""
Test that stop_loss, take_profit, and trailing_stop_pct columns are working
"""

import asyncio
from datetime import datetime
from src.trading.simple_paper_trader_v2 import SimplePaperTraderV2
from src.data.supabase_client import SupabaseClient
from loguru import logger


async def test_new_columns():
    """Test that all new columns are saved correctly"""

    # Initialize components
    trader = SimplePaperTraderV2(initial_balance=1000.0)
    db = SupabaseClient()

    # Test symbol that won't interfere with real trading
    test_symbol = "TESTCOL"
    test_price = 50.0
    test_usd_amount = 100.0
    test_strategy = "swing"

    logger.info("Testing new columns: stop_loss, take_profit, trailing_stop_pct")

    # Open a position
    position = await trader.open_position(
        symbol=test_symbol,
        usd_amount=test_usd_amount,
        market_price=test_price,
        strategy=test_strategy,
        use_adaptive=True,  # This will set SL/TP/Trailing based on market cap
    )

    if position:
        logger.info(f"✅ Position opened for {test_symbol}")

        # Wait a moment for DB save
        await asyncio.sleep(1)

        # Check if all fields were saved
        result = db.client.table("paper_trades").select("*").eq("symbol", test_symbol).execute()

        if result.data:
            trade = result.data[0]
            logger.info("✅ Trade saved to database with:")
            logger.info(f"   - Price: ${trade['price']}")
            logger.info(f"   - Amount: {trade['amount']}")
            logger.info(f"   - Stop Loss: ${trade['stop_loss']}")
            logger.info(f"   - Take Profit: ${trade['take_profit']}")
            logger.info(f"   - Trailing Stop %: {trade['trailing_stop_pct']}")
            logger.info(f"   - Trading Engine: {trade['trading_engine']}")

            # Verify the values are reasonable
            if trade["stop_loss"] and trade["take_profit"] and trade["trailing_stop_pct"]:
                logger.info("\n✅ ALL NEW COLUMNS ARE WORKING!")
                logger.info("   Stop loss, take profit, and trailing stop are all being saved correctly.")
            else:
                logger.warning("\n⚠️ Some columns may be NULL")
        else:
            logger.error("❌ Trade not found in database")

        # Clean up - close the position
        await trader.close_position(
            symbol=test_symbol,
            current_price=test_price * 1.05,
            exit_reason="test_complete",
        )

        # Clean up test data
        logger.info("\nCleaning up test data...")
        db.client.table("paper_trades").delete().eq("symbol", test_symbol).execute()
        logger.info("✅ Test data cleaned up")
    else:
        logger.error("Failed to open position")


if __name__ == "__main__":
    asyncio.run(test_new_columns())
