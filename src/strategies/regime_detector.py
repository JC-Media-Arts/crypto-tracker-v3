"""
Market Regime Detector - MVP Circuit Breaker Version
Provides fast protection against flash crashes and market panics
"""

from typing import Dict, Optional, Tuple, List
from datetime import datetime, timedelta
from collections import deque
from loguru import logger
from enum import Enum
import json
import os
import asyncio
from src.notifications.slack_notifier import SlackNotifier, NotificationType


class MarketRegime(Enum):
    """Market regime states"""

    PANIC = "PANIC"  # BTC down >3% in 1hr or extreme volatility - Stop all new trades
    CAUTION = "CAUTION"  # BTC down >2% in 1hr or >5% in 4hr - Reduce positions by 50%
    EUPHORIA = (
        "EUPHORIA"  # BTC up >3% in 1hr or high volatility up - Be careful with FOMO
    )
    NORMAL = "NORMAL"  # Business as usual


class RegimeDetector:
    """
    MVP Circuit Breaker for flash crash protection
    Monitors BTC price changes and adjusts trading behavior
    """

    def __init__(
        self, enabled: bool = True, config_path: str = "configs/paper_trading.json"
    ):
        """
        Initialize the regime detector with enhanced market protection

        Args:
            enabled: Whether the circuit breaker is active (can disable for testing)
            config_path: Path to configuration file
        """
        self.enabled = enabled
        self.btc_prices = deque(
            maxlen=2880
        )  # Store 48 hours of minute data for cumulative decline
        self.price_history = (
            []
        )  # List of (timestamp, price) tuples for volatility calculation
        self.last_regime = MarketRegime.NORMAL
        self.last_alert_time = None
        self.alert_cooldown = 300  # 5 minutes between alerts

        # Track disabled strategies
        self.disabled_strategies = (
            {}
        )  # {strategy: {'time': timestamp, 'volatility': float}}
        self.strategy_reenable_times = {}  # {strategy: datetime}

        # Load configuration
        self.config = self._load_config(config_path)
        self.market_protection = self.config.get("market_protection", {})

        # Initialize Slack notifier for PANIC alerts
        self.slack_notifier = None
        slack_webhook = os.getenv("SLACK_WEBHOOK_TRADES")
        if slack_webhook:
            try:
                self.slack_notifier = SlackNotifier(webhook_url=slack_webhook)
                logger.info("Slack notifier initialized for PANIC alerts to #trades")
            except Exception as e:
                logger.error(f"Failed to initialize Slack notifier: {e}")
        else:
            logger.warning("No SLACK_WEBHOOK_TRADES configured - PANIC alerts disabled")

        logger.info(f"Enhanced Regime Detector initialized (enabled={enabled})")
        logger.info(
            f"Market Protection: {self.market_protection.get('enabled', False)}"
        )

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

        # Also maintain price history for volatility calculation
        self.price_history.append((timestamp, price))
        # Keep only last 48 hours
        cutoff = datetime.now() - timedelta(hours=48)
        self.price_history = [(t, p) for t, p in self.price_history if t >= cutoff]

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
        Enhanced regime detection with multiple triggers including volatility

        Returns:
            Current MarketRegime state
        """
        if not self.enabled:
            return MarketRegime.NORMAL

        # Get all metrics
        btc_1h = self.get_btc_change(hours=1)
        btc_4h = self.get_btc_change(hours=4)
        btc_24h = self.get_btc_change(hours=24)
        volatility_24h = self.calculate_volatility(24)
        volatility_4h = self.calculate_volatility(4)  # Medium-term volatility
        has_cumulative_decline = self.check_cumulative_decline()

        # Default to NORMAL if insufficient data
        if btc_1h is None:
            return MarketRegime.NORMAL

        # PANIC conditions (any one triggers) - highest priority
        panic_conditions = [
            btc_1h and btc_1h <= -3.0,  # Flash crash: 3% drop in 1 hour
            btc_24h and btc_24h <= -5.0,  # Daily crash: 5% drop in 24 hours
            volatility_24h
            and volatility_24h
            >= self.market_protection.get("volatility_thresholds", {}).get(
                "panic", 12.0
            ),  # Extreme volatility
            has_cumulative_decline,  # Slow bleed detected
        ]

        if any(panic_conditions):
            regime = MarketRegime.PANIC
            if regime != self.last_regime:
                self._log_regime_change(regime, btc_1h, btc_4h)
                self.last_regime = regime
                # Send immediate PANIC alert
                if self.market_protection.get("alerts", {}).get(
                    "immediate_panic", True
                ):
                    self._send_panic_alert(btc_1h, btc_24h, volatility_24h)
            return regime

        # CAUTION conditions
        caution_conditions = [
            btc_1h and btc_1h <= -2.0,  # Quick drop: 2% in 1 hour
            btc_4h and btc_4h <= -3.0,  # Reduced from -5% for earlier detection
            btc_24h and btc_24h <= -3.0,  # Daily weakness
            volatility_24h
            and volatility_24h
            >= self.market_protection.get("volatility_thresholds", {}).get(
                "high", 8.0
            ),  # High volatility
        ]

        if any(caution_conditions):
            regime = MarketRegime.CAUTION
            if regime != self.last_regime:
                self._log_regime_change(regime, btc_1h, btc_4h)
                self.last_regime = regime
            return regime

        # EUPHORIA conditions (rapid rise OR high volatility up)
        euphoria_conditions = [
            btc_1h and btc_1h >= 3.0,  # Quick pump: 3% in 1 hour
            btc_24h and btc_24h >= 8.0,  # Daily FOMO: 8% in 24 hours
            volatility_24h
            and volatility_24h
            >= self.market_protection.get("volatility_thresholds", {}).get("high", 8.0)
            and btc_1h
            and btc_1h > 0,  # Volatile upward movement
        ]

        if any(euphoria_conditions):
            regime = MarketRegime.EUPHORIA
            if regime != self.last_regime:
                self._log_regime_change(regime, btc_1h, btc_4h)
                self.last_regime = regime
            return regime

        # Otherwise NORMAL
        regime = MarketRegime.NORMAL
        if regime != self.last_regime:
            self._log_regime_change(regime, btc_1h, btc_4h)
            self.last_regime = regime

        return regime

    def _send_panic_alert(self, btc_1h: float, btc_24h: float, volatility: float):
        """Send immediate Slack alert for PANIC regime"""
        logger.critical(f"🚨🚨🚨 MARKET PANIC DETECTED!")
        logger.critical(
            f"BTC 1h: {btc_1h:.2f}%, 24h: {btc_24h:.2f}%, Volatility: {volatility:.2f}%"
        )
        logger.critical(f"ALL NEW TRADES HALTED!")

        # Send Slack alert if configured
        if self.slack_notifier and self.market_protection.get("alerts", {}).get(
            "immediate_panic", True
        ):
            try:
                # Determine the primary trigger
                trigger_reason = []
                if btc_1h <= -5:
                    trigger_reason.append(f"BTC 1h drop: {btc_1h:.1f}%")
                if btc_24h <= -10:
                    trigger_reason.append(f"BTC 24h drop: {btc_24h:.1f}%")
                if volatility >= 12:
                    trigger_reason.append(f"Extreme volatility: {volatility:.1f}%")

                asyncio.run(
                    self.slack_notifier.send_notification(
                        title="🚨🚨🚨 MARKET PANIC DETECTED - TRADING HALTED",
                        message=f"All new trades have been automatically halted due to extreme market conditions.",
                        notification_type=NotificationType.REGIME_CHANGE,
                        color="danger",
                        details={
                            "Trigger": " | ".join(trigger_reason)
                            if trigger_reason
                            else "Multiple conditions",
                            "BTC 1h Change": f"{btc_1h:+.2f}%",
                            "BTC 24h Change": f"{btc_24h:+.2f}%",
                            "Market Volatility": f"{volatility:.2f}%",
                            "Protection Status": "🛑 FULL PROTECTION ACTIVATED",
                            "Action Required": "Monitor market conditions. System will resume automatically when stable.",
                        },
                    )
                )
                logger.info("PANIC alert sent to Slack #trades channel")
            except Exception as e:
                logger.error(f"Failed to send PANIC alert to Slack: {e}")

    def _log_regime_change(
        self, new_regime: MarketRegime, btc_1h: float, btc_4h: Optional[float]
    ):
        """Log regime changes with appropriate severity"""
        btc_4h_str = f"{btc_4h:.1f}%" if btc_4h is not None else "N/A"

        if new_regime == MarketRegime.PANIC:
            logger.error(f"🚨 MARKET PANIC! BTC 1h: {btc_1h:.1f}%, 4h: {btc_4h_str}")
        elif new_regime == MarketRegime.CAUTION:
            logger.warning(
                f"⚠️ MARKET CAUTION! BTC 1h: {btc_1h:.1f}%, 4h: {btc_4h_str}"
            )
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
        btc_24h = self.get_btc_change(hours=24)
        volatility_24h = self.calculate_volatility(24)
        volatility_smoothed = self.calculate_volatility_smoothed(24)
        regime = self.get_market_regime()

        return {
            "current_regime": regime.value,
            "btc_1h_change": btc_1h,
            "btc_4h_change": btc_4h,
            "btc_24h_change": btc_24h,
            "volatility_24h": volatility_24h,
            "volatility_smoothed": volatility_smoothed,
            "position_multiplier": self.get_position_multiplier(regime),
            "disabled_strategies": list(self.disabled_strategies.keys()),
            "has_cumulative_decline": self.check_cumulative_decline(),
            "data_points": len(self.btc_prices),
            "enabled": self.enabled,
            "protection_enabled": self.market_protection.get("enabled", False),
        }

    def reset(self):
        """Reset the detector (useful for testing)"""
        self.btc_prices.clear()
        self.price_history.clear()
        self.last_regime = MarketRegime.NORMAL
        self.last_alert_time = None
        self.disabled_strategies.clear()
        self.strategy_reenable_times.clear()
        logger.info("Regime Detector reset")

    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file"""
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load config from {config_path}: {e}")
        return {}

    def calculate_volatility(self, hours: int = 24) -> Optional[float]:
        """
        Calculate price range volatility over period using 1-minute data

        Args:
            hours: Number of hours to calculate volatility over

        Returns:
            Volatility as percentage of price range
        """
        if len(self.price_history) < 2:
            return None

        # Get prices from last N hours
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_prices = [p for t, p in self.price_history if t >= cutoff_time]

        if len(recent_prices) < 2:
            return None

        high = max(recent_prices)
        low = min(recent_prices)
        open_price = recent_prices[0]

        if open_price == 0:
            return None

        # Calculate volatility as percentage range
        volatility = ((high - low) / open_price) * 100
        return volatility

    def calculate_volatility_smoothed(
        self, hours: int = 24, smooth_minutes: int = 5
    ) -> Optional[float]:
        """
        Calculate smoothed volatility using 5-minute averages for less noise

        Args:
            hours: Number of hours to calculate over
            smooth_minutes: Minutes to average for smoothing

        Returns:
            Smoothed volatility percentage
        """
        if len(self.price_history) < 2:
            return None

        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_data = [(t, p) for t, p in self.price_history if t >= cutoff_time]

        if len(recent_data) < smooth_minutes:
            return None

        # Group into 5-minute buckets and average
        smoothed_prices = []
        for i in range(0, len(recent_data), smooth_minutes):
            bucket = recent_data[i : i + smooth_minutes]
            if bucket:
                avg_price = sum(p for _, p in bucket) / len(bucket)
                smoothed_prices.append(avg_price)

        if len(smoothed_prices) < 2:
            return None

        high = max(smoothed_prices)
        low = min(smoothed_prices)
        open_price = smoothed_prices[0]

        if open_price == 0:
            return None

        volatility = ((high - low) / open_price) * 100
        return volatility

    def check_cumulative_decline(self) -> bool:
        """
        Check for slow, sustained decline over 24-48 hours
        Measures from peak to current (not point-to-point)

        Returns:
            True if cumulative decline threshold exceeded
        """
        if not self.market_protection.get("enabled", False):
            return False

        decline_config = self.market_protection.get("cumulative_decline", {})
        if not decline_config.get("check_from_peak", True):
            return False

        # Check 24-hour decline from peak
        cutoff_24h = datetime.now() - timedelta(hours=24)
        prices_24h = [p for t, p in self.price_history if t >= cutoff_24h]

        if prices_24h and len(prices_24h) >= 10:  # Need some data
            peak_24h = max(prices_24h)
            current = prices_24h[-1]
            decline_24h = ((current - peak_24h) / peak_24h) * 100

            threshold_24h = decline_config.get("24h_threshold", -3.0)
            if decline_24h <= threshold_24h:
                logger.warning(
                    f"24h cumulative decline detected: {decline_24h:.2f}% from peak"
                )
                return True

        # Check 48-hour decline from peak
        cutoff_48h = datetime.now() - timedelta(hours=48)
        prices_48h = [p for t, p in self.price_history if t >= cutoff_48h]

        if prices_48h and len(prices_48h) >= 10:
            peak_48h = max(prices_48h)
            current = prices_48h[-1]
            decline_48h = ((current - peak_48h) / peak_48h) * 100

            threshold_48h = decline_config.get("48h_threshold", -5.0)
            if decline_48h <= threshold_48h:
                logger.warning(
                    f"48h cumulative decline detected: {decline_48h:.2f}% from peak"
                )
                return True

        return False

    def should_disable_strategy(self, strategy: str) -> bool:
        """
        Check if specific strategy should be disabled based on volatility

        Args:
            strategy: Strategy name (CHANNEL, SWING, DCA)

        Returns:
            True if strategy should be disabled
        """
        if not self.market_protection.get("enabled", False):
            return False

        volatility = self.calculate_volatility(24)
        if volatility is None:
            return False

        # Check if already disabled and in cooldown
        if strategy in self.strategy_reenable_times:
            if datetime.now() < self.strategy_reenable_times[strategy]:
                return True  # Still in cooldown
            else:
                # Check if volatility low enough to re-enable (hysteresis)
                hysteresis = self.market_protection.get("hysteresis", {})
                reenable_vol = hysteresis.get("channel_reenable_volatility", 6.0)

                if strategy == "CHANNEL" and volatility <= reenable_vol:
                    del self.strategy_reenable_times[strategy]
                    del self.disabled_strategies[strategy]
                    logger.info(
                        f"Re-enabling {strategy} strategy (volatility: {volatility:.2f}%)"
                    )
                    return False

        # Get strategy-specific volatility limits
        limits = self.market_protection.get("volatility_thresholds", {}).get(
            "strategy_limits", {}
        )
        limit = limits.get(strategy, 100.0)

        if volatility >= limit:
            if strategy not in self.disabled_strategies:
                # First time disabling
                self.disabled_strategies[strategy] = {
                    "time": datetime.now(),
                    "volatility": volatility,
                }

                # Set re-enable time
                cooldown_hours = self.market_protection.get("hysteresis", {}).get(
                    "reenable_cooldown_hours", 2
                )
                self.strategy_reenable_times[strategy] = datetime.now() + timedelta(
                    hours=cooldown_hours
                )

                logger.warning(
                    f"Disabling {strategy} strategy due to volatility: {volatility:.2f}% >= {limit}%"
                )

                # Send immediate alert for first CHANNEL disable
                if strategy == "CHANNEL" and self.market_protection.get(
                    "alerts", {}
                ).get("immediate_channel_disable", True):
                    self._send_strategy_disable_alert(strategy, volatility)

            return True

        return False

    def _send_strategy_disable_alert(self, strategy: str, volatility: float):
        """Send immediate Slack alert for strategy disable"""
        logger.critical(
            f"🚨 STRATEGY DISABLED: {strategy} (volatility: {volatility:.2f}%)"
        )

        # Send Slack alert if configured (only for first CHANNEL disable)
        if (
            self.slack_notifier
            and strategy == "CHANNEL"
            and self.market_protection.get("alerts", {}).get(
                "immediate_channel_disable", True
            )
        ):
            try:
                # Get re-enable time
                reenable_time = self.strategy_reenable_times.get(strategy)
                reenable_str = (
                    reenable_time.strftime("%H:%M %Z") if reenable_time else "Unknown"
                )

                asyncio.run(
                    self.slack_notifier.send_notification(
                        title=f"⚠️ {strategy} STRATEGY DISABLED",
                        message=f"The {strategy} strategy has been automatically disabled due to high market volatility.",
                        notification_type=NotificationType.REGIME_CHANGE,
                        color="warning",
                        details={
                            "Reason": f"Market volatility exceeded {strategy} threshold",
                            "Current Volatility": f"{volatility:.2f}%",
                            "Threshold": f"{self.market_protection.get('volatility_thresholds', {}).get('strategy_limits', {}).get(strategy, 'N/A')}%",
                            "Re-enable Volatility": f"{self.market_protection.get('hysteresis', {}).get('channel_reenable_volatility', 6.0)}%",
                            "Estimated Re-enable": reenable_str,
                            "Note": "Strategy will re-enable automatically when volatility drops",
                        },
                    )
                )
                logger.info(f"{strategy} disable alert sent to Slack #trades channel")
            except Exception as e:
                logger.error(f"Failed to send {strategy} disable alert to Slack: {e}")
