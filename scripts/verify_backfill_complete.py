#!/usr/bin/env python3
"""
Comprehensive verification of OHLC data backfill
Checks data completeness, quality, and continuous updates
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Tuple
import pandas as pd

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.config.settings import get_settings
from supabase import create_client, Client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class BackfillVerifier:
    """Verify OHLC backfill completeness and quality"""

    def __init__(self):
        settings = get_settings()
        self.supabase = create_client(settings.supabase_url, settings.supabase_key)
        self.expected_symbols = self.get_expected_symbols()
        self.results = {
            "total_symbols": len(self.expected_symbols),
            "symbols_with_data": 0,
            "missing_symbols": [],
            "incomplete_symbols": [],
            "data_gaps": [],
            "quality_issues": [],
            "update_status": {},
            "summary": {},
        }

    def get_expected_symbols(self) -> List[str]:
        """Get list of all expected symbols"""
        return [
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
            # Tier 4: Solid Mid-Caps (30 coins)
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
        ]

    def verify_symbol_coverage(self):
        """Check which symbols have data"""
        print("\n" + "=" * 80)
        print("SYMBOL COVERAGE VERIFICATION")
        print("=" * 80)

        try:
            # Get unique symbols from database
            result = self.supabase.table("ohlc_data").select("symbol").execute()

            if result.data:
                symbols_in_db = set(row["symbol"] for row in result.data)
                self.results["symbols_with_data"] = len(symbols_in_db)

                # Find missing symbols
                missing = set(self.expected_symbols) - symbols_in_db
                self.results["missing_symbols"] = sorted(list(missing))

                # Find unexpected symbols
                unexpected = symbols_in_db - set(self.expected_symbols)

                print(f"Expected symbols: {len(self.expected_symbols)}")
                print(f"Symbols with data: {len(symbols_in_db)}")
                print(f"Missing symbols: {len(missing)}")

                if missing:
                    print(f"\n❌ Missing symbols: {', '.join(sorted(missing)[:10])}")
                    if len(missing) > 10:
                        print(f"   ... and {len(missing) - 10} more")
                else:
                    print("✅ All expected symbols have data!")

                if unexpected:
                    print(
                        f"\n⚠️  Unexpected symbols found: {', '.join(sorted(unexpected))}"
                    )

        except Exception as e:
            print(f"❌ Error checking symbol coverage: {e}")

    def verify_timeframe_coverage(self):
        """Check data completeness for each timeframe"""
        print("\n" + "=" * 80)
        print("TIMEFRAME COVERAGE VERIFICATION")
        print("=" * 80)

        timeframes = ["1d", "1h", "15m"]
        expected_bars = {
            "1d": 90,  # ~3 months of daily
            "1h": 800,  # ~33 days of hourly
            "15m": 3000,  # ~31 days of 15-min
        }

        for tf in timeframes:
            print(f"\n{tf} Timeframe:")
            print("-" * 40)

            incomplete = []

            for symbol in self.expected_symbols[
                :10
            ]:  # Check first 10 symbols as sample
                try:
                    result = (
                        self.supabase.table("ohlc_data")
                        .select("timestamp", count="exact")
                        .eq("symbol", symbol)
                        .eq("timeframe", tf)
                        .execute()
                    )

                    count = result.count if hasattr(result, "count") else 0

                    if count < expected_bars[tf] * 0.8:  # Allow 20% tolerance
                        incomplete.append(f"{symbol}({count})")

                except Exception as e:
                    incomplete.append(f"{symbol}(error)")

            if incomplete:
                print(f"⚠️  Incomplete data: {', '.join(incomplete[:5])}")
                self.results["incomplete_symbols"].extend(incomplete)
            else:
                print(f"✅ All sampled symbols have sufficient {tf} data")

    def verify_data_gaps(self):
        """Check for gaps in the data"""
        print("\n" + "=" * 80)
        print("DATA GAP ANALYSIS")
        print("=" * 80)

        # Sample check on BTC as representative
        test_symbols = ["BTC", "ETH", "SOL"]

        for symbol in test_symbols:
            print(f"\n{symbol}:")

            for timeframe in ["1d", "1h", "15m"]:
                try:
                    # Get recent data
                    cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()

                    result = (
                        self.supabase.table("ohlc_data")
                        .select("timestamp")
                        .eq("symbol", symbol)
                        .eq("timeframe", timeframe)
                        .gte("timestamp", cutoff)
                        .order("timestamp")
                        .execute()
                    )

                    if result.data and len(result.data) > 1:
                        timestamps = pd.to_datetime(
                            [row["timestamp"] for row in result.data]
                        )

                        # Expected frequency
                        freq_map = {
                            "1m": "1min",
                            "15m": "15min",
                            "1h": "1H",
                            "1d": "1D",
                        }
                        expected_freq = freq_map.get(timeframe, "1D")

                        # Check for gaps
                        expected_range = pd.date_range(
                            start=timestamps.min(),
                            end=timestamps.max(),
                            freq=expected_freq,
                        )

                        missing = set(expected_range) - set(timestamps)

                        if missing:
                            print(f"  {timeframe}: ⚠️  {len(missing)} gaps found")
                            self.results["data_gaps"].append(
                                {
                                    "symbol": symbol,
                                    "timeframe": timeframe,
                                    "gaps": len(missing),
                                }
                            )
                        else:
                            print(f"  {timeframe}: ✅ No gaps")
                    else:
                        print(f"  {timeframe}: No recent data")

                except Exception as e:
                    print(f"  {timeframe}: Error - {str(e)[:50]}")

    def verify_data_quality(self):
        """Check data quality (OHLC relationships, nulls, etc)"""
        print("\n" + "=" * 80)
        print("DATA QUALITY VERIFICATION")
        print("=" * 80)

        # Sample check
        sample_symbols = ["BTC", "ETH", "SOL", "PEPE", "WIF"]

        for symbol in sample_symbols:
            try:
                result = (
                    self.supabase.table("ohlc_data")
                    .select("open, high, low, close, volume")
                    .eq("symbol", symbol)
                    .eq("timeframe", "1d")
                    .limit(100)
                    .execute()
                )

                if result.data:
                    df = pd.DataFrame(result.data)

                    # Check OHLC relationships
                    invalid_ohlc = (
                        (df["high"] < df["low"])
                        | (df["high"] < df["open"])
                        | (df["high"] < df["close"])
                        | (df["low"] > df["open"])
                        | (df["low"] > df["close"])
                    ).sum()

                    # Check for nulls
                    null_count = df.isnull().sum().sum()

                    # Check for negative values
                    negative_count = (
                        (df[["open", "high", "low", "close", "volume"]] < 0).sum().sum()
                    )

                    if invalid_ohlc > 0 or null_count > 0 or negative_count > 0:
                        print(f"❌ {symbol}: Quality issues found")
                        self.results["quality_issues"].append(
                            {
                                "symbol": symbol,
                                "invalid_ohlc": invalid_ohlc,
                                "nulls": null_count,
                                "negatives": negative_count,
                            }
                        )
                    else:
                        print(f"✅ {symbol}: Data quality good")

            except Exception as e:
                print(f"❌ {symbol}: Error checking quality - {str(e)[:50]}")

    def verify_continuous_updates(self):
        """Check if continuous updates are working"""
        print("\n" + "=" * 80)
        print("CONTINUOUS UPDATE VERIFICATION")
        print("=" * 80)

        # Check data freshness
        cutoff_1h = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        cutoff_24h = (datetime.utcnow() - timedelta(hours=24)).isoformat()

        for timeframe in ["1m", "15m", "1h", "1d"]:
            try:
                # Check last hour
                result_1h = (
                    self.supabase.table("ohlc_data")
                    .select("symbol")
                    .eq("timeframe", timeframe)
                    .gte("timestamp", cutoff_1h)
                    .execute()
                )

                # Check last 24 hours
                result_24h = (
                    self.supabase.table("ohlc_data")
                    .select("symbol")
                    .eq("timeframe", timeframe)
                    .gte("timestamp", cutoff_24h)
                    .execute()
                )

                symbols_1h = (
                    set(row["symbol"] for row in result_1h.data)
                    if result_1h.data
                    else set()
                )
                symbols_24h = (
                    set(row["symbol"] for row in result_24h.data)
                    if result_24h.data
                    else set()
                )

                self.results["update_status"][timeframe] = {
                    "last_hour": len(symbols_1h),
                    "last_24h": len(symbols_24h),
                }

                print(f"\n{timeframe}:")
                print(f"  Last hour: {len(symbols_1h)} symbols updated")
                print(f"  Last 24h: {len(symbols_24h)} symbols updated")

                if timeframe in ["1m", "15m"] and len(symbols_1h) < 50:
                    print(f"  ⚠️  Low update rate for {timeframe}")
                elif len(symbols_24h) < 50:
                    print(f"  ⚠️  Updates may not be working properly")
                else:
                    print(f"  ✅ Updates working well")

            except Exception as e:
                print(f"{timeframe}: Error - {str(e)[:50]}")

    def generate_summary(self):
        """Generate final summary report"""
        print("\n" + "=" * 80)
        print("VERIFICATION SUMMARY")
        print("=" * 80)

        # Calculate scores
        coverage_score = (
            self.results["symbols_with_data"] / self.results["total_symbols"]
        ) * 100

        print(f"\n📊 OVERALL RESULTS:")
        print(f"  Symbol Coverage: {coverage_score:.1f}%")
        print(
            f"  Symbols with data: {self.results['symbols_with_data']}/{self.results['total_symbols']}"
        )

        if self.results["missing_symbols"]:
            print(f"  Missing symbols: {len(self.results['missing_symbols'])}")

        if self.results["data_gaps"]:
            print(
                f"  Symbols with gaps: {len(set(g['symbol'] for g in self.results['data_gaps']))}"
            )

        if self.results["quality_issues"]:
            print(
                f"  Quality issues found: {len(self.results['quality_issues'])} symbols"
            )

        # Update status
        if self.results["update_status"]:
            print(f"\n📈 UPDATE STATUS:")
            for tf, status in self.results["update_status"].items():
                print(f"  {tf}: {status['last_hour']} symbols in last hour")

        # Final verdict
        print(f"\n🎯 FINAL VERDICT:")

        if coverage_score >= 95 and not self.results["quality_issues"]:
            print("  ✅ BACKFILL SUCCESSFUL - Data pipeline fully operational!")
        elif coverage_score >= 80:
            print("  ⚠️  BACKFILL MOSTLY COMPLETE - Some issues to address")
        else:
            print("  ❌ BACKFILL INCOMPLETE - Significant issues found")

        # Recommendations
        if self.results["missing_symbols"]:
            print(f"\n📝 RECOMMENDATIONS:")
            print(
                f"  1. Re-run backfill for missing symbols: {', '.join(self.results['missing_symbols'][:5])}"
            )

        if self.results["data_gaps"]:
            print(f"  2. Fill gaps using incremental updater")

        if self.results["quality_issues"]:
            print(f"  3. Review and fix data quality issues")

        # Save detailed report
        self.save_report()

    def save_report(self):
        """Save detailed report to file"""
        report_file = (
            Path("data")
            / f"backfill_verification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        report_file.parent.mkdir(exist_ok=True)

        with open(report_file, "w") as f:
            f.write("OHLC BACKFILL VERIFICATION REPORT\n")
            f.write(f"Generated: {datetime.now()}\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"Total Expected Symbols: {self.results['total_symbols']}\n")
            f.write(f"Symbols with Data: {self.results['symbols_with_data']}\n")

            if self.results["missing_symbols"]:
                f.write(f"\nMissing Symbols:\n")
                for symbol in self.results["missing_symbols"]:
                    f.write(f"  - {symbol}\n")

            if self.results["data_gaps"]:
                f.write(f"\nData Gaps Found:\n")
                for gap in self.results["data_gaps"]:
                    f.write(
                        f"  - {gap['symbol']} {gap['timeframe']}: {gap['gaps']} gaps\n"
                    )

            if self.results["quality_issues"]:
                f.write(f"\nQuality Issues:\n")
                for issue in self.results["quality_issues"]:
                    f.write(f"  - {issue}\n")

        print(f"\n📄 Detailed report saved to: {report_file}")

    def run_verification(self):
        """Run all verification checks"""
        print("\n" + "=" * 80)
        print("OHLC BACKFILL VERIFICATION")
        print("=" * 80)
        print(f"Time: {datetime.now()}")
        print(f"Expected Symbols: {len(self.expected_symbols)}")

        # Run all checks
        self.verify_symbol_coverage()
        self.verify_timeframe_coverage()
        self.verify_data_gaps()
        self.verify_data_quality()
        self.verify_continuous_updates()
        self.generate_summary()


def main():
    """Main entry point"""
    verifier = BackfillVerifier()
    verifier.run_verification()


if __name__ == "__main__":
    main()
