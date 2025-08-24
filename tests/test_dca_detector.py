#!/usr/bin/env python3
"""
Test DCA Detector with current market data.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from src.strategies.dca.detector import DCADetector
from src.strategies.dca.grid import GridCalculator

# Load environment variables
load_dotenv()


def test_dca_detection():
    """Test DCA detection on current market data."""

    print("=" * 80)
    print("DCA STRATEGY DETECTOR TEST")
    print("=" * 80)

    # Initialize clients
    print("\n1. Initializing Supabase client...")
    supabase_client = SupabaseClient()

    print("2. Initializing DCA Detector...")
    detector = DCADetector(supabase_client)

    # Test with a few symbols first
    test_symbols = ["BTC", "ETH", "SOL", "ADA", "DOT"]

    print(f"\n3. Checking for DCA setups in: {', '.join(test_symbols)}")
    print("-" * 40)

    setups = detector.detect_setups(symbols=test_symbols)

    if not setups:
        print("❌ No DCA setups detected currently.")
        print("\nThis could mean:")
        print("  - No symbols have dropped 5%+ from recent highs")
        print("  - BTC regime is not favorable (BEAR/CRASH)")
        print("  - Insufficient volume")
    else:
        print(f"\n✅ Found {len(setups)} DCA setups!")

        for i, setup in enumerate(setups, 1):
            print(f"\n📊 Setup #{i}: {setup['symbol']}")
            print(f"  Current Price: ${setup['setup_price']:.4f}")
            print(f"  Drop from 4h high: {setup['setup_data']['drop_pct']:.2f}%")
            print(f"  RSI: {setup['setup_data']['rsi']:.1f}")
            print(f"  Volume Ratio: {setup['setup_data']['volume_avg_ratio']:.2f}x")
            print(f"  BTC Regime: {setup['setup_data']['btc_regime']}")

            # Test grid calculation
            print(f"\n  Testing Grid Calculation...")
            config = detector.config
            calculator = GridCalculator(config)

            # Simulate ML confidence (would come from model)
            ml_confidence = 0.65

            grid = calculator.calculate_grid(
                current_price=setup["setup_price"],
                ml_confidence=ml_confidence,
                support_levels=setup["setup_data"]["support_levels"],
            )

            print(f"  Grid Levels: {len(grid['levels'])}")
            print(f"  Total Investment: ${grid['total_investment']:.2f}")
            print(f"  Average Entry: ${grid['average_entry']:.4f}")
            print(f"  Stop Loss: ${grid['stop_loss']:.4f} ({config['stop_loss']}%)")
            print(
                f"  Take Profit: ${grid['take_profit']:.4f} (+{config['take_profit']}%)"
            )

            print("\n  Grid Details:")
            for level in grid["levels"]:
                print(
                    f"    Level {level['level']}: ${level['price']:.4f} - Size: ${level['size']:.2f}"
                )

    # Check BTC regime
    print("\n" + "=" * 80)
    print("MARKET REGIME CHECK")
    print("-" * 40)

    btc_regime = detector._get_btc_regime()
    print(f"Current BTC Regime: {btc_regime}")

    # Get latest regime data
    try:
        result = (
            supabase_client.client.table("market_regimes")
            .select("*")
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
        )

        if result.data:
            regime_data = result.data[0]
            print(f"BTC Price: ${regime_data['btc_price']:.2f}")
            print(f"Timestamp: {regime_data['timestamp']}")
    except Exception as e:
        print(f"Error fetching regime data: {e}")

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    test_dca_detection()
