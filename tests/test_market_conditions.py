#!/usr/bin/env python3
"""Test why strategies aren't finding setups"""

from src.strategies.dca.detector import DCADetector
from src.strategies.swing.detector import SwingDetector
from src.strategies.channel.detector import ChannelDetector
from src.data.hybrid_fetcher import HybridDataFetcher
from src.data.supabase_client import SupabaseClient
import asyncio


async def test_current_market():
    db = SupabaseClient()
    dca = DCADetector(db)
    swing = SwingDetector(db)
    channel = ChannelDetector()
    fetcher = HybridDataFetcher()

    print("Testing current market conditions...")
    print("=" * 60)

    symbols = ["BTC", "ETH", "SOL"]

    for symbol in symbols:
        print(f"\n{symbol} Analysis:")
        print("-" * 40)

        # Get data
        data = await fetcher.get_recent_data(symbol, hours=24, timeframe="15m")

        if data:
            # Calculate market metrics
            current = data[-1]["close"]
            high_4h = max(d["high"] for d in data[-16:])  # Last 4 hours (16 * 15min)
            high_24h = max(d["high"] for d in data)
            low_24h = min(d["low"] for d in data)

            drop_from_4h = ((current - high_4h) / high_4h) * 100
            drop_from_24h = ((current - high_24h) / high_24h) * 100
            range_pct = ((high_24h - low_24h) / low_24h) * 100

            print(f"  Current Price: ${current:.2f}")
            print(f"  4h High: ${high_4h:.2f}")
            print(f"  24h High: ${high_24h:.2f}")
            print(f"  24h Low: ${low_24h:.2f}")
            print(f"  Drop from 4h high: {drop_from_4h:.2f}%")
            print(f"  Drop from 24h high: {drop_from_24h:.2f}%")
            print(f"  24h Range: {range_pct:.2f}%")

            print(f"\n  Strategy Analysis:")

            # DCA needs -3.5% from 4h high
            print(f"  DCA: Needs {drop_from_4h:.2f}% / -3.5% drop")
            if drop_from_4h <= -3.5:
                print(f"    ✅ Would trigger!")
            else:
                need_more = -3.5 - drop_from_4h
                print(f"    ❌ Need {need_more:.2f}% more drop")

            # Swing needs breakout patterns
            print(f"  SWING: Looking for breakouts...")
            # Check if near 24h high (potential breakout)
            if current > high_24h * 0.98:  # Within 2% of high
                print(f"    📈 Near 24h high (potential breakout)")
            else:
                print(f"    ❌ Not in breakout zone")

            # Channel needs clear range
            print(f"  CHANNEL: Checking for channel...")
            if range_pct > 2 and range_pct < 10:
                position_in_range = (current - low_24h) / (high_24h - low_24h)
                print(f"    📊 Range exists ({range_pct:.1f}%)")
                print(f"    Position in range: {position_in_range:.1%}")
                if position_in_range > 0.8:
                    print(f"    ❌ Too high in range (need < 20%)")
                elif position_in_range < 0.2:
                    print(f"    ✅ Good entry position!")
            else:
                print(f"    ❌ No clear range")


asyncio.run(test_current_market())
