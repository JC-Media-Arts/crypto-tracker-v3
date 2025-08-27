"""
Simple rule-based strategy detection for Phase 1 recovery
No ML, just basic technical rules with lowered thresholds
"""

from typing import Dict, List, Optional
from loguru import logger


class SimpleRules:
    """Simple rule-based strategy detection without ML"""

    def __init__(self, config: Dict = None):
        """Initialize with simplified thresholds from config"""
        self.config = config or {}

        # Load thresholds from config with sensible defaults
        self.dca_drop_threshold = self.config.get(
            "dca_drop_threshold", -4.0
        )  # Default: 4% drop from recent high
        self.swing_breakout_threshold = self.config.get(
            "swing_breakout_threshold", 1.015
        )  # Default: 1.5% breakout
        self.channel_position_threshold = self.config.get(
            "channel_position_threshold", 0.15
        )  # Default: Bottom/top 15% of range

        # Additional thresholds for proper detection
        self.swing_volume_surge = self.config.get(
            "swing_volume_surge", 1.5
        )  # Default: 1.5x average volume
        self.channel_touches = self.config.get(
            "channel_touches", 3
        )  # Default: 3 touches to confirm channel

        # Fixed confidence for all signals (no ML)
        self.fixed_confidence = 0.5

        logger.info(
            f"Simple Rules initialized: DCA={self.dca_drop_threshold}%, Swing={self.swing_breakout_threshold}%"
        )

    def check_dca_setup(self, symbol: str, data: List[Dict]) -> Optional[Dict]:
        """
        Simple DCA detection - just price drop from recent high

        Args:
            symbol: Trading symbol
            data: OHLC data (list of dicts with 'high', 'low', 'close', 'volume')

        Returns:
            Setup dict if conditions met, None otherwise
        """
        if not data or len(data) < 20:
            return None

        try:
            # Get current price and recent high
            current_price = data[-1]["close"]
            recent_high = max(d["high"] for d in data[-20:])

            # Calculate drop percentage
            drop_pct = ((current_price - recent_high) / recent_high) * 100

            # Simple rule: Signal if dropped enough
            if drop_pct <= self.dca_drop_threshold:
                return {
                    "strategy": "DCA",
                    "symbol": symbol,
                    "signal": True,
                    "drop_pct": drop_pct,
                    "current_price": current_price,
                    "recent_high": recent_high,
                    "confidence": self.fixed_confidence,
                    "ml_used": False,
                    "reason": f"Price dropped {drop_pct:.1f}% (threshold: {self.dca_drop_threshold}%)",
                }

        except Exception as e:
            logger.error(f"Error in DCA check for {symbol}: {e}")

        return None

    def check_swing_setup(self, symbol: str, data: List[Dict]) -> Optional[Dict]:
        """
        Simple Swing detection - price breakout with volume

        Args:
            symbol: Trading symbol
            data: OHLC data

        Returns:
            Setup dict if conditions met, None otherwise
        """
        if not data or len(data) < 10:
            return None

        try:
            # Get current bar and recent data
            current = data[-1]
            recent_data = data[-10:-1]  # Last 9 bars (exclude current)

            # Calculate breakout
            recent_high = max(d["high"] for d in recent_data)
            price_breakout = ((current["close"] - recent_high) / recent_high) * 100

            # Calculate volume surge
            avg_volume = sum(d["volume"] for d in recent_data) / len(recent_data)
            volume_surge = current["volume"] / avg_volume if avg_volume > 0 else 0

            # Simple rules: Breakout + Volume
            # Convert threshold to percentage (1.010 = 1% breakout)
            breakout_threshold_pct = (self.swing_breakout_threshold - 1) * 100
            if (
                price_breakout >= breakout_threshold_pct
                and volume_surge > self.swing_volume_surge
            ):
                return {
                    "strategy": "SWING",
                    "symbol": symbol,
                    "signal": True,
                    "breakout_pct": price_breakout,
                    "volume_surge": volume_surge,
                    "entry_price": current["close"],
                    "confidence": self.fixed_confidence,
                    "ml_used": False,
                    "reason": f"Breakout {price_breakout:.1f}% with {volume_surge:.1f}x volume",
                }

        except Exception as e:
            logger.error(f"Error in Swing check for {symbol}: {e}")

        return None

    def check_channel_setup(self, symbol: str, data: List[Dict]) -> Optional[Dict]:
        """
        Simple Channel detection - range-bound trading

        Args:
            symbol: Trading symbol
            data: OHLC data

        Returns:
            Setup dict if conditions met, None otherwise
        """
        if not data or len(data) < 20:
            return None

        try:
            # Get price range over last 20 bars
            prices = [d["close"] for d in data[-20:]]
            high = max(prices)
            low = min(prices)
            current = prices[-1]

            # Avoid division by zero
            if high == low:
                return None

            # Calculate position in range (0 = bottom, 1 = top)
            position = (current - low) / (high - low)

            # Signal at extremes
            if position <= self.channel_position_threshold:
                # Near bottom - BUY signal
                return {
                    "strategy": "CHANNEL",
                    "symbol": symbol,
                    "signal": True,
                    "signal_type": "BUY",
                    "position": position,
                    "channel_high": high,
                    "channel_low": low,
                    "entry_price": current,
                    "confidence": self.fixed_confidence,
                    "ml_used": False,
                    "reason": f"Near channel bottom ({position:.1%} position)",
                }
            elif position >= (1 - self.channel_position_threshold):
                # Near top - SELL signal (for existing positions)
                return {
                    "strategy": "CHANNEL",
                    "symbol": symbol,
                    "signal": True,
                    "signal_type": "SELL",
                    "position": position,
                    "channel_high": high,
                    "channel_low": low,
                    "entry_price": current,
                    "confidence": self.fixed_confidence,
                    "ml_used": False,
                    "reason": f"Near channel top ({position:.1%} position)",
                }

        except Exception as e:
            logger.error(f"Error in Channel check for {symbol}: {e}")

        return None

    def predict_dca(self, features: Dict) -> Dict:
        """
        Fake ML prediction for DCA - returns fixed confidence
        Used when ML is disabled but code expects ML format
        """
        return {
            "confidence": self.fixed_confidence,
            "win_probability": 0.5,
            "optimal_take_profit": 5.0,  # Fixed 5% TP
            "optimal_stop_loss": -3.0,  # Fixed 3% SL
            "predicted_hold_hours": 24,
            "ml_used": False,
        }

    def predict_swing(self, features: Dict) -> Dict:
        """
        Fake ML prediction for Swing - returns fixed confidence
        """
        return {
            "confidence": self.fixed_confidence,
            "breakout_success_probability": 0.5,
            "optimal_take_profit": 7.0,  # Fixed 7% TP
            "optimal_stop_loss": -3.0,  # Fixed 3% SL
            "ml_used": False,
        }

    def get_fixed_confidence(self) -> float:
        """Get the fixed confidence value used for all signals"""
        return self.fixed_confidence
