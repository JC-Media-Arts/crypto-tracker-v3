#!/usr/bin/env python3
"""Check DCA trigger conditions for all monitored coins"""

from src.data.hybrid_fetcher import HybridDataFetcher
from src.data.supabase_client import SupabaseClient
import asyncio


async def check_all_coins():
    fetcher = HybridDataFetcher()

    # Get the full list of symbols being monitored
    symbols = [
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

    print("=" * 70)
    print("DCA TRIGGER ANALYSIS - ALL MONITORED COINS")
    print("=" * 70)
    print("DCA triggers when price drops 3.5% from 4-hour high")
    print("-" * 70)
    print(
        f'{"Symbol":<8} {"Current":<10} {"4h High":<10} {"Drop %":<8} {"Need":<8} {"Status":<10}'
    )
    print("-" * 70)

    ready_to_trigger = []
    close_to_trigger = []

    for symbol in symbols:
        try:
            # Get last 4 hours of data
            data = await fetcher.get_recent_data(symbol, hours=4, timeframe="15m")

            if data and len(data) > 0:
                current = data[-1]["close"]
                high_4h = max(d["high"] for d in data)
                drop_pct = ((current - high_4h) / high_4h) * 100
                need_more = -3.5 - drop_pct

                # Determine status
                if drop_pct <= -3.5:
                    status = "✅ READY!"
                    ready_to_trigger.append((symbol, drop_pct))
                elif drop_pct <= -2.5:
                    status = "🟡 Close"
                    close_to_trigger.append((symbol, drop_pct))
                else:
                    status = "❌ Wait"

                # Format the output
                current_str = f"${current:.2f}"
                high_str = f"${high_4h:.2f}"

                print(
                    f"{symbol:<8} {current_str:<10} {high_str:<10} {drop_pct:>7.2f}% {need_more:>7.2f}% {status:<10}"
                )
        except Exception as e:
            print(f"{symbol:<8} Error fetching data: {str(e)[:30]}")

    print("-" * 70)
    print(f"\nSUMMARY:")
    print(f"  ✅ Ready to trigger DCA: {len(ready_to_trigger)} coins")
    if ready_to_trigger:
        for sym, drop in ready_to_trigger:
            print(f"     - {sym}: {drop:.2f}%")

    print(f"  🟡 Close to trigger (<1% away): {len(close_to_trigger)} coins")
    if close_to_trigger:
        for sym, drop in close_to_trigger:
            print(f"     - {sym}: {drop:.2f}%")

    print(
        f"  ❌ Waiting: {len(symbols) - len(ready_to_trigger) - len(close_to_trigger)} coins"
    )

    if len(ready_to_trigger) > 0:
        print(f"\n⚠️  {len(ready_to_trigger)} coins SHOULD be triggering DCA buys!")
        print("     Check if paper trader is running and processing these signals.")

    # Also check some smaller/more volatile coins
    print("\n" + "=" * 70)
    print("CHECKING ADDITIONAL VOLATILE COINS")
    print("-" * 70)

    volatile_coins = ["PEPE", "WIF", "BONK", "FLOKI", "RNDR", "INJ", "FET", "OCEAN"]

    for symbol in volatile_coins:
        try:
            data = await fetcher.get_recent_data(symbol, hours=4, timeframe="15m")
            if data and len(data) > 0:
                current = data[-1]["close"]
                high_4h = max(d["high"] for d in data)
                drop_pct = ((current - high_4h) / high_4h) * 100

                if drop_pct <= -3.5:
                    print(f"  {symbol}: {drop_pct:.2f}% ✅ Would trigger!")
                elif drop_pct <= -2.5:
                    print(f"  {symbol}: {drop_pct:.2f}% 🟡 Close")
        except:
            pass  # Skip if not available


asyncio.run(check_all_coins())
