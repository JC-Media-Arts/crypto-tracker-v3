"""
Market Regime Detector - MVP Circuit Breaker Version
Provides fast protection against flash crashes and market panics
"""

from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from collections import deque
from loguru import logger
from enum import Enum


class MarketRegime(Enum):
    """Market regime states"""

    PANIC = "PANIC"  # BTC down >3% in 1hr - Stop all new trades
    CAUTION = "CAUTION"  # BTC down >2% in 1hr or >5% in 4hr - Reduce positions by 50%
    EUPHORIA = "EUPHORIA"  # BTC up >3% in 1hr - Be careful with FOMO
    NORMAL = "NORMAL"  # Business as usual


class RegimeDetector:
    """
    MVP Circuit Breaker for flash crash protection
    Monitors BTC price changes and adjusts trading behavior
    """

    def __init__(self, enabled: bool = True):
        """
        Initialize the regime detector

        Args:
            enabled: Whether the circuit breaker is active (can disable for testing)
        """
        self.enabled = enabled
        self.btc_prices = deque(maxlen=240)  # Store 4 hours of minute data
        self.last_regime = MarketRegime.NORMAL
        self.last_alert_time = None
        self.alert_cooldown = 300  # 5 minutes between alerts

        logger.info(f"Regime Detector initialized (enabled={enabled})")

    def update_btc_price(self, price: float, timestamp: Optional[datetime] = None):
        """
        Update BTC price cache

        Args:
            price: Current BTC price
            timestamp: Price timestamp (defaults to now)
        """
        if not self.enabled:
            return

        if timestamp is None:
            timestamp = datetime.now()

        self.btc_prices.append({"price": price, "timestamp": timestamp})

    def get_btc_change(self, hours: float = 1) -> Optional[float]:
        """
        Calculate BTC price change over specified hours

        Args:
            hours: Number of hours to look back

        Returns:
            Percentage change or None if insufficient data
        """
        if not self.btc_prices or len(self.btc_prices) < 2:
            return None

        current_price = self.btc_prices[-1]["price"]
        current_time = self.btc_prices[-1]["timestamp"]
        target_time = current_time - timedelta(hours=hours)

        # Find price closest to target time
        past_price = None
        for price_data in self.btc_prices:
            if price_data["timestamp"] <= target_time:
                past_price = price_data["price"]
                break  # Use first price that's old enough

        if past_price is None:
            # Not enough history, use oldest available if we have some data
            if len(self.btc_prices) >= 2:  # Need at least 2 prices
                past_price = self.btc_prices[0]["price"]
            else:
                return None

        # Calculate percentage change
        change = ((current_price - past_price) / past_price) * 100
        return change

    def get_market_regime(self) -> MarketRegime:
        """
        Determine current market regime based on BTC movements

        Returns:
            Current MarketRegime state
        """
        if not self.enabled:
            return MarketRegime.NORMAL

        # Get BTC changes
        btc_1h = self.get_btc_change(hours=1)
        btc_4h = self.get_btc_change(hours=4)

        # Default to NORMAL if insufficient data
        if btc_1h is None:
            return MarketRegime.NORMAL

        # Check for PANIC (highest priority)
        if btc_1h <= -3:
            regime = MarketRegime.PANIC

        # Check for CAUTION
        elif btc_1h <= -2 or (btc_4h is not None and btc_4h <= -5):
            regime = MarketRegime.CAUTION

        # Check for EUPHORIA
        elif btc_1h >= 3:
            regime = MarketRegime.EUPHORIA

        # Otherwise NORMAL
        else:
            regime = MarketRegime.NORMAL

        # Log regime changes
        if regime != self.last_regime:
            self._log_regime_change(regime, btc_1h, btc_4h)
            self.last_regime = regime

        return regime

    def _log_regime_change(
        self, new_regime: MarketRegime, btc_1h: float, btc_4h: Optional[float]
    ):
        """Log regime changes with appropriate severity"""
        btc_4h_str = f"{btc_4h:.1f}%" if btc_4h is not None else "N/A"

        if new_regime == MarketRegime.PANIC:
            logger.error(f"🚨 MARKET PANIC! BTC 1h: {btc_1h:.1f}%, 4h: {btc_4h_str}")
        elif new_regime == MarketRegime.CAUTION:
            logger.warning(f"⚠️ MARKET CAUTION! BTC 1h: {btc_1h:.1f}%, 4h: {btc_4h_str}")
        elif new_regime == MarketRegime.EUPHORIA:
            logger.warning(
                f"🚀 MARKET EUPHORIA! BTC 1h: {btc_1h:.1f}%, 4h: {btc_4h_str}"
            )
        else:
            logger.info(f"✅ MARKET NORMAL. BTC 1h: {btc_1h:.1f}%, 4h: {btc_4h_str}")

    def should_send_alert(self) -> bool:
        """Check if we should send a Slack alert (with cooldown)"""
        if self.last_alert_time is None:
            return True

        time_since_alert = (datetime.now() - self.last_alert_time).total_seconds()
        return time_since_alert >= self.alert_cooldown

    def get_position_multiplier(self, regime: Optional[MarketRegime] = None) -> float:
        """
        Get position size multiplier based on regime

        Args:
            regime: Market regime (uses current if not provided)

        Returns:
            Multiplier for position sizing (0.0 to 1.0)
        """
        if not self.enabled:
            return 1.0

        if regime is None:
            regime = self.get_market_regime()

        multipliers = {
            MarketRegime.PANIC: 0.0,  # No new positions
            MarketRegime.CAUTION: 0.5,  # Half size
            MarketRegime.EUPHORIA: 0.7,  # Slightly reduced (FOMO protection)
            MarketRegime.NORMAL: 1.0,  # Full size
        }

        return multipliers.get(regime, 1.0)

    def get_regime_stats(self) -> Dict:
        """Get current regime statistics for monitoring"""
        btc_1h = self.get_btc_change(hours=1)
        btc_4h = self.get_btc_change(hours=4)
        regime = self.get_market_regime()

        return {
            "current_regime": regime.value,
            "btc_1h_change": btc_1h,
            "btc_4h_change": btc_4h,
            "position_multiplier": self.get_position_multiplier(regime),
            "data_points": len(self.btc_prices),
            "enabled": self.enabled,
        }

    def reset(self):
        """Reset the detector (useful for testing)"""
        self.btc_prices.clear()
        self.last_regime = MarketRegime.NORMAL
        self.last_alert_time = None
        logger.info("Regime Detector reset")
