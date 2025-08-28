import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.data.supabase_client import SupabaseClient
import json
from datetime import datetime, timedelta, timezone

# Initialize Supabase client
client = SupabaseClient()

print("=== Checking CHANNEL Strategy Exit Parameters ===\n")

# First, let's see what columns we have
# Get one record to check structure
response = client.client.table("paper_trades").select("*").limit(1).execute()
if response.data:
    print("Available columns in paper_trades table:")
    print(list(response.data[0].keys()))
    print()

# Get recent trades with CHANNEL in metadata
response = (
    client.client.table("paper_trades")
    .select("*")
    .order("created_at", desc=True)
    .limit(100)
    .execute()
)

channel_trades = []
for trade in response.data:
    metadata = trade.get("metadata", "{}")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except:
            metadata = {}

    if metadata.get("strategy") == "CHANNEL":
        channel_trades.append(trade)

print(f"Found {len(channel_trades)} recent CHANNEL trades\n")

# Show open CHANNEL positions
open_trades = [t for t in channel_trades if t.get("status") == "OPEN"]
print(f"=== {len(open_trades)} OPEN CHANNEL Positions ===")

for trade in open_trades[:5]:  # Show first 5
    symbol = trade.get("symbol", "N/A")
    entry_price = trade.get("entry_price", 0)
    metadata = (
        json.loads(trade.get("metadata", "{}"))
        if isinstance(trade.get("metadata"), str)
        else trade.get("metadata", {})
    )

    # Extract exit parameters
    take_profit = metadata.get("take_profit", 0)
    stop_loss = metadata.get("stop_loss", 0)
    trailing_stop = metadata.get("trailing_stop", 0)

    print(f"\nSymbol: {symbol}")
    print(f"Entry Price: ${entry_price:.4f}")
    print(
        f"Take Profit: {take_profit*100:.1f}%"
        if take_profit
        else "Take Profit: Not set"
    )
    print(f"Stop Loss: {stop_loss*100:.1f}%" if stop_loss else "Stop Loss: Not set")
    print(
        f"Trailing Stop: {trailing_stop*100:.1f}%"
        if trailing_stop
        else "Trailing Stop: Not set"
    )

# Check closed trades
closed_trades = [t for t in channel_trades if t.get("status") == "CLOSED"]
print(f"\n\n=== {len(closed_trades)} Recent CLOSED CHANNEL Trades ===")

for trade in closed_trades[:5]:  # Show first 5
    symbol = trade.get("symbol", "N/A")
    entry_price = trade.get("entry_price", 0)
    exit_price = trade.get("exit_price", 0)
    exit_reason = trade.get("exit_reason", "N/A")

    # Calculate actual exit percentage
    if entry_price > 0:
        exit_pct = ((exit_price - entry_price) / entry_price) * 100
    else:
        exit_pct = 0

    print(f"\nSymbol: {symbol}")
    print(f"Entry: ${entry_price:.4f} -> Exit: ${exit_price:.4f} ({exit_pct:+.1f}%)")
    print(f"Exit Reason: {exit_reason}")

# Load the config to compare
from src.config.config_loader import ConfigLoader

config_loader = ConfigLoader()
config = config_loader.load()

print("\n\n=== CHANNEL Exit Parameters from Config ===")
channel_exits = config.get("strategies", {}).get("CHANNEL", {}).get("exits_by_tier", {})
for tier, params in channel_exits.items():
    print(f"\n{tier}:")
    print(f"  Take Profit: {params.get('take_profit', 0)*100:.1f}%")
    print(f"  Stop Loss: {params.get('stop_loss', 0)*100:.1f}%")
    print(f"  Trailing Stop: {params.get('trailing_stop', 0)*100:.1f}%")
