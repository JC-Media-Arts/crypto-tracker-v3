#!/usr/bin/env python3
"""
Script to disable ML and Shadow Testing systems for Phase 1 recovery
This creates a simplified rule-based trading system
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from loguru import logger

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))


def disable_ml_and_shadow():
    """Disable ML predictions and shadow testing"""

    logger.info("=" * 60)
    logger.info("PHASE 1.1: DISABLING ML AND SHADOW TESTING")
    logger.info("=" * 60)

    # Create configuration file to disable ML and shadow testing
    config = {
        "ml_enabled": False,
        "shadow_testing_enabled": False,
        "use_simple_rules": True,
        "phase": "recovery_phase_1",
        "updated_at": datetime.now().isoformat(),
        "notes": "ML and Shadow Testing disabled for Phase 1 recovery - focusing on pure rule-based trading",
        # Simplified thresholds (30% lower than original)
        "dca_config": {
            "drop_threshold": -3.5,  # Was -5.0, now 30% lower
            "min_confidence": 0.0,  # No ML confidence needed
            "use_ml": False,
        },
        "swing_config": {
            "breakout_threshold": 2.1,  # Was 3.0, now 30% lower
            "min_confidence": 0.0,  # No ML confidence needed
            "use_ml": False,
        },
        "channel_config": {
            "min_channel_strength": 0.42,  # Was 0.6, now 30% lower
            "min_confidence": 0.0,  # No ML confidence needed
            "use_ml": False,
        },
        # Aggressive test settings for more trades
        "trading_rules": {
            "max_open_positions": 10,  # Increased from 5
            "position_size": 50,  # Smaller positions for more trades
            "stop_loss": -3.0,  # Tighter stop loss
            "take_profit": 5.0,  # Lower take profit for more exits
            "time_exit_hours": 12,  # Exit after 12 hours
        },
    }

    # Save configuration
    config_path = Path("config/recovery_phase.json")
    config_path.parent.mkdir(exist_ok=True)

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    logger.info(f"✅ Configuration saved to {config_path}")

    # Create a modified strategy manager that doesn't use ML
    create_simple_strategy_manager()

    # Update environment variables file
    update_env_file()

    logger.info("")
    logger.info("CHANGES MADE:")
    logger.info("1. ❌ ML predictions disabled")
    logger.info("2. ❌ Shadow testing disabled")
    logger.info("3. ✅ Simple rule-based trading enabled")
    logger.info("4. ✅ Thresholds lowered by 30% for more signals")
    logger.info("5. ✅ Position limits increased to 10")
    logger.info("6. ✅ Position size reduced to $50")

    return config


def create_simple_strategy_manager():
    """Create a simplified strategy manager without ML"""

    simple_manager = '''#!/usr/bin/env python3
"""
Simplified Strategy Manager for Phase 1 Recovery
Pure rule-based trading without ML or Shadow Testing
"""

import asyncio
from typing import Dict, List
from datetime import datetime
from loguru import logger
from pathlib import Path
import json
import sys

sys.path.append(str(Path(__file__).parent.parent))

from src.strategies.dca.detector import DCADetector
from src.strategies.swing.detector import SwingDetector
from src.strategies.channel.detector import ChannelDetector
from src.data.hybrid_fetcher import HybridDataFetcher
from src.data.supabase_client import SupabaseClient


class SimpleStrategyManager:
    """Simplified manager without ML"""

    def __init__(self):
        # Load recovery config
        with open("config/recovery_phase.json", "r") as f:
            self.config = json.load(f)

        self.supabase = SupabaseClient()
        self.data_fetcher = HybridDataFetcher()

        # Initialize detectors with simplified config
        self.dca_detector = DCADetector(self.supabase)
        self.swing_detector = SwingDetector(self.supabase)
        self.channel_detector = ChannelDetector()

        # Simplified thresholds
        self.dca_threshold = self.config["dca_config"]["drop_threshold"]
        self.swing_threshold = self.config["swing_config"]["breakout_threshold"]
        self.channel_threshold = self.config["channel_config"]["min_channel_strength"]

        logger.info("✅ Simple Strategy Manager initialized (NO ML)")

    async def scan_all(self, symbols: List[str]) -> List[Dict]:
        """Scan all symbols with simple rules"""
        signals = []

        for symbol in symbols:
            # Get data
            data = await self.data_fetcher.get_recent_data(
                symbol=symbol,
                hours=24,
                timeframe="15m"
            )

            if not data:
                continue

            # Check DCA (simple oversold)
            dca_signal = self.check_dca_simple(symbol, data)
            if dca_signal:
                signals.append(dca_signal)

            # Check Swing (simple breakout)
            swing_signal = self.check_swing_simple(symbol, data)
            if swing_signal:
                signals.append(swing_signal)

            # Check Channel (simple bounce)
            channel_signal = self.check_channel_simple(symbol, data)
            if channel_signal:
                signals.append(channel_signal)

        logger.info(f"Found {len(signals)} signals (no ML filtering)")
        return signals

    def check_dca_simple(self, symbol: str, data: List[Dict]) -> Dict:
        """Simple DCA check - just price drop"""
        if len(data) < 20:
            return None

        current_price = data[-1]["close"]
        recent_high = max(d["high"] for d in data[-20:])

        drop_pct = ((current_price - recent_high) / recent_high) * 100

        if drop_pct <= self.dca_threshold:
            return {
                "strategy": "DCA",
                "symbol": symbol,
                "signal": True,
                "drop_pct": drop_pct,
                "confidence": 0.5,  # Fixed confidence
                "entry_price": current_price
            }
        return None

    def check_swing_simple(self, symbol: str, data: List[Dict]) -> Dict:
        """Simple Swing check - price and volume breakout"""
        if len(data) < 10:
            return None

        current = data[-1]
        recent_high = max(d["high"] for d in data[-10:-1])
        avg_volume = sum(d["volume"] for d in data[-10:-1]) / 9

        price_breakout = ((current["close"] - recent_high) / recent_high) * 100
        volume_surge = current["volume"] / avg_volume if avg_volume > 0 else 0

        if price_breakout >= self.swing_threshold and volume_surge > 1.5:
            return {
                "strategy": "SWING",
                "symbol": symbol,
                "signal": True,
                "breakout_pct": price_breakout,
                "volume_surge": volume_surge,
                "confidence": 0.5,  # Fixed confidence
                "entry_price": current["close"]
            }
        return None

    def check_channel_simple(self, symbol: str, data: List[Dict]) -> Dict:
        """Simple Channel check - range bound"""
        if len(data) < 20:
            return None

        prices = [d["close"] for d in data[-20:]]
        high = max(prices)
        low = min(prices)
        current = prices[-1]

        if high == low:
            return None

        position = (current - low) / (high - low)

        # Signal at channel extremes
        if position < 0.2 or position > 0.8:
            return {
                "strategy": "CHANNEL",
                "symbol": symbol,
                "signal": True,
                "position": position,
                "signal_type": "BUY" if position < 0.2 else "SELL",
                "confidence": 0.5,  # Fixed confidence
                "entry_price": current
            }
        return None


async def main():
    """Run simple strategy scanning"""
    manager = SimpleStrategyManager()

    symbols = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "AVAX", "DOGE"]

    while True:
        try:
            logger.info("Running simplified scan (NO ML)...")
            signals = await manager.scan_all(symbols)

            for signal in signals:
                logger.info(f"📊 {signal['strategy']} Signal: {signal['symbol']} @ ${signal['entry_price']:.2f}")

            await asyncio.sleep(60)

        except Exception as e:
            logger.error(f"Error: {e}")
            await asyncio.sleep(60)


if __name__ == "__main__":
    logger.info("Starting Simple Strategy Manager (Phase 1 Recovery)")
    asyncio.run(main())
'''

    # Save the simple manager
    simple_path = Path("scripts/simple_strategy_manager.py")
    with open(simple_path, "w") as f:
        f.write(simple_manager)

    # Make it executable
    simple_path.chmod(0o755)

    logger.info(f"✅ Created {simple_path}")


def update_env_file():
    """Add environment variables to disable ML and Shadow"""

    env_vars = """
# Phase 1 Recovery Settings
ML_ENABLED=false
SHADOW_TESTING_ENABLED=false
USE_SIMPLE_RULES=true
RECOVERY_PHASE=1
MIN_CONFIDENCE=0.0
"""

    env_path = Path(".env.recovery")
    with open(env_path, "w") as f:
        f.write(env_vars)

    logger.info(f"✅ Created {env_path}")

    # Also update the main settings to check for these
    logger.info("ℹ️  To activate: export $(cat .env.recovery | xargs)")


if __name__ == "__main__":
    try:
        config = disable_ml_and_shadow()

        logger.info("")
        logger.info("=" * 60)
        logger.info("NEXT STEPS:")
        logger.info("1. Stop current processes: make stop-all")
        logger.info("2. Activate recovery mode: export $(cat .env.recovery | xargs)")
        logger.info("3. Run simple scanner: python scripts/simple_strategy_manager.py")
        logger.info("4. Start paper trading with lower thresholds")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Error disabling ML/Shadow: {e}")
        sys.exit(1)
