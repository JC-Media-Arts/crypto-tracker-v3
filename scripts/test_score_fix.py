#!/usr/bin/env python3
"""
Test script to verify the score field fix in SwingAnalyzer
Tests both paths: setups with and without score field
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from loguru import logger
from src.strategies.swing.analyzer import SwingAnalyzer


def test_score_fix():
    """Test that SwingAnalyzer handles missing score field gracefully"""

    analyzer = SwingAnalyzer()

    # Test 1: Setup WITH score field (normal case)
    setup_with_score = {
        "symbol": "BTC",
        "price": 50000,
        "entry_price": 50000,  # Required field
        "score": 75,  # Has score
        "confidence": 0.6,
        "pattern": "Breakout",  # Use capital B for pattern
        "stop_loss": 48000,
        "take_profit": 52000,
        "expected_value": 100,
        "risk_reward_ratio": 2.0,
        "priority": 5,
    }

    # Test 2: Setup WITHOUT score field (SimpleRules case)
    setup_without_score = {
        "symbol": "ETH",
        "price": 3000,
        "entry_price": 3000,  # Required field
        # NO score field - simulating SimpleRules
        "confidence": 0.5,
        "pattern": "simple_breakout",
        "stop_loss": 2850,
        "take_profit": 3150,
        "expected_value": 75,
        "risk_reward_ratio": 1.8,
        "priority": 3,
    }

    # Test 3: Setup with None score
    setup_none_score = {
        "symbol": "SOL",
        "price": 100,
        "entry_price": 100,  # Required field
        "score": None,  # Explicitly None
        "confidence": 0.45,
        "pattern": "Breakout",
        "stop_loss": 95,
        "take_profit": 105,
        "expected_value": 50,
        "risk_reward_ratio": 2.0,
        "priority": 2,
    }

    market_data = {"btc_trend": 0.02, "market_breadth": 0.6, "fear_greed_index": 55}

    portfolio = {"current_positions": [], "available_capital": 1000}

    print("Testing SwingAnalyzer with different score scenarios...")

    try:
        # Test with score
        print("\n1. Testing setup WITH score field:")
        analysis1 = analyzer.analyze_setup(setup_with_score, market_data)
        print(f"   ✅ Analysis successful - adjusted_score: {analysis1.get('adjusted_score', 'N/A')}")

        # Test without score
        print("\n2. Testing setup WITHOUT score field:")
        analysis2 = analyzer.analyze_setup(setup_without_score, market_data)
        print(f"   ✅ Analysis successful - adjusted_score: {analysis2.get('adjusted_score', 'N/A')}")

        # Test with None score
        print("\n3. Testing setup with None score:")
        analysis3 = analyzer.analyze_setup(setup_none_score, market_data)
        print(f"   ✅ Analysis successful - adjusted_score: {analysis3.get('adjusted_score', 'N/A')}")

        # Test that the critical methods don't crash
        print("\n4. Testing that critical methods handle missing score:")

        # Test rank_opportunities which uses composite_score
        opportunities = [setup_with_score, setup_without_score]
        try:
            ranked = analyzer.rank_opportunities(opportunities, portfolio)
            print(f"   ✅ rank_opportunities handled {len(ranked)} setups")
        except Exception as e:
            print(f"   ❌ rank_opportunities failed: {e}")
            raise

        print("\n✅ ALL TESTS PASSED! SwingAnalyzer now handles missing score field gracefully.")
        print("The fix respects the system design where SimpleRules is a valid fallback path.")

        return True

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_score_fix()
    sys.exit(0 if success else 1)
