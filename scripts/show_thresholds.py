#!/usr/bin/env python3
"""Display current strategy thresholds"""

import json
from pathlib import Path

print("=" * 60)
print("📊 CURRENT STRATEGY THRESHOLDS FOR TRIGGERING TRADES")
print("=" * 60)

# Load paper trading config
config_path = Path("configs/paper_trading.json")
if config_path.exists():
    with open(config_path) as f:
        config = json.load(f)
else:
    print("Config file not found!")
    exit(1)

print("\n🎯 GLOBAL THRESHOLDS:")
print(f'  • ML Confidence Required: {config["ml_confidence_threshold"]*100:.0f}%')
print(f'  • Min Signal Strength: {config["min_signal_strength"]*100:.0f}%')
print(f'  • Required Confirmations: {config["required_confirmations"]}/3 indicators')
print(f'  • Max Positions: {config["max_positions"]}')
print(f'  • Risk Per Trade: {config["risk_per_trade"]*100:.0f}%')

print("\n💰 DCA STRATEGY:")
dca = config["strategies"]["DCA"]
print(f'  • Status: {"✅ ENABLED" if dca["enabled"] else "❌ DISABLED"}')
print(f'  • Min Confidence: {dca["min_confidence"]*100:.0f}%')
print(f"  • Price Drop Trigger: -5% from 4h high (hardcoded)")
print(f'  • Grid Levels: {dca["grid_levels"]} levels')
print(f'  • Grid Spacing: {dca["grid_spacing"]*100:.0f}%')
print(f'  • Volume Threshold: ${dca["volume_threshold"]:,}')

print("\n🎢 SWING STRATEGY:")
swing = config["strategies"]["SWING"]
print(f'  • Status: {"✅ ENABLED" if swing["enabled"] else "❌ DISABLED"}')
print(f'  • Min Confidence: {swing["min_confidence"]*100:.0f}%')
print(f"  • Min Score Required: 50 points (hardcoded)")
print(f'  • Breakout Confirmation: {swing["breakout_confirmation"]*100:.1f}%')
print(f'  • Volume Surge Required: {swing["volume_surge"]}x average')
print(f'  • Take Profit: {swing["take_profit"]*100:.0f}%')
print(f'  • Stop Loss: {swing["stop_loss"]*100:.0f}%')

print("\n📊 CHANNEL STRATEGY:")
channel = config["strategies"]["CHANNEL"]
print(f'  • Status: {"✅ ENABLED" if channel["enabled"] else "❌ DISABLED"}')
print(f'  • Min Confidence: {channel["min_confidence"]*100:.0f}%')
print(f'  • Entry at: {channel["entry_threshold"]*100:.0f}% of channel range')
print(f'  • Exit at: {channel["exit_threshold"]*100:.0f}% of channel range')
print(f'  • Min Channel Width: {channel["channel_width_min"]*100:.0f}%')
print(f'  • Required Touches: {channel["channel_touches"]} on each boundary')

print("\n📈 SCORING BREAKDOWN:")
print("\nSWING SCORING (100 points max, 50 min to trigger):")
print("  • Breakout Detection: 30 points")
print("  • Volume Confirmation: 20 points")
print("  • Trend Alignment: 20 points")
print("  • Momentum Indicators: 15 points")
print("  • Price Action (24h): 15 points")

print("\nDCA TRIGGERS:")
print("  • Price drops 5% from 4-hour high")
print("  • Volume above average")
print("  • Not in strong downtrend")
print("  • ML confidence > 50%")

print("\nCHANNEL TRIGGERS:")
print("  • Clear parallel channel formed")
print("  • At least 2 touches on each boundary")
print("  • Price near lower boundary (90% of range)")
print("  • Channel width between 2-10%")

print("\n⏰ LAST UPDATED:", config["updated_at"][:19])
print("=" * 60)
