import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.data.supabase_client import SupabaseClient
import json
from datetime import datetime, timedelta, timezone

# Initialize Supabase client
client = SupabaseClient()

# Get recent CHANNEL trades
end_time = datetime.now(timezone.utc)
start_time = end_time - timedelta(days=1)

# Get open CHANNEL positions
response = (
    client.client.table("paper_trades")
    .select("*")
    .eq("status", "OPEN")
    .eq("strategy", "CHANNEL")
    .order("created_at", desc=True)
    .limit(10)
    .execute()
)

print("=== Recent OPEN CHANNEL Positions ===")
for trade in response.data:
    symbol = trade.get("symbol", "N/A")
    entry_price = trade.get("entry_price", 0)
    metadata = json.loads(trade.get("metadata", "{}"))

    # Extract exit parameters
    tp_price = metadata.get("take_profit_price", 0)
    sl_price = metadata.get("stop_loss_price", 0)
    trailing_stop_pct = metadata.get("trailing_stop_pct", 0)

    # Calculate percentages
    if entry_price > 0:
        tp_pct = ((tp_price - entry_price) / entry_price) * 100 if tp_price > 0 else 0
        sl_pct = ((entry_price - sl_price) / entry_price) * 100 if sl_price > 0 else 0
    else:
        tp_pct = sl_pct = 0

    print(f"\nSymbol: {symbol}")
    print(f"Entry Price: ${entry_price:.4f}")
    print(f"Take Profit: ${tp_price:.4f} ({tp_pct:.1f}%)")
    print(f"Stop Loss: ${sl_price:.4f} ({sl_pct:.1f}%)")
    print(f"Trailing Stop: {trailing_stop_pct:.1f}%")
    print(f"Metadata: {json.dumps(metadata, indent=2)}")

# Also check recent closed CHANNEL trades
print("\n\n=== Recent CLOSED CHANNEL Trades ===")
response = (
    client.client.table("paper_trades")
    .select("*")
    .eq("status", "CLOSED")
    .eq("strategy", "CHANNEL")
    .order("exit_time", desc=True)
    .limit(5)
    .execute()
)

for trade in response.data:
    symbol = trade.get("symbol", "N/A")
    entry_price = trade.get("entry_price", 0)
    exit_price = trade.get("exit_price", 0)
    metadata = json.loads(trade.get("metadata", "{}"))

    # Calculate actual exit percentage
    if entry_price > 0:
        exit_pct = ((exit_price - entry_price) / entry_price) * 100
    else:
        exit_pct = 0

    print(f"\nSymbol: {symbol}")
    print(f"Entry Price: ${entry_price:.4f}")
    print(f"Exit Price: ${exit_price:.4f} ({exit_pct:.1f}%)")
    print(f"Exit Reason: {trade.get('exit_reason', 'N/A')}")
