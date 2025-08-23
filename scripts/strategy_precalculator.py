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
        self.simple_rules = SimpleRules()

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

        # Readiness calculation
        breakout_readiness = min(100, max(0, (breakout_pct + 2) * 50))
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

    async def calculate_market_summary(self, swing, channel, dca):
        """Calculate and save market summary"""
        try:
            # Find best opportunities
            ready_swing = sum(1 for s in swing if s["readiness"] >= 90)
            ready_channel = sum(1 for c in channel if c["readiness"] >= 80)
            ready_dca = sum(1 for d in dca if d["readiness"] >= 80)

            if ready_channel > ready_swing and ready_channel > ready_dca:
                condition = "RANGE-BOUND"
                best_strategy = "CHANNEL"
                notes = f"{ready_channel} symbols in buy zone"
            elif ready_swing > ready_dca:
                condition = "BREAKOUT POTENTIAL"
                best_strategy = "SWING"
                notes = f"{ready_swing} symbols near breakout"
            elif ready_dca > 0:
                condition = "DIP OPPORTUNITY"
                best_strategy = "DCA"
                notes = f"{ready_dca} symbols ready for DCA"
            else:
                condition = "NEUTRAL"
                best_strategy = "WAIT"
                notes = "No strong setups currently"

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
