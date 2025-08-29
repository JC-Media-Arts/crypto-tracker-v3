import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.data.supabase_client import SupabaseClient
import json
from src.config.config_loader import ConfigLoader

# Initialize
client = SupabaseClient()
config_loader = ConfigLoader()
config = config_loader.load()

# Get CHANNEL trades
response = (
    client.client.table("paper_trades")
    .select("*")
    .eq("strategy_name", "CHANNEL")
    .eq("side", "BUY")
    .order("created_at", desc=True)
    .limit(20)
    .execute()
)

print("=== CHANNEL Strategy Exit Parameters Comparison ===\n")
print("Checking recent CHANNEL BUY trades...\n")

# Group by symbol to determine market cap tier
symbol_data = {}

for trade in response.data:
    symbol = trade.get("symbol")
    price = trade.get("price", 0)
    tp_price = trade.get("take_profit", 0)
    sl_price = trade.get("stop_loss", 0)
    trailing_stop_pct = trade.get("trailing_stop_pct", 0)

    if price > 0:
        # Calculate percentages
        tp_pct = ((tp_price - price) / price) * 100
        sl_pct = ((price - sl_price) / price) * 100

        symbol_data[symbol] = {
            "price": price,
            "tp_pct": tp_pct,
            "sl_pct": sl_pct,
            "trailing_stop_pct": trailing_stop_pct * 100,  # Convert to percentage
            "tp_price": tp_price,
            "sl_price": sl_price,
        }

# Load market cap tiers from config
market_cap_tiers = config.get("market_cap_tiers", {})
large_cap = market_cap_tiers.get("large_cap", [])
mid_cap = market_cap_tiers.get("mid_cap", [])
small_cap = market_cap_tiers.get("small_cap", [])
memecoin = market_cap_tiers.get("memecoin", [])


# Function to get tier
def get_tier(symbol):
    if symbol in large_cap:
        return "large_cap"
    elif symbol in mid_cap:
        return "mid_cap"
    elif symbol in small_cap:
        return "small_cap"
    elif symbol in memecoin:
        return "memecoin"
    else:
        return "unknown"


# Get CHANNEL exit parameters from config
channel_exits = config.get("strategies", {}).get("CHANNEL", {}).get("exits_by_tier", {})

print("Symbol Analysis:")
print("-" * 80)

for symbol, data in symbol_data.items():
    tier = get_tier(symbol)
    config_params = channel_exits.get(tier, {})

    config_tp = config_params.get("take_profit", 0) * 100
    config_sl = config_params.get("stop_loss", 0) * 100
    config_trail = config_params.get("trailing_stop", 0) * 100

    print(f"\n{symbol} ({tier}):")
    print(f"  Entry Price: ${data['price']:.4f}")
    print(
        f"  Take Profit: ${data['tp_price']:.4f} ({data['tp_pct']:.2f}%) - Config: {config_tp:.1f}%"
    )
    print(
        f"  Stop Loss: ${data['sl_price']:.4f} ({data['sl_pct']:.2f}%) - Config: {config_sl:.1f}%"
    )
    print(
        f"  Trailing Stop: {data['trailing_stop_pct']:.1f}% - Config: {config_trail:.1f}%"
    )

    # Check for discrepancies
    tp_diff = abs(data["tp_pct"] - config_tp)
    sl_diff = abs(data["sl_pct"] - config_sl)
    trail_diff = abs(data["trailing_stop_pct"] - config_trail)

    if tp_diff > 0.1 or sl_diff > 0.1 or trail_diff > 0.1:
        print(f"  ⚠️  DISCREPANCY FOUND!")

print("\n\n=== Config Values for Reference ===")
for tier, params in channel_exits.items():
    print(f"\n{tier}:")
    print(f"  Take Profit: {params.get('take_profit', 0)*100:.1f}%")
    print(f"  Stop Loss: {params.get('stop_loss', 0)*100:.1f}%")
    print(f"  Trailing Stop: {params.get('trailing_stop', 0)*100:.1f}%")
