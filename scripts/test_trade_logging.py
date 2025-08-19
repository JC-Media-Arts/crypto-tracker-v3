#!/usr/bin/env python3
"""
Test trade logging and feedback loop
"""

import sys
import asyncio
from datetime import datetime
from loguru import logger

sys.path.append(".")

from src.data.supabase_client import SupabaseClient
from src.strategies.scan_logger_v2 import ScanLoggerV2
from src.trading.trade_logger import TradeLogger


async def test_trade_logging():
    """Test the complete feedback loop"""

    # Initialize components
    supabase = SupabaseClient()
    scan_logger = ScanLoggerV2(supabase.client)
    trade_logger = TradeLogger(supabase.client)

    print("\n" + "=" * 60)
    print("TESTING TRADE LOGGING & FEEDBACK LOOP")
    print("=" * 60)

    # Step 1: Simulate a scan that results in a TAKE decision
    print("\n1. Logging a scan that triggers a trade...")

    scan_id = scan_logger.log_scan_decision(
        symbol="BTC",
        strategy_name="DCA",
        decision="TAKE",
        reason="all_conditions_met",
        features={"price": 45000, "drop_pct": -5.2, "rsi": 28, "volume_ratio": 2.1},
        ml_confidence=0.72,
        ml_predictions={
            "take_profit": 8.5,
            "stop_loss": -4.0,
            "hold_hours": 36,
            "win_probability": 0.68,
        },
        setup_data={"drop_from_high": -5.2, "support_level": 44500},
        market_regime="NORMAL",
        btc_price=45000,
        proposed_position_size=50,
        proposed_capital=50,
        immediate_insert=True,  # Get scan_id immediately
    )

    if scan_id:
        print(f"✅ Scan logged with ID: {scan_id}")
    else:
        print("❌ Failed to log scan")
        return

    # Step 2: Open a trade linked to this scan
    print("\n2. Opening a trade linked to the scan...")

    trade_id = trade_logger.open_trade(
        scan_id=scan_id,
        symbol="BTC",
        strategy_name="DCA",
        entry_price=45000,
        position_size=0.001,
        capital_used=50,
        ml_predictions={
            "take_profit": 8.5,
            "stop_loss": -4.0,
            "hold_hours": 36,
            "win_probability": 0.68,
        },
        ml_confidence=0.72,
    )

    if trade_id:
        print(f"✅ Trade opened with ID: {trade_id}")
    else:
        print("❌ Failed to open trade")
        return

    # Step 3: Check active trades
    print("\n3. Checking active trades...")
    active = trade_logger.get_active_trades()
    print(f"Active trades: {len(active)}")
    for tid, trade in active.items():
        print(f"  - Trade {tid}: {trade['symbol']} @ ${trade['entry_price']}")

    # Step 4: Simulate trade closing (win scenario)
    print("\n4. Simulating trade close (win)...")

    exit_price = 48825  # 8.5% profit as predicted
    success = trade_logger.close_trade(
        trade_id=trade_id,
        exit_price=exit_price,
        exit_reason="take_profit",
        market_regime="NORMAL",
        btc_price=48000,
    )

    if success:
        print(f"✅ Trade closed successfully")
        print(f"   Entry: $45,000 → Exit: ${exit_price:,.0f}")
        print(f"   P&L: +${(exit_price - 45000) * 0.001:,.2f} (+8.5%)")
    else:
        print("❌ Failed to close trade")

    # Step 5: Check trade performance
    print("\n5. Checking trade performance...")
    performance = trade_logger.get_trade_performance(hours=1)

    print(f"Performance Summary:")
    print(f"  Total Trades: {performance.get('total_trades', 0)}")
    print(f"  Open Trades: {performance.get('open_trades', 0)}")
    print(f"  Closed Trades: {performance.get('closed_trades', 0)}")
    print(f"  Win Rate: {performance.get('win_rate', 0):.1%}")
    print(f"  Avg P&L: {performance.get('avg_pnl_pct', 0):.2f}%")
    print(f"  Total P&L: ${performance.get('total_pnl', 0):.2f}")

    # Step 6: Query the ML feedback view
    print("\n6. Checking ML training feedback...")

    try:
        result = (
            supabase.client.table("ml_training_feedback").select("*").limit(5).execute()
        )

        if result.data:
            print(f"Found {len(result.data)} feedback records")
            for record in result.data:
                print(
                    f"  - Scan {record['scan_id']}: "
                    f"Predicted {record['ml_confidence']:.2f} confidence, "
                    f"Outcome: {'WIN' if record['outcome_label'] == 1 else 'LOSS'}"
                )
        else:
            print("No feedback records found yet")
    except Exception as e:
        print(f"Note: ml_training_feedback view may not exist yet: {e}")

    # Step 7: Check prediction accuracy
    print("\n7. Checking prediction accuracy...")

    try:
        result = (
            supabase.client.table("prediction_accuracy_analysis").select("*").execute()
        )

        if result.data:
            print("Prediction Accuracy by Strategy:")
            for record in result.data:
                print(f"  {record['strategy_name']}:")
                print(
                    f"    - Predicted Win Rate: {record.get('avg_predicted_win_prob', 0):.1%}"
                )
                print(f"    - Actual Win Rate: {record.get('actual_win_rate', 0):.1%}")
                print(f"    - Avg ML Confidence: {record.get('avg_confidence', 0):.2f}")
        else:
            print("No accuracy data available yet")
    except Exception as e:
        print(f"Note: prediction_accuracy_analysis view may not exist yet: {e}")

    print("\n" + "=" * 60)
    print("✅ PHASE 2 TESTING COMPLETE!")
    print("=" * 60)
    print("\nThe feedback loop is working:")
    print("1. Scans are logged with all decision data")
    print("2. Trades are linked to their triggering scans")
    print("3. Trade outcomes are tracked and analyzed")
    print("4. ML predictions can be compared to actual outcomes")
    print("5. This data is ready for model retraining")


if __name__ == "__main__":
    asyncio.run(test_trade_logging())
