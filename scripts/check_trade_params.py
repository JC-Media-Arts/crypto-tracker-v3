#!/usr/bin/env python3
"""Check actual parameters used in recent trades"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from datetime import datetime, timezone, timedelta
from src.data.supabase_client import SupabaseClient
import pandas as pd
import json

db = SupabaseClient()

# Get recent CHANNEL trades with their metadata
recent_cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()

result = (
    db.client.table("paper_trades")
    .select("symbol, price, created_at, trading_engine, parameters")
    .eq("strategy_name", "CHANNEL")
    .eq("side", "BUY")
    .gte("created_at", recent_cutoff)
    .order("created_at", desc=True)
    .limit(20)
    .execute()
)

if result.data:
    trades = pd.DataFrame(result.data)
    trades["created_at"] = pd.to_datetime(trades["created_at"])
    trades["minutes_ago"] = (
        datetime.now(timezone.utc) - trades["created_at"]
    ).dt.total_seconds() / 60

    print(f"📊 Last 20 CHANNEL BUY trades (past 30 min):\n")

    # Group by trading engine
    engines = trades["trading_engine"].value_counts()
    print("Trading Engines:")
    for engine, count in engines.items():
        print(f"  {engine}: {count} trades")

    print(f"\n🔍 Sample Trade Details:")
    for idx, row in trades.head(5).iterrows():
        print(f"\n{row['symbol']} - {row['minutes_ago']:.0f} min ago")
        print(f"  Engine: {row['trading_engine']}")
        if row.get("parameters"):
            try:
                params = (
                    json.loads(row["parameters"])
                    if isinstance(row["parameters"], str)
                    else row["parameters"]
                )
                if isinstance(params, dict):
                    if "channel_position" in params:
                        print(f"  Channel Position: {params['channel_position']:.2%}")
                    if "buy_zone" in params:
                        print(f"  Buy Zone Used: {params['buy_zone']}")
                    print(f"  Params: {params}")
            except Exception as e:
                print(f"  Error parsing params: {e}")

# Check if there are trades from before and after config change
config_change_time = datetime.now(timezone.utc) - timedelta(minutes=10)  # Approximate
before = trades[trades["created_at"] < config_change_time]
after = trades[trades["created_at"] >= config_change_time]

print(f"\n⏰ Trade Timeline:")
print(f"  Before recent changes (10+ min ago): {len(before)} trades")
print(f"  After recent changes (last 10 min): {len(after)} trades")

# Check unique symbols
unique_symbols = trades["symbol"].nunique()
print(f"\n📈 Unique symbols traded: {unique_symbols}")
print(f"  Symbols: {', '.join(trades['symbol'].unique()[:10])}")

# Check if multiple trades per symbol
duplicates = trades[trades.duplicated(subset=["symbol"], keep=False)]
if not duplicates.empty:
    print(f"\n⚠️  Multiple trades on same symbols:")
    dup_counts = duplicates["symbol"].value_counts()
    for symbol, count in dup_counts.head(5).items():
        print(f"  {symbol}: {count} trades")
