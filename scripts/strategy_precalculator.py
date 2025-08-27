#!/usr/bin/env python3
"""
Pre-calculate strategy status and cache in database
This runs as a background service to avoid dashboard timeouts
"""

import sys
import asyncio
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict

sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient  # noqa: E402
from src.strategies.simple_rules import SimpleRules  # noqa: E402
from loguru import logger  # noqa: E402


class StrategyPreCalculator:
    """Pre-calculates strategy readiness for all symbols"""

    def __init__(self):
        self.db = SupabaseClient()
        # Load proper config from paper_trading_config
        from configs.paper_trading_config import PAPER_TRADING_CONFIG

        config = {
            "dca_drop_threshold": PAPER_TRADING_CONFIG["strategies"]["DCA"].get(
                "drop_threshold", -2.5
            ),
            "swing_breakout_threshold": PAPER_TRADING_CONFIG["strategies"]["SWING"].get(
                "breakout_threshold", 1.010
            ),
            "channel_position_threshold": PAPER_TRADING_CONFIG["strategies"][
                "CHANNEL"
            ].get("buy_zone", 0.10),
            "swing_volume_surge": PAPER_TRADING_CONFIG["strategies"]["SWING"].get(
                "volume_surge", 1.3
            ),
            "channel_touches": PAPER_TRADING_CONFIG["strategies"]["CHANNEL"].get(
                "channel_touches", 3
            ),
        }
        self.simple_rules = SimpleRules(config)

        # ALL monitored symbols from the system
        self.symbols = [
            # Tier 1: Core (20 coins)
            "BTC",
            "ETH",
            "SOL",
            "BNB",
            "XRP",
            "ADA",
            "AVAX",
            "DOGE",
            "DOT",
            "POL",
            "LINK",
            "TON",
            "SHIB",
            "TRX",
            "UNI",
            "ATOM",
            "BCH",
            "APT",
            "NEAR",
            "ICP",
            # Tier 2: DeFi/Layer 2 (20 coins)
            "ARB",
            "OP",
            "AAVE",
            "CRV",
            "MKR",
            "LDO",
            "SUSHI",
            "COMP",
            "SNX",
            "BAL",
            "INJ",
            "SEI",
            "PENDLE",
            "BLUR",
            "ENS",
            "GRT",
            "RENDER",
            "FET",
            "RPL",
            "SAND",
            # Tier 3: Trending/Memecoins (20 coins)
            "PEPE",
            "WIF",
            "BONK",
            "FLOKI",
            "MEME",
            "POPCAT",
            "MEW",
            "TURBO",
            "NEIRO",
            "PNUT",
            "GOAT",
            "ACT",
            "TRUMP",
            "FARTCOIN",
            "MOG",
            "PONKE",
            "TREMP",
            "BRETT",
            "GIGA",
            "HIPPO",
            # Tier 4: Solid Mid-Caps (30+ coins)
            "FIL",
            "RUNE",
            "IMX",
            "FLOW",
            "MANA",
            "AXS",
            "CHZ",
            "GALA",
            "LRC",
            "OCEAN",
            "QNT",
            "ALGO",
            "XLM",
            "XMR",
            "ZEC",
            "DASH",
            "HBAR",
            "VET",
            "THETA",
            "EOS",
            "KSM",
            "STX",
            "KAS",
            "TIA",
            "JTO",
            "JUP",
            "PYTH",
            "DYM",
            "STRK",
            "ALT",
            "PORTAL",
            "BEAM",
            "MASK",
            "API3",
        ]

    async def calculate_all(self):
        """Calculate strategy status for all symbols"""
        logger.info("=" * 60)
        logger.info("STRATEGY PRE-CALCULATOR")
        logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Processing {len(self.symbols)} symbols")
        logger.info("=" * 60)

        start_time = time.time()

        # Clear old cache entries
        await self.clear_old_cache()

        # Calculate for each symbol
        swing_candidates = []
        channel_candidates = []
        dca_candidates = []

        processed_count = 0
        skipped_count = 0

        for i, symbol in enumerate(self.symbols, 1):
            # Show progress every 10 symbols
            if i % 10 == 1:
                logger.info(f"Progress: {i}/{len(self.symbols)} symbols...")

            try:
                # Fetch data from materialized view (faster)
                result = (
                    self.db.client.table("ohlc_recent")
                    .select("*")
                    .eq("symbol", symbol)
                    .eq("timeframe", "15m")
                    .order("timestamp", desc=True)
                    .limit(100)
                    .execute()
                )

                if not result.data or len(result.data) < 20:
                    skipped_count += 1
                    continue

                data = result.data[::-1]  # Reverse to chronological
                current = data[-1]
                recent_data = data[-20:]

                # Calculate SWING readiness
                swing_readiness = self.calculate_swing_readiness(
                    data, current, recent_data
                )
                swing_candidates.append(
                    {
                        "symbol": symbol,
                        "strategy_name": "SWING",
                        "readiness": swing_readiness["readiness"],
                        "current_price": current["close"],
                        "details": swing_readiness["details"],
                        "status": swing_readiness["status"],
                    }
                )

                # Calculate CHANNEL readiness
                channel_readiness = self.calculate_channel_readiness(data, current)
                channel_candidates.append(
                    {
                        "symbol": symbol,
                        "strategy_name": "CHANNEL",
                        "readiness": channel_readiness["readiness"],
                        "current_price": current["close"],
                        "details": channel_readiness["details"],
                        "status": channel_readiness["status"],
                    }
                )

                # Calculate DCA readiness
                dca_readiness = self.calculate_dca_readiness(data, current)
                dca_candidates.append(
                    {
                        "symbol": symbol,
                        "strategy_name": "DCA",
                        "readiness": dca_readiness["readiness"],
                        "current_price": current["close"],
                        "details": dca_readiness["details"],
                        "status": dca_readiness["status"],
                    }
                )

                processed_count += 1

            except Exception as e:
                logger.error(f"  Error processing {symbol}: {str(e)[:100]}")
                skipped_count += 1
                continue

        # Save to cache
        await self.save_to_cache(swing_candidates, channel_candidates, dca_candidates)

        # Calculate market summary
        await self.calculate_market_summary(
            swing_candidates, channel_candidates, dca_candidates
        )

        elapsed = time.time() - start_time
        logger.info(f"\n✅ Pre-calculation complete in {elapsed:.2f}s")
        logger.info(f"   Processed: {processed_count}/{len(self.symbols)} symbols")
        logger.info(f"   Skipped: {skipped_count} (insufficient data)")
        logger.info(
            f"   Cache entries: {len(swing_candidates + channel_candidates + dca_candidates)}"
        )

    def calculate_swing_readiness(self, data, current, recent_data) -> Dict:
        """Calculate swing trading readiness"""
        recent_high = max(d["high"] for d in recent_data[-10:])
        breakout_pct = ((current["close"] - recent_high) / recent_high) * 100

        avg_volume = sum(d["volume"] for d in recent_data[-10:]) / 10
        volume_ratio = current["volume"] / avg_volume if avg_volume > 0 else 0

        # Fixed readiness calculation - properly scale based on proximity to breakout
        threshold = 1.0  # 1% breakout threshold from config
        if breakout_pct < -2:
            breakout_readiness = 0  # Far below resistance
        elif breakout_pct < 0:
            # Below resistance: scale 0-70% based on proximity
            breakout_readiness = (breakout_pct + 2) * 35
        elif breakout_pct < threshold:
            # Between resistance and threshold: 70-90%
            breakout_readiness = 70 + (breakout_pct / threshold) * 20
        else:
            # Above threshold: 90-100%
            breakout_readiness = min(100, 90 + (breakout_pct - threshold) * 10)

        volume_readiness = min(100, (volume_ratio / 1.5) * 100)
        readiness = breakout_readiness * 0.7 + volume_readiness * 0.3

        status = (
            "READY 🟢"
            if readiness >= 90
            else ("CLOSE 🟡" if readiness >= 70 else "WAITING ⚪")
        )

        return {
            "readiness": round(readiness, 2),
            "details": f"Breakout: {breakout_pct:.1f}%, Vol: {volume_ratio:.1f}x",
            "status": status,
        }

    def calculate_channel_readiness(self, data, current) -> Dict:
        """Calculate channel trading readiness"""
        prices = [d["close"] for d in data[-20:]]
        high = max(prices)
        low = min(prices)
        current_price = current["close"]

        position = (current_price - low) / (high - low) * 100 if high != low else 50

        # Best to buy at bottom of channel
        if position <= 35:
            readiness = 100 - (position / 35 * 20)
        else:
            readiness = max(0, 80 - (position - 35) * 1.6)

        status = (
            "BUY ZONE 🟢"
            if readiness >= 80
            else ("NEUTRAL 🟡" if readiness >= 30 else "SELL ZONE 🔴")
        )

        return {
            "readiness": round(readiness, 2),
            "details": f"Position: {position:.0f}% of channel",
            "status": status,
        }

    def calculate_dca_readiness(self, data, current) -> Dict:
        """Calculate DCA readiness"""
        high_20 = max(d["high"] for d in data[-20:])
        drop_from_high = ((current["close"] - high_20) / high_20) * 100

        dca_threshold = self.simple_rules.dca_drop_threshold

        if drop_from_high <= dca_threshold:
            extra_drop = abs(drop_from_high - dca_threshold)
            readiness = min(100, 80 + extra_drop * 4)
        else:
            distance_to_threshold = abs(drop_from_high - dca_threshold)
            readiness = max(0, 80 - distance_to_threshold * 20)

        status = (
            "READY 🟢"
            if readiness >= 80
            else ("CLOSE 🟡" if readiness >= 60 else "WAITING ⚪")
        )

        return {
            "readiness": round(readiness, 2),
            "details": f"Drop: {drop_from_high:.1f}% from high",
            "status": status,
        }

    async def clear_old_cache(self):
        """Clear cache entries older than 10 minutes"""
        try:
            cutoff = (datetime.now() - timedelta(minutes=10)).isoformat()
            self.db.client.table("strategy_status_cache").delete().lt(
                "calculated_at", cutoff
            ).execute()
            logger.info("Cleared old cache entries")
        except Exception as e:
            logger.warning(f"Could not clear old cache: {str(e)[:100]}")

    async def save_to_cache(self, swing, channel, dca):
        """Save calculated results to cache"""
        try:
            # Combine all candidates
            all_entries = []

            for item in swing:
                all_entries.append(
                    {
                        "symbol": item["symbol"],
                        "strategy_name": item["strategy_name"],
                        "readiness": item["readiness"],
                        "current_price": item["current_price"],
                        "details": item["details"],
                        "status": item["status"],
                        "calculated_at": datetime.now().isoformat(),
                    }
                )

            for item in channel:
                all_entries.append(
                    {
                        "symbol": item["symbol"],
                        "strategy_name": item["strategy_name"],
                        "readiness": item["readiness"],
                        "current_price": item["current_price"],
                        "details": item["details"],
                        "status": item["status"],
                        "calculated_at": datetime.now().isoformat(),
                    }
                )

            for item in dca:
                all_entries.append(
                    {
                        "symbol": item["symbol"],
                        "strategy_name": item["strategy_name"],
                        "readiness": item["readiness"],
                        "current_price": item["current_price"],
                        "details": item["details"],
                        "status": item["status"],
                        "calculated_at": datetime.now().isoformat(),
                    }
                )

            # Upsert to cache (handles duplicates by updating)
            self.db.client.table("strategy_status_cache").upsert(
                all_entries, on_conflict="symbol,strategy_name"
            ).execute()
            logger.info(f"Saved {len(all_entries)} entries to cache")

        except Exception as e:
            logger.error(f"Error saving to cache: {e}")

    async def analyze_market_structure(self):
        """Analyze actual market structure instead of just counting signals"""
        try:
            # Focus on top coins for market analysis
            market_symbols = [
                "BTC",
                "ETH",
                "SOL",
                "BNB",
                "XRP",
                "ADA",
                "DOGE",
                "AVAX",
                "DOT",
                "POL",
            ]

            metrics = {
                "total_symbols": len(market_symbols),
                "avg_drop_from_high": 0,
                "avg_range_size": 0,
                "trending_up_count": 0,
                "trending_down_count": 0,
                "ranging_count": 0,
                "symbols_with_drop": 0,
                "symbols_with_surge": 0,
                "biggest_drop": 0,
                "biggest_drop_symbol": None,
            }

            for symbol in market_symbols:
                try:
                    # Fetch recent data for analysis
                    result = (
                        self.db.client.table("ohlc_recent")
                        .select("*")
                        .eq("symbol", symbol)
                        .eq("timeframe", "15m")
                        .order("timestamp", desc=True)
                        .limit(100)
                        .execute()
                    )

                    if not result.data or len(result.data) < 50:
                        continue

                    data = result.data[::-1]  # Reverse to chronological

                    # Calculate drop from recent high (20 bars = 5 hours)
                    high_20 = max(d["high"] for d in data[-20:])
                    low_20 = min(d["low"] for d in data[-20:])
                    current = data[-1]["close"]

                    drop_from_high = ((current - high_20) / high_20) * 100
                    metrics["avg_drop_from_high"] += drop_from_high

                    # Track biggest drop
                    if drop_from_high < metrics["biggest_drop"]:
                        metrics["biggest_drop"] = drop_from_high
                        metrics["biggest_drop_symbol"] = symbol

                    # Count symbols with significant drops
                    if drop_from_high < -1.5:
                        metrics["symbols_with_drop"] += 1

                    # Calculate range size
                    range_size = ((high_20 - low_20) / low_20) * 100
                    metrics["avg_range_size"] += range_size

                    # Determine trend (using 20 vs 50 bar SMAs)
                    if len(data) >= 50:
                        sma_20 = sum(d["close"] for d in data[-20:]) / 20
                        sma_50 = sum(d["close"] for d in data[-50:]) / 50

                        if sma_20 > sma_50 * 1.02:  # Up trend (2% above)
                            metrics["trending_up_count"] += 1
                        elif sma_20 < sma_50 * 0.98:  # Down trend (2% below)
                            metrics["trending_down_count"] += 1
                        else:  # Ranging
                            metrics["ranging_count"] += 1

                    # Check for volume surge
                    recent_vol = data[-1]["volume"]
                    avg_vol = sum(d["volume"] for d in data[-20:]) / 20
                    if recent_vol > avg_vol * 1.5:
                        metrics["symbols_with_surge"] += 1

                except Exception as e:
                    logger.warning(f"Error analyzing {symbol}: {str(e)[:50]}")
                    continue

            # Calculate averages
            if metrics["total_symbols"] > 0:
                metrics["avg_drop_from_high"] /= metrics["total_symbols"]
                metrics["avg_range_size"] /= metrics["total_symbols"]

            logger.info(
                f"""
📊 Market Structure Analysis:
   Average Drop: {metrics['avg_drop_from_high']:.1f}%
   Average Range: {metrics['avg_range_size']:.1f}%
   Trending Up: {metrics['trending_up_count']}/{metrics['total_symbols']}
   Trending Down: {metrics['trending_down_count']}/{metrics['total_symbols']}
   Ranging: {metrics['ranging_count']}/{metrics['total_symbols']}
   Symbols with >1.5% drop: {metrics['symbols_with_drop']}
   Biggest Drop: {metrics['biggest_drop']:.1f}% ({metrics['biggest_drop_symbol']})
            """
            )

            return metrics

        except Exception as e:
            logger.error(f"Error analyzing market structure: {e}")
            return None

    def determine_best_strategy_from_structure(self, metrics):
        """Determine best strategy based on actual market structure, not signal counts"""
        if not metrics:
            return "CHANNEL", "NEUTRAL", "Unable to analyze market"

        condition = "NEUTRAL"
        best_strategy = "CHANNEL"  # Default
        notes = ""

        # Decision tree based on market reality

        # 1. Significant market-wide drop detected -> DCA opportunity
        if metrics["avg_drop_from_high"] < -1.5 or metrics["symbols_with_drop"] >= 4:
            best_strategy = "DCA"
            condition = "DIP OPPORTUNITY"
            notes = (
                f"Market dropped {abs(metrics['avg_drop_from_high']):.1f}% - "
                f"{metrics['symbols_with_drop']} coins down >1.5%"
            )

        # 2. Strong upward momentum with volume -> SWING opportunity
        elif metrics["trending_up_count"] >= 6 and metrics["symbols_with_surge"] >= 3:
            best_strategy = "SWING"
            condition = "BREAKOUT MOMENTUM"
            notes = (
                f"{metrics['trending_up_count']} coins trending up with volume surges"
            )

        # 3. Downtrend but not sharp drop -> Wait or careful DCA
        elif metrics["trending_down_count"] >= 6:
            if metrics["avg_drop_from_high"] < -1.0:
                best_strategy = "DCA"
                condition = "GRADUAL DECLINE"
                notes = "Market declining - selective DCA opportunities"
            else:
                best_strategy = "WAIT"
                condition = "DOWNTREND"
                notes = "Market trending down - wait for better entries"

        # 4. Low volatility ranging market -> CHANNEL trading
        elif metrics["ranging_count"] >= 5 and metrics["avg_range_size"] < 4:
            best_strategy = "CHANNEL"
            condition = "RANGE-BOUND"
            notes = f"Market ranging in {metrics['avg_range_size']:.1f}% band - ideal for channel trading"

        # 5. Mixed signals but some upward momentum -> Look for SWING
        elif metrics["trending_up_count"] > metrics["trending_down_count"]:
            best_strategy = "SWING"
            condition = "SELECTIVE MOMENTUM"
            notes = f"{metrics['trending_up_count']} coins showing strength"

        # 6. Default to CHANNEL in unclear conditions
        else:
            best_strategy = "CHANNEL"
            condition = "NEUTRAL"
            notes = "Mixed market - channel trading at extremes"

        logger.info(f"📈 Strategy Decision: {best_strategy} - {condition}")
        logger.info(f"   Reasoning: {notes}")

        return best_strategy, condition, notes

    async def calculate_market_summary(self, swing, channel, dca):
        """Calculate and save market summary using market structure analysis"""
        try:
            # Keep signal counts for reference
            ready_swing = sum(1 for s in swing if s["readiness"] >= 90)
            ready_channel = sum(1 for c in channel if c["readiness"] >= 80)
            ready_dca = sum(1 for d in dca if d["readiness"] >= 80)

            logger.info(
                f"Signal Counts - Swing: {ready_swing}, Channel: {ready_channel}, DCA: {ready_dca}"
            )

            # Analyze actual market structure
            market_metrics = await self.analyze_market_structure()

            # Determine best strategy based on market structure, not counts
            (
                best_strategy,
                condition,
                notes,
            ) = self.determine_best_strategy_from_structure(market_metrics)

            # Add signal availability info to notes
            signal_info = f" (Signals available: {ready_dca} DCA, {ready_swing} Swing, {ready_channel} Channel)"
            notes = notes + signal_info if notes else signal_info

            # Save to cache
            summary = {
                "condition": condition,
                "best_strategy": best_strategy,
                "notes": notes,
                "calculated_at": datetime.now().isoformat(),
            }

            self.db.client.table("market_summary_cache").insert(summary).execute()
            logger.info(f"Market summary: {condition} - Best: {best_strategy}")

        except Exception as e:
            logger.error(f"Error saving market summary: {e}")

    async def run_continuous(self):
        """Run continuously, updating every 5 minutes"""
        logger.info("Starting continuous pre-calculation service...")
        logger.info("Updates every 5 minutes")

        while True:
            try:
                await self.calculate_all()
                await asyncio.sleep(300)  # 5 minutes
            except KeyboardInterrupt:
                logger.info("Stopping pre-calculator...")
                break
            except Exception as e:
                logger.error(f"Error in continuous run: {e}")
                await asyncio.sleep(60)  # Retry after 1 minute on error


async def main():
    """Run the pre-calculator"""
    calculator = StrategyPreCalculator()

    # Run once or continuously
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--continuous", action="store_true", help="Run continuously")
    args = parser.parse_args()

    if args.continuous:
        await calculator.run_continuous()
    else:
        await calculator.calculate_all()


if __name__ == "__main__":
    asyncio.run(main())
