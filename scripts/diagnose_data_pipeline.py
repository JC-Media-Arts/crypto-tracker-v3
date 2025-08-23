#!/usr/bin/env python3
"""
Diagnose data pipeline issues - why only 1 symbol has data
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import requests
import time
from typing import List, Dict

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.config.settings import get_settings
from supabase import create_client, Client


def get_all_configured_symbols() -> List[str]:
    """Get the list of all configured symbols"""
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
        # Tier 4: Solid Mid-Caps (30 coins - partial list for testing)
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


def diagnose_database_state():
    """Check what's actually in the database"""
    print("=" * 80)
    print("DATABASE STATE DIAGNOSIS")
    print("=" * 80)

    settings = get_settings()
    supabase: Client = create_client(settings.supabase_url, settings.supabase_key)

    # 1. Check unique symbols in database
    print("\n1. CHECKING UNIQUE SYMBOLS IN DATABASE")
    print("-" * 40)

    try:
        # Get unique symbols
        result = supabase.table("ohlc_data").select("symbol").execute()

        if result.data:
            unique_symbols = set(row["symbol"] for row in result.data)
            print(f"✅ Found {len(unique_symbols)} unique symbols in database:")
            for symbol in sorted(unique_symbols)[:20]:  # Show first 20
                print(f"   - {symbol}")
            if len(unique_symbols) > 20:
                print(f"   ... and {len(unique_symbols) - 20} more")
        else:
            print("❌ No data found in ohlc_data table")

    except Exception as e:
        print(f"❌ Error querying database: {e}")

    # 2. Check data distribution by timeframe
    print("\n2. DATA DISTRIBUTION BY TIMEFRAME")
    print("-" * 40)

    timeframes = ["1m", "15m", "1h", "4h", "1d"]
    for tf in timeframes:
        try:
            # Count records for this timeframe
            result = (
                supabase.table("ohlc_data")
                .select("symbol", count="exact")
                .eq("timeframe", tf)
                .limit(1)
                .execute()
            )

            count = result.count if hasattr(result, "count") else 0

            # Get unique symbols for this timeframe
            symbol_result = (
                supabase.table("ohlc_data")
                .select("symbol")
                .eq("timeframe", tf)
                .execute()
            )

            if symbol_result.data:
                tf_symbols = set(row["symbol"] for row in symbol_result.data)
                print(f"{tf:4s}: {len(tf_symbols)} symbols, {count:,} total records")
            else:
                print(f"{tf:4s}: No data")

        except Exception as e:
            print(f"{tf:4s}: Error - {str(e)[:50]}")

    # 3. Check recent data updates
    print("\n3. RECENT DATA UPDATES (Last 24 Hours)")
    print("-" * 40)

    cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()

    try:
        result = (
            supabase.table("ohlc_data")
            .select("symbol, timeframe, timestamp")
            .gte("timestamp", cutoff)
            .order("timestamp", desc=True)
            .limit(100)
            .execute()
        )

        if result.data:
            recent_symbols = set(row["symbol"] for row in result.data)
            print(f"✅ {len(recent_symbols)} symbols updated in last 24h:")

            # Show sample of recent updates
            for row in result.data[:5]:
                print(
                    f"   {row['symbol']:6s} {row['timeframe']:4s} - {row['timestamp']}"
                )
        else:
            print("❌ No updates in last 24 hours")

    except Exception as e:
        print(f"❌ Error checking recent updates: {e}")


def check_polygon_api():
    """Test Polygon API directly"""
    print("\n" + "=" * 80)
    print("POLYGON API DIAGNOSIS")
    print("=" * 80)

    settings = get_settings()
    api_key = settings.polygon_api_key

    if not api_key:
        print("❌ No Polygon API key configured")
        return

    print("\n1. TESTING POLYGON API CONNECTION")
    print("-" * 40)

    # Test with a few symbols
    test_symbols = ["BTC", "ETH", "SOL", "PEPE", "WIF"]

    for symbol in test_symbols:
        ticker = f"X:{symbol}USD"
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/2024-01-01/{datetime.now().strftime('%Y-%m-%d')}"

        params = {"adjusted": "true", "sort": "desc", "limit": 1, "apiKey": api_key}

        try:
            response = requests.get(url, params=params, timeout=5)

            if response.status_code == 200:
                data = response.json()
                if data.get("results"):
                    print(
                        f"✅ {symbol}: Data available (latest: {datetime.fromtimestamp(data['results'][0]['t']/1000).date()})"
                    )
                else:
                    print(f"⚠️  {symbol}: No results returned")
            elif response.status_code == 429:
                print(f"❌ {symbol}: Rate limited!")
                # Check rate limit headers
                remaining = response.headers.get("X-RateLimit-Remaining", "unknown")
                reset = response.headers.get("X-RateLimit-Reset", "unknown")
                print(f"   Rate limit remaining: {remaining}")
                print(f"   Reset at: {reset}")
                break
            else:
                print(
                    f"❌ {symbol}: HTTP {response.status_code} - {response.text[:100]}"
                )

        except Exception as e:
            print(f"❌ {symbol}: Error - {e}")

        time.sleep(0.2)  # Small delay to avoid rate limiting

    # Check API key tier
    print("\n2. CHECKING API KEY TIER")
    print("-" * 40)

    try:
        # Make a simple request to check headers
        url = "https://api.polygon.io/v1/marketstatus/now"
        response = requests.get(url, params={"apiKey": api_key}, timeout=5)

        if response.status_code == 200:
            # Check rate limit headers
            limit = response.headers.get("X-RateLimit-Limit", "unknown")
            remaining = response.headers.get("X-RateLimit-Remaining", "unknown")

            print(f"Rate Limit: {remaining}/{limit} requests remaining")

            # Determine tier based on limit
            if limit != "unknown":
                limit_int = int(limit)
                if limit_int <= 5:
                    print("📊 API Tier: FREE (5 requests/minute)")
                    print("⚠️  WARNING: Free tier is very limited for 90 symbols!")
                elif limit_int <= 100:
                    print("📊 API Tier: STARTER")
                elif limit_int <= 1000:
                    print("📊 API Tier: DEVELOPER")
                else:
                    print("📊 API Tier: PROFESSIONAL or higher")
        else:
            print(f"Could not determine API tier: HTTP {response.status_code}")

    except Exception as e:
        print(f"Error checking API tier: {e}")


def check_missing_symbols():
    """Identify which symbols are missing data"""
    print("\n" + "=" * 80)
    print("MISSING SYMBOLS ANALYSIS")
    print("=" * 80)

    settings = get_settings()
    supabase: Client = create_client(settings.supabase_url, settings.supabase_key)

    configured_symbols = get_all_configured_symbols()

    print(f"\nConfigured symbols: {len(configured_symbols)}")

    # Get symbols that have data
    try:
        result = supabase.table("ohlc_data").select("symbol").execute()

        if result.data:
            symbols_with_data = set(row["symbol"] for row in result.data)
            missing_symbols = set(configured_symbols) - symbols_with_data

            print(f"Symbols with data: {len(symbols_with_data)}")
            print(f"Missing symbols: {len(missing_symbols)}")

            if missing_symbols:
                print("\nMissing symbols (need to backfill):")
                for i, symbol in enumerate(sorted(missing_symbols), 1):
                    print(f"  {i:2d}. {symbol}")
                    if i >= 20:
                        print(f"  ... and {len(missing_symbols) - 20} more")
                        break
        else:
            print("❌ No symbols have data - need complete backfill")

    except Exception as e:
        print(f"❌ Error checking missing symbols: {e}")


def suggest_solutions():
    """Suggest solutions based on diagnosis"""
    print("\n" + "=" * 80)
    print("RECOMMENDED SOLUTIONS")
    print("=" * 80)

    print(
        """
Based on the diagnosis, here are the recommended fixes:

1. **If Rate Limited (Free Tier)**:
   - Reduce number of symbols (90 is too many for free tier)
   - Upgrade Polygon API plan
   - Implement better rate limit handling
   - Use batch requests where possible

2. **If Missing Symbols**:
   Run backfill for all missing symbols:
   ```bash
   python scripts/fetch_all_historical_ohlc.py
   ```

3. **If Data is Stale**:
   Start the incremental updater:
   ```bash
   python scripts/incremental_ohlc_updater.py
   ```

4. **If WebSocket Issues**:
   Check data collector service:
   ```bash
   python scripts/run_data_collector.py
   ```

5. **For Production**:
   Set up scheduled updates:
   ```bash
   # Run every 5 minutes for 1m data
   */5 * * * * python scripts/incremental_ohlc_updater.py --timeframe 1m

   # Run every 15 minutes for 15m data
   */15 * * * * python scripts/incremental_ohlc_updater.py --timeframe 15m
   ```
"""
    )


def main():
    """Run all diagnostics"""
    print("\n" + "=" * 80)
    print("DATA PIPELINE DIAGNOSTIC REPORT")
    print("=" * 80)
    print(f"Timestamp: {datetime.now()}")
    print("=" * 80)

    # Run diagnostics
    diagnose_database_state()
    check_polygon_api()
    check_missing_symbols()
    suggest_solutions()

    print("\n" + "=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
