import json
from datetime import datetime

# Read the current config
with open('configs/paper_trading_config_unified.json', 'r') as f:
    config = json.load(f)

# Update version and timestamp
config['version'] = "1.0.17"
config['last_updated'] = datetime.now().isoformat()

# Update CHANNEL detection thresholds by tier (ML-Optimized)
config['strategies']['CHANNEL']['detection_thresholds_by_tier'] = {
    "large_cap": {
        "entry_threshold": 0.88,  # Tighter (was 0.85)
        "exit_threshold": 0.12,   # Adjusted accordingly
        "channel_width_min": 0.02,  # Keep current
        "channel_width_max": 0.08,  # Keep current
        "channel_strength_min": 0.82,  # Higher (was 0.8)
        "buy_zone": 0.025  # Tighter (was 0.03)
    },
    "mid_cap": {
        "entry_threshold": 0.87,  # Tighter (was 0.85)
        "exit_threshold": 0.13,
        "channel_width_min": 0.03,  # Keep current
        "channel_width_max": 0.10,  # Keep current
        "channel_strength_min": 0.77,  # Higher (was 0.75)
        "buy_zone": 0.04  # Tighter (was 0.05)
    },
    "small_cap": {
        "entry_threshold": 0.85,  # Keep current (94% win rate!)
        "exit_threshold": 0.15,
        "channel_width_min": 0.04,  # Keep current
        "channel_width_max": 0.12,  # Keep current
        "channel_strength_min": 0.72,  # Slightly higher (was 0.7)
        "buy_zone": 0.06  # Tighter (was 0.07)
    },
    "memecoin": {
        "entry_threshold": 0.92,  # MUCH looser (was 0.95)
        "exit_threshold": 0.08,
        "channel_width_min": 0.05,  # Keep current
        "channel_width_max": 0.15,  # Keep current
        "channel_strength_min": 0.60,  # Lower (was 0.65)
        "buy_zone": 0.12  # Wider (was 0.10)
    }
}

# Write the updated config
with open('configs/paper_trading_config_unified.json', 'w') as f:
    json.dump(config, f, indent=2)

print("CHANNEL configuration updated successfully!")
print("\nNew CHANNEL tiered thresholds:")
for tier, settings in config['strategies']['CHANNEL']['detection_thresholds_by_tier'].items():
    print(f"  {tier}:")
    print(f"    Entry: {settings['entry_threshold']} (near bottom)")
    print(f"    Buy zone: {settings['buy_zone']}")
    print(f"    Strength min: {settings['channel_strength_min']}")
