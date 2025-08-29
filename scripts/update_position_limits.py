import json
from datetime import datetime

# Read the current config
with open('configs/paper_trading_config_unified.json', 'r') as f:
    config = json.load(f)

# Update version and timestamp
config['version'] = "1.0.18"
config['last_updated'] = datetime.now().isoformat()

# Update position limits
print("Updating position limits...")
print(f"  max_positions_total: {config['position_management']['max_positions_total']} → 150")
print(f"  max_positions_per_strategy: {config['position_management']['max_positions_per_strategy']} (unchanged)")

config['position_management']['max_positions_total'] = 150
config['position_management']['max_positions_per_strategy'] = 50

# Write the updated config
with open('configs/paper_trading_config_unified.json', 'w') as f:
    json.dump(config, f, indent=2)

print("\n✅ Configuration updated successfully!")
print(f"Version: {config['version']}")
print(f"Updated: {config['last_updated'][:19]}")
print("\nNew limits:")
print(f"  Total positions allowed: 150")
print(f"  Per strategy limit: 50")
print(f"  Per symbol limit: {config['position_management']['max_positions_per_symbol']}")
print("\nWith 74 open positions, the system now has 76 slots available for new trades!")
