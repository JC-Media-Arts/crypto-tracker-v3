#!/usr/bin/env python3
"""
Demo script showing the Adaptive Position Sizing System in action.
"""

import sys
from pathlib import Path
import pandas as pd
from datetime import datetime
from dateutil import tz
from loguru import logger

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.trading.position_sizer import (
    AdaptivePositionSizer,
    PositionSizingConfig,
    PortfolioRiskManager,
)


def demo_position_sizing():
    """Demonstrate adaptive position sizing with various market conditions."""

    logger.info("=" * 80)
    logger.info("ADAPTIVE POSITION SIZING DEMO")
    logger.info("=" * 80)

    # Initialize with custom config
    config = PositionSizingConfig(
        base_position_usd=100.0,
        bear_market_mult=2.0,
        bull_market_mult=0.5,
        high_volatility_mult=1.2,
        underperform_mult=1.3,
    )

    sizer = AdaptivePositionSizer(config)
    portfolio_value = 10000

    logger.info(f"\nPortfolio Value: ${portfolio_value:,.2f}")
    logger.info(f"Base Position Size: ${config.base_position_usd:.2f}")

    # Define test scenarios
    scenarios = [
        {
            "name": "🐻 BEAR Market + Underperforming + High Vol",
            "symbol": "SOL",
            "market_data": {
                "btc_regime": "BEAR",
                "btc_volatility_7d": 0.8,
                "symbol_vs_btc_7d": -15,
                "market_cap_tier": 1,
            },
            "ml_confidence": 0.8,
        },
        {
            "name": "🐂 BULL Market + Outperforming + Low Vol",
            "symbol": "PEPE",
            "market_data": {
                "btc_regime": "BULL",
                "btc_volatility_7d": 0.2,
                "symbol_vs_btc_7d": 20,
                "market_cap_tier": 2,
            },
            "ml_confidence": 0.3,
        },
        {
            "name": "😐 NEUTRAL Market + Average Conditions",
            "symbol": "ETH",
            "market_data": {
                "btc_regime": "NEUTRAL",
                "btc_volatility_7d": 0.4,
                "symbol_vs_btc_7d": 0,
                "market_cap_tier": 0,
            },
            "ml_confidence": 0.6,
        },
        {
            "name": "🎯 Perfect DCA Setup (BEAR + Underperform)",
            "symbol": "AVAX",
            "market_data": {
                "btc_regime": "BEAR",
                "btc_volatility_7d": 0.6,
                "symbol_vs_btc_7d": -20,
                "market_cap_tier": 1,
            },
            "ml_confidence": 0.9,
        },
        {
            "name": "⚠️ Worst Case (BULL + Outperform)",
            "symbol": "BTC",
            "market_data": {
                "btc_regime": "BULL",
                "btc_volatility_7d": 0.3,
                "symbol_vs_btc_7d": 15,
                "market_cap_tier": 0,
            },
            "ml_confidence": 0.2,
        },
    ]

    logger.info("\n" + "=" * 80)
    logger.info("POSITION SIZING SCENARIOS")
    logger.info("=" * 80)

    results = []

    for scenario in scenarios:
        logger.info(f"\n{scenario['name']}")
        logger.info("-" * 60)

        # Calculate position size
        size, multipliers = sizer.calculate_position_size(
            symbol=scenario["symbol"],
            portfolio_value=portfolio_value,
            market_data=scenario["market_data"],
            ml_confidence=scenario["ml_confidence"],
        )

        # Display details
        logger.info(f"Symbol: {scenario['symbol']}")
        logger.info(f"Market Conditions:")
        logger.info(f"  - BTC Regime: {scenario['market_data']['btc_regime']}")
        logger.info(f"  - Volatility: {scenario['market_data']['btc_volatility_7d']:.1%}")
        logger.info(f"  - vs BTC (7d): {scenario['market_data']['symbol_vs_btc_7d']:+.1f}%")
        logger.info(f"  - ML Confidence: {scenario['ml_confidence']:.1%}")

        logger.info(f"\nMultipliers Applied:")
        for key, value in multipliers.items():
            logger.info(f"  - {key:15s}: {value:.2f}x")

        total_multiplier = 1.0
        for mult in multipliers.values():
            total_multiplier *= mult

        logger.info(f"  - TOTAL:          {total_multiplier:.2f}x")

        logger.info(f"\n💰 POSITION SIZE: ${size:.2f}")
        logger.info(f"   (Base ${config.base_position_usd:.0f} × {total_multiplier:.2f} = ${size:.2f})")
        logger.info(f"   Portfolio %: {(size/portfolio_value)*100:.1f}%")

        results.append(
            {
                "scenario": scenario["name"],
                "size": size,
                "total_mult": total_multiplier,
                "portfolio_pct": (size / portfolio_value) * 100,
            }
        )

    # Summary table
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)

    df_results = pd.DataFrame(results)
    logger.info("\n" + df_results.to_string(index=False))

    # Risk management demo
    logger.info("\n" + "=" * 80)
    logger.info("PORTFOLIO RISK MANAGEMENT DEMO")
    logger.info("=" * 80)

    manager = PortfolioRiskManager(sizer)
    manager.portfolio_value = portfolio_value

    # Try to open multiple positions
    positions_to_open = [
        ("SOL", 100, 300),
        ("AVAX", 50, 250),
        ("PEPE", 20, 150),
        ("DOGE", 10, 100),
    ]

    logger.info(f"\nAttempting to open {len(positions_to_open)} positions:")

    for symbol, price, size in positions_to_open:
        if manager.can_open_position(symbol, size):
            success = manager.open_position(
                symbol=symbol,
                entry_price=price,
                size=size,
                stop_loss=price * 0.92,
                take_profit=price * 1.10,
            )
            status = "✅ Opened" if success else "❌ Failed"
        else:
            status = "❌ Blocked (risk limits)"

        logger.info(f"  {symbol}: ${size:.0f} position - {status}")

    # Show portfolio summary
    summary = manager.get_portfolio_summary()

    logger.info("\n📊 Portfolio Summary:")
    logger.info(f"  - Portfolio Value: ${summary['portfolio_value']:,.2f}")
    logger.info(f"  - Open Positions: {summary['open_positions']}")
    logger.info(
        f"  - Current Exposure: ${summary['current_exposure_usd']:.2f} ({summary['current_exposure_pct']:.1f}%)"
    )
    logger.info(f"  - Available Capital: ${summary['available_capital']:,.2f}")

    # Simulate closing a position with profit
    if "SOL" in manager.open_positions:
        pnl = manager.close_position("SOL", 110)  # 10% profit
        logger.info(f"\n💵 Closed SOL position: P&L = ${pnl:+.2f}")

    logger.info("\n" + "=" * 80)
    logger.info("KEY INSIGHTS")
    logger.info("=" * 80)

    logger.info("\n1. BEAR markets get 2x position size (best for DCA)")
    logger.info("2. BULL markets get 0.5x position size (reduce risk)")
    logger.info("3. Underperforming coins get 1.3x boost (better bounce potential)")
    logger.info("4. High volatility gets 1.2x boost (bigger moves)")
    logger.info("5. ML confidence scales from 0.5x to 1.5x")
    logger.info("6. Risk limits prevent overexposure")

    logger.success("\n✅ Adaptive Position Sizing System Ready for Production!")


if __name__ == "__main__":
    demo_position_sizing()
