#!/usr/bin/env python3
"""Monitor OHLC backfill progress."""

import sys
from pathlib import Path
from datetime import datetime
import json

sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from loguru import logger


def get_symbol_list():
    """Get full list of symbols."""
    tier1 = [
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
    ]
    tier2 = [
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
    ]
    tier3 = [
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
    ]
    tier4 = [
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
        "ANKR",
        "CTSI",
        "YFI",
        "AUDIO",
        "ENJ",
    ]

    # Remove duplicate BLUR
    all_symbols = list(set(tier1 + tier2 + tier3 + tier4))
    return sorted(all_symbols)


def main():
    print("=" * 80)
    print("OHLC BACKFILL PROGRESS MONITOR")
    print("=" * 80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    supabase = SupabaseClient()
    all_symbols = get_symbol_list()

    # Check progress for each timeframe
    timeframes = ["1d", "1h", "15m", "1m"]

    print("Progress by Timeframe:")
    print("-" * 40)

    for tf in timeframes:
        # Get unique symbols with data for this timeframe
        result = (
            supabase.client.rpc("get_unique_symbols_by_timeframe", {"tf": tf}).execute() if False else None
        )  # RPC might not exist

        # Fallback: direct query
        try:
            result = supabase.client.table("ohlc_data").select("symbol").eq("timeframe", tf).execute()

            if result.data:
                unique_symbols = list(set([r["symbol"] for r in result.data]))
                progress_pct = (len(unique_symbols) / len(all_symbols)) * 100

                print(f"{tf:4} : {len(unique_symbols):3}/{len(all_symbols)} symbols ({progress_pct:.1f}%)")

                # Show which symbols are done
                if len(unique_symbols) > 0 and len(unique_symbols) < len(all_symbols):
                    missing = set(all_symbols) - set(unique_symbols)
                    if len(missing) <= 10:
                        print(f"       Missing: {', '.join(sorted(missing))}")
            else:
                print(f"{tf:4} : 0/{len(all_symbols)} symbols (0.0%)")

        except Exception as e:
            print(f"{tf:4} : Error checking - {e}")

    print()
    print("Detailed Statistics:")
    print("-" * 40)

    # Get total bar counts
    for tf in timeframes:
        try:
            result = (
                supabase.client.table("ohlc_data")
                .select("symbol", count="exact")
                .eq("timeframe", tf)
                .limit(1)
                .execute()
            )

            # This is a workaround - we need to query without limit to get true count
            # But for now, let's get sample data
            sample = (
                supabase.client.table("ohlc_data").select("symbol,timestamp").eq("timeframe", tf).limit(5000).execute()
            )

            if sample.data:
                symbols_with_data = list(set([r["symbol"] for r in sample.data]))
                approx_bars = len(sample.data)
                print(f"{tf:4} : ~{approx_bars:,} bars across {len(symbols_with_data)} symbols")

        except Exception as e:
            logger.error(f"Error getting stats for {tf}: {e}")

    print()

    # Check if backfill results file exists
    results_file = Path("data/backfill_results.json")
    if results_file.exists():
        print("Latest Backfill Results:")
        print("-" * 40)
        with open(results_file, "r") as f:
            results = json.load(f)
            for symbol in list(results.keys())[:5]:  # Show first 5
                print(f"{symbol}: ", end="")
                for tf, data in results[symbol].items():
                    if "new_bars" in data:
                        print(f"{tf}={data['new_bars']} ", end="")
                print()
            if len(results) > 5:
                print(f"... and {len(results)-5} more symbols")

    print()
    print("=" * 80)
    print("Note: Counts are approximate due to query limits")
    print("Check data/backfill_results.json for detailed progress")
    print("=" * 80)


if __name__ == "__main__":
    main()
