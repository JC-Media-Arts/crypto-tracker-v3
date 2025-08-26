#!/usr/bin/env python3
"""
Test current strategy thresholds against live market data
to determine if signals should be generated
"""

import asyncio
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from loguru import logger
import sys
from collections import defaultdict

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.hybrid_fetcher import HybridDataFetcher
from src.strategies.simple_rules import SimpleRules
from supabase import Client, create_client

load_dotenv()


async def test_thresholds():
    """Test if current thresholds should generate signals"""

    # Initialize components
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    supabase_client = create_client(supabase_url, supabase_key)

    data_fetcher = HybridDataFetcher()  # No arguments needed

    # Load actual config from paper_trading_config
    from configs.paper_trading_config import PAPER_TRADING_CONFIG

    config = {
        "dca_drop_threshold": PAPER_TRADING_CONFIG["strategies"]["DCA"].get(
            "drop_threshold", -2.5
        ),
        "swing_breakout_threshold": PAPER_TRADING_CONFIG["strategies"]["SWING"].get(
            "breakout_threshold", 1.010
        ),
        "channel_position_threshold": PAPER_TRADING_CONFIG["strategies"]["CHANNEL"].get(
            "buy_zone", 0.10
        ),
        "swing_volume_surge": PAPER_TRADING_CONFIG["strategies"]["SWING"].get(
            "volume_surge", 1.3
        ),
        "channel_touches": PAPER_TRADING_CONFIG["strategies"]["CHANNEL"].get(
            "channel_touches", 3
        ),
    }
    simple_rules = SimpleRules(config)

    # Test symbols - mix of different types
    test_symbols = [
        "BTC",
        "ETH",
        "SOL",
        "XRP",
        "ADA",  # Large caps
        "PEPE",
        "WIF",
        "BONK",
        "NEIRO",  # Memecoins
        "ARB",
        "OP",
        "INJ",
        "FET",  # Mid caps
    ]

    logger.info("=" * 80)
    logger.info("STRATEGY THRESHOLD TEST")
    logger.info(f"Testing at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Current thresholds:")
    logger.info(f"  DCA: {config['dca_drop_threshold']}% drop from recent high")
    logger.info(
        f"  SWING: {config['swing_breakout_threshold']}x breakout + {config['swing_volume_surge']}x volume"
    )
    logger.info(
        f"  CHANNEL: Top/Bottom {config['channel_position_threshold']*100}% of range"
    )
    logger.info("=" * 80)

    # Check market summary cache
    try:
        result = (
            supabase_client.table("market_summary_cache")
            .select("*")
            .order("calculated_at", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            market_data = result.data[0]
            logger.info(f"\n📊 Market Analyzer Says:")
            logger.info(
                f"  Best Strategy: {market_data.get('best_strategy', 'Unknown')}"
            )
            logger.info(f"  Condition: {market_data.get('condition', 'Unknown')}")
            logger.info(f"  Notes: {market_data.get('notes', 'None')}")
            logger.info(f"  Updated: {market_data.get('calculated_at', 'Unknown')}")
    except Exception as e:
        logger.error(f"Could not fetch market analysis: {e}")

    # Track results
    signals_found = defaultdict(list)
    near_misses = defaultdict(list)

    logger.info("\n🔍 Testing each symbol for signals...")
    logger.info("-" * 80)

    for symbol in test_symbols:
        try:
            # Get recent 1-minute data (last 4 hours for DCA, last hour for others)
            data = await data_fetcher.get_recent_data(
                symbol=symbol, timeframe="1m", hours=4
            )

            if not data or len(data) < 50:
                logger.warning(f"{symbol}: Insufficient data")
                continue

            current_price = data[-1]["close"]

            # Test DCA
            dca_signal = simple_rules.check_dca_setup(symbol, data)
            if dca_signal and dca_signal.get("signal"):
                signals_found["DCA"].append(
                    f"{symbol} (drop: {dca_signal.get('drop_pct', 0):.2f}%)"
                )
                logger.success(
                    f"✅ {symbol} - DCA SIGNAL! Drop: {dca_signal.get('drop_pct', 0):.2f}%"
                )
            else:
                # Check how close we are to DCA threshold
                recent_high = max([d["high"] for d in data[-240:]])  # 4 hours
                drop_pct = ((current_price - recent_high) / recent_high) * 100
                if drop_pct < 0:  # Only if it's actually down
                    distance_from_threshold = abs(
                        drop_pct - config["dca_drop_threshold"]
                    )
                    if distance_from_threshold < 2.0:  # Within 2% of threshold
                        near_misses["DCA"].append(
                            f"{symbol} (drop: {drop_pct:.2f}%, need: {config['dca_drop_threshold']}%)"
                        )
                        logger.info(
                            f"📉 {symbol} - DCA near miss: {drop_pct:.2f}% (need {config['dca_drop_threshold']}%)"
                        )

            # Test SWING
            swing_signal = simple_rules.check_swing_setup(symbol, data)
            if swing_signal and swing_signal.get("signal"):
                signals_found["SWING"].append(
                    f"{symbol} (breakout: {swing_signal.get('breakout_pct', 0):.2f}x)"
                )
                logger.success(
                    f"✅ {symbol} - SWING SIGNAL! Breakout: {swing_signal.get('breakout_pct', 0):.2f}x"
                )
            else:
                # Check how close we are to SWING threshold
                if len(data) >= 20:
                    resistance = max([d["high"] for d in data[-20:]])
                    breakout = current_price / resistance

                    # Calculate volume surge
                    recent_volumes = [
                        d["volume"] for d in data[-20:] if d.get("volume")
                    ]
                    if recent_volumes:
                        avg_volume = sum(recent_volumes) / len(recent_volumes)
                        current_volume = data[-1].get("volume", 0)
                        volume_surge = (
                            current_volume / avg_volume if avg_volume > 0 else 0
                        )

                        if (
                            breakout > 1.0 and volume_surge > 1.0
                        ):  # Positive breakout with some volume
                            if breakout > 1.005:  # At least 0.5% breakout
                                near_misses["SWING"].append(
                                    f"{symbol} (breakout: {breakout:.3f}x, vol: {volume_surge:.1f}x)"
                                )
                                logger.info(
                                    f"📈 {symbol} - SWING near miss: breakout {breakout:.3f}x, volume {volume_surge:.1f}x"
                                )

            # Test CHANNEL
            channel_signal = simple_rules.check_channel_setup(symbol, data)
            if channel_signal and channel_signal.get("signal"):
                position = channel_signal.get("position", 0)
                signals_found["CHANNEL"].append(f"{symbol} (pos: {position:.1%})")
                logger.success(f"✅ {symbol} - CHANNEL SIGNAL! Position: {position:.1%}")

        except Exception as e:
            logger.error(f"{symbol}: Error - {e}")

    # Print summary
    logger.info("\n" + "=" * 80)
    logger.info("📊 RESULTS SUMMARY")
    logger.info("=" * 80)

    # Signals found
    logger.info("\n✅ Signals Generated:")
    for strategy in ["DCA", "SWING", "CHANNEL"]:
        count = len(signals_found[strategy])
        if count > 0:
            logger.success(f"  {strategy}: {count} signals")
            for signal in signals_found[strategy][:5]:  # Show first 5
                logger.info(f"    - {signal}")
        else:
            logger.warning(f"  {strategy}: 0 signals")

    # Near misses
    logger.info("\n⚠️  Near Misses (close to threshold):")
    for strategy in ["DCA", "SWING"]:
        if near_misses[strategy]:
            logger.info(f"  {strategy}: {len(near_misses[strategy])} near misses")
            for miss in near_misses[strategy][:3]:  # Show first 3
                logger.info(f"    - {miss}")

    # Analysis
    logger.info("\n🔍 ANALYSIS:")

    total_dca = len(signals_found["DCA"])
    total_swing = len(signals_found["SWING"])
    total_channel = len(signals_found["CHANNEL"])

    if total_dca == 0 and total_swing == 0:
        logger.error("❌ DCA and SWING thresholds are too conservative!")
        logger.error("   No signals despite market analyzer recommendations")

        if near_misses["DCA"]:
            logger.info("\n💡 DCA Recommendation:")
            logger.info(f"   Current threshold: {config['dca_drop_threshold']}%")
            logger.info(f"   Suggested: -2.5% or -3.0% (would capture near misses)")

        if near_misses["SWING"]:
            logger.info("\n💡 SWING Recommendation:")
            logger.info(f"   Current threshold: {config['swing_breakout_threshold']}x")
            logger.info(f"   Suggested: 1.010x (1% breakout)")
    else:
        logger.success("✅ Thresholds are generating signals")

    if total_channel > (total_dca + total_swing) * 3:
        logger.warning("\n⚠️  CHANNEL is still too dominant!")
        logger.warning(
            f"   CHANNEL: {total_channel} vs DCA+SWING: {total_dca + total_swing}"
        )
        logger.info("   Consider tightening CHANNEL threshold to 0.10 (10%)")

    # Check if market analyzer is misleading
    try:
        result = (
            supabase_client.table("market_summary_cache")
            .select("best_strategy")
            .order("calculated_at", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            best_strategy = result.data[0].get("best_strategy", "").upper()
            if best_strategy == "DCA" and total_dca == 0:
                logger.error("\n🚨 Market Analyzer Issue Detected!")
                logger.error(
                    f"   Recommends {best_strategy} but no {best_strategy} signals possible"
                )
                logger.error(
                    "   Either thresholds need adjustment or analyzer logic is flawed"
                )
            elif best_strategy == "SWING" and total_swing == 0:
                logger.error("\n🚨 Market Analyzer Issue Detected!")
                logger.error(
                    f"   Recommends {best_strategy} but no {best_strategy} signals possible"
                )
    except:
        pass

    logger.info("\n" + "=" * 80)
    logger.info("TEST COMPLETE")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_thresholds())
