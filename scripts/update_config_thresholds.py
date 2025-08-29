import json
from datetime import datetime

# Read the current config
with open("configs/paper_trading_config_unified.json", "r") as f:
    config = json.load(f)

# Update version and timestamp
config["version"] = "1.0.16"
config["last_updated"] = datetime.now().isoformat()

# Update DCA detection thresholds by tier (aggressive-leaning for ML data)
config["strategies"]["DCA"]["detection_thresholds_by_tier"] = {
    "large_cap": {
        "drop_threshold": -1.75,  # More aggressive (was -3.1)
        "volume_requirement": 0.75,  # More lenient (was 0.85)
        "volume_threshold": 100000,
        "grid_levels": 3,
        "grid_spacing": 0.02,
    },
    "mid_cap": {
        "drop_threshold": -2.25,  # More aggressive (was -4.0)
        "volume_requirement": 0.85,  # Keep current
        "volume_threshold": 75000,
        "grid_levels": 4,
        "grid_spacing": 0.025,
    },
    "small_cap": {
        "drop_threshold": -3.0,  # More aggressive (was -4.5)
        "volume_requirement": 0.9,  # Slightly stricter (was 0.8)
        "volume_threshold": 50000,
        "grid_levels": 5,
        "grid_spacing": 0.03,
    },
    "memecoin": {
        "drop_threshold": -4.0,  # More aggressive (was -5.0)
        "volume_requirement": 1.1,  # Stricter for memecoins (was 0.75)
        "volume_threshold": 25000,
        "grid_levels": 5,
        "grid_spacing": 0.04,
    },
}

# Also update the default fallback threshold to be the mid_cap value
config["strategies"]["DCA"]["detection_thresholds"]["drop_threshold"] = -2.25

# Write the updated config
with open("configs/paper_trading_config_unified.json", "w") as f:
    json.dump(config, f, indent=2)

print("Configuration updated successfully!")
print("\nNew DCA tiered thresholds:")
for tier, settings in config["strategies"]["DCA"][
    "detection_thresholds_by_tier"
].items():
    print(
        f"  {tier}: drop={settings['drop_threshold']}%, volume={settings['volume_requirement']}x"
    )
