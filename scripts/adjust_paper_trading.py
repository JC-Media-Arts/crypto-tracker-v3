#!/usr/bin/env python3
"""
Adjust paper trading thresholds to be less conservative and generate more trades
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))


def adjust_thresholds():
    """Make paper trading less conservative to actually generate trades"""

    print("=" * 60)
    print("📊 ADJUSTING PAPER TRADING THRESHOLDS")
    print("=" * 60)

    # New loosened configuration
    config = {
        "ml_confidence_threshold": 0.55,  # Down from 0.70 (accept 55% confidence)
        "min_signal_strength": 0.6,  # Down from 0.80 (accept moderate signals)
        "required_confirmations": 2,  # Down from 3 (need 2/3 indicators)
        "position_size_multiplier": 1.5,  # Up from 1.0 (take larger positions)
        "max_positions": 5,  # Keep at 5
        "risk_per_trade": 0.02,  # 2% risk per trade (up from 0.5%)
        "stop_loss_percentage": 0.02,  # 2% stop loss
        "take_profit_percentage": 0.05,  # 5% take profit
        "trailing_stop": True,  # Enable trailing stops
        "trailing_stop_percentage": 0.015,  # 1.5% trailing stop
        "strategies": {
            "DCA": {
                "enabled": True,
                "min_confidence": 0.50,  # Very loose for DCA
                "grid_levels": 5,
                "grid_spacing": 0.02,  # 2% grid spacing
                "max_grids_per_symbol": 3,
                "volume_threshold": 100000,  # Minimum volume
            },
            "SWING": {
                "enabled": True,
                "min_confidence": 0.55,  # Moderate confidence needed
                "take_profit": 0.05,  # 5% profit target
                "stop_loss": 0.02,  # 2% stop loss
                "breakout_confirmation": 0.015,  # 1.5% breakout needed
                "volume_surge": 1.5,  # 1.5x volume surge
            },
            "CHANNEL": {
                "enabled": True,
                "min_confidence": 0.55,  # Moderate confidence needed
                "entry_threshold": 0.90,  # Enter at 90% of channel range
                "exit_threshold": 0.10,  # Exit at 10% of channel range
                "channel_width_min": 0.02,  # Minimum 2% channel width
                "channel_touches": 2,  # Minimum touches required
            },
        },
        "timeframes": {
            "primary": "15m",  # Primary timeframe
            "confirmation": "1h",  # Confirmation timeframe
            "trend": "4h",  # Trend timeframe
        },
        "filters": {
            "min_volume_24h": 100000,  # Minimum 24h volume
            "min_price": 0.01,  # Minimum price
            "max_spread": 0.005,  # Maximum 0.5% spread
            "avoid_news_hours": False,  # Trade during news (more opportunities)
            "trade_weekends": True,  # Trade on weekends
        },
        "updated_at": datetime.utcnow().isoformat(),
    }

    # Create configs directory if it doesn't exist
    config_dir = Path("configs")
    config_dir.mkdir(exist_ok=True)

    # Save to config directory
    config_file = config_dir / "paper_trading.json"
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\n✅ Configuration saved to: {config_file}")

    # Also create a Python config file for direct import
    py_config_file = config_dir / "paper_trading_config.py"
    with open(py_config_file, "w") as f:
        f.write('"""Paper trading configuration with loosened thresholds"""\n\n')
        f.write("PAPER_TRADING_CONFIG = ")
        f.write(json.dumps(config, indent=4))
        f.write("\n")

    print(f"✅ Python config saved to: {py_config_file}")

    print("\n📈 New settings summary:")
    print("-" * 40)
    print("  • ML Confidence: 55% (was 70%)")
    print("  • Min Signal: 60% (was 80%)")
    print("  • Confirmations: 2/3 (was 3/3)")
    print("  • Position Size: 1.5x larger")
    print("  • Risk per Trade: 2% (was 0.5%)")
    print("  • All 3 strategies enabled")

    print("\n🎯 Expected impact:")
    print("-" * 40)
    print("  • 3-5x more trade signals")
    print("  • Faster entry on opportunities")
    print("  • More diverse strategy mix")
    print("  • Higher trading frequency")

    # Check if .env file exists and suggest updates
    env_file = Path(".env")
    if env_file.exists():
        print("\n📝 Add these to your .env file:")
        print("-" * 40)
        print("# Paper Trading Thresholds (Loosened)")
        print("PAPER_TRADING_ML_THRESHOLD=0.55")
        print("PAPER_TRADING_MIN_SIGNAL=0.60")
        print("PAPER_TRADING_RISK_PER_TRADE=0.02")
        print("PAPER_TRADING_CONFIRMATIONS=2")
        print("PAPER_TRADING_POSITION_MULTIPLIER=1.5")
        print("")
        print("# Strategy Enablement")
        print("ENABLE_DCA_STRATEGY=true")
        print("ENABLE_SWING_STRATEGY=true")
        print("ENABLE_CHANNEL_STRATEGY=true")
        print("")
        print("# SWING Strategy Settings")
        print("SWING_MIN_VOLUME=100000")
        print("SWING_MIN_BREAKOUT_STRENGTH=1.5")
        print("SWING_VOLUME_SURGE_THRESHOLD=1.5")
        print("SWING_MIN_TOUCHES=2")
        print("SWING_LOOKBACK_PERIODS=20")
        print("")
        print("# CHANNEL Strategy Settings")
        print("CHANNEL_MIN_VOLUME=100000")
        print("CHANNEL_MIN_TOUCHES=2")
        print("CHANNEL_BREAKOUT_THRESHOLD=0.02")
        print("CHANNEL_WIDTH_MIN=0.02")
        print("CHANNEL_WIDTH_MAX=0.15")
        print("CHANNEL_LOOKBACK_PERIODS=20")

    return config


def verify_paper_trading_script():
    """Check if paper trading script will use new config"""
    paper_trading_script = Path("scripts/run_paper_trading.py")

    if paper_trading_script.exists():
        with open(paper_trading_script, "r") as f:
            content = f.read()

        print("\n🔍 Checking paper trading script...")
        print("-" * 40)

        if "paper_trading.json" in content or "paper_trading_config" in content:
            print("✅ Paper trading script appears to read config")
        else:
            print("⚠️  Paper trading script may need updating to use new config")
            print("   Consider adding:")
            print("   from configs.paper_trading_config import PAPER_TRADING_CONFIG")
    else:
        print("\n⚠️  Paper trading script not found at expected location")


if __name__ == "__main__":
    # Adjust thresholds
    new_config = adjust_thresholds()

    # Verify integration
    verify_paper_trading_script()

    print("\n✅ Threshold adjustment complete!")
    print("🚀 Paper trading should now generate 3-5x more signals")
