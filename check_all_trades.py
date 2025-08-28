import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.data.supabase_client import SupabaseClient
import json
from datetime import datetime, timedelta, timezone

# Initialize Supabase client
client = SupabaseClient()

# Get recent trades
response = (
    client.client.table("paper_trades")
    .select("*")
    .order("created_at", desc=True)
    .limit(10)
    .execute()
)

print(f"=== Found {len(response.data)} recent trades ===\n")

for i, trade in enumerate(response.data[:5]):
    print(f"\nTrade {i+1}:")
    print(f"Symbol: {trade.get('symbol')}")
    print(f"Side: {trade.get('side')}")
    print(f"Status: {trade.get('status')}")
    print(f"Strategy Name: {trade.get('strategy_name')}")
    print(f"Take Profit: {trade.get('take_profit')}")
    print(f"Stop Loss: {trade.get('stop_loss')}")
    print(f"Trailing Stop %: {trade.get('trailing_stop_pct')}")

    # Check metadata
    metadata = trade.get("metadata")
    if metadata:
        print(f"Metadata type: {type(metadata)}")
        if isinstance(metadata, str):
            try:
                metadata_dict = json.loads(metadata)
                print(
                    f"Metadata strategy: {metadata_dict.get('strategy', 'Not found')}"
                )
            except:
                print("Could not parse metadata")
    else:
        print("No metadata")

# Check if trades are stored with strategy_name column
print("\n\n=== Checking for CHANNEL strategy trades ===")
response = (
    client.client.table("paper_trades")
    .select("*")
    .eq("strategy_name", "CHANNEL")
    .order("created_at", desc=True)
    .limit(10)
    .execute()
)
print(f"Found {len(response.data)} trades with strategy_name='CHANNEL'")
