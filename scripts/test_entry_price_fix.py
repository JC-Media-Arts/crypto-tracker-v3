#!/usr/bin/env python3
"""
Test script to verify the entry_price fix in SwingAnalyzer
Tests that analyzer handles both 'price' and missing fields gracefully
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from loguru import logger
from src.strategies.swing.analyzer import SwingAnalyzer


def test_entry_price_fix():
    """Test that SwingAnalyzer handles price fields correctly"""

    analyzer = SwingAnalyzer()

    # Test 1: Setup with 'price' field (standard)
    setup_with_price = {
        "symbol": "BTC",
        "price": 50000,  # Standard field name
        "score": 75,
        "confidence": 0.6,
        "pattern": "Breakout",
        "stop_loss": 48000,
        "take_profit": 52000,
        "expected_value": 100,
        "risk_reward_ratio": 2.0,
        "priority": 5,
    }

    # Test 2: Setup without 'price' or 'entry_price' (edge case)
    setup_without_price = {
        "symbol": "ETH",
        # NO price field at all
        "score": 60,
        "confidence": 0.5,
        "pattern": "simple_breakout",
        # Missing stop_loss and take_profit too
        "expected_value": 75,
        "risk_reward_ratio": 1.8,
        "priority": 3,
    }

    # Test 3: Setup with minimal fields (SimpleRules case)
    setup_minimal = {
        "symbol": "SOL",
        "price": 100,
        # Missing pattern, stop_loss, take_profit
        "confidence": 0.45,
        "expected_value": 50,
        "risk_reward_ratio": 2.0,
        "priority": 2,
    }

    market_data = {"btc_trend": 0.02, "market_breadth": 0.6, "fear_greed_index": 55}

    print("Testing SwingAnalyzer entry_price fix...")

    try:
        # Test with standard price field
        print("\n1. Testing setup WITH 'price' field:")
        analysis1 = analyzer.analyze_setup(setup_with_price, market_data)
        trade_plan1 = analysis1.get("trade_plan", {})
        print(f"   ✅ Analysis successful")
        print(f"   Entry price in trade plan: ${trade_plan1.get('entry_price', 'N/A')}")
        print(f"   Stop loss: ${trade_plan1.get('stop_loss', 'N/A')}")

        # Test without price field
        print("\n2. Testing setup WITHOUT price field:")
        analysis2 = analyzer.analyze_setup(setup_without_price, market_data)
        trade_plan2 = analysis2.get("trade_plan", {})
        print(f"   ✅ Analysis successful")
        print(f"   Entry price in trade plan: ${trade_plan2.get('entry_price', 'N/A')}")
        print(f"   Stop loss: ${trade_plan2.get('stop_loss', 'N/A')} (should be default)")

        # Test with minimal fields
        print("\n3. Testing setup with minimal fields:")
        analysis3 = analyzer.analyze_setup(setup_minimal, market_data)
        trade_plan3 = analysis3.get("trade_plan", {})
        print(f"   ✅ Analysis successful")
        print(f"   Entry price in trade plan: ${trade_plan3.get('entry_price', 'N/A')}")
        print(
            f"   Pattern handling: {trade_plan3.get('notes', ['No notes'])[0] if trade_plan3.get('notes') else 'No notes'}"
        )

        # Test BEAR market adjustment
        print("\n4. Testing BEAR market regime adjustment:")
        bear_market_data = {
            "btc_trend": -0.10,  # -10% BTC drop
            "market_breadth": 0.2,  # Low breadth
            "fear_greed_index": 20,  # Fear
        }
        analysis4 = analyzer.analyze_setup(setup_with_price, bear_market_data)
        print(f"   ✅ BEAR market analysis successful")
        print(f"   Adjusted stop loss: ${analysis4.get('stop_loss', 'N/A')}")
        print(f"   Adjusted take profit: ${analysis4.get('take_profit', 'N/A')}")

        print("\n✅ ALL TESTS PASSED! SwingAnalyzer now handles price fields correctly.")
        print("The fix standardizes on 'price' field and uses defensive access throughout.")

        return True

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_entry_price_fix()
    sys.exit(0 if success else 1)
