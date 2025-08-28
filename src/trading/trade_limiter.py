"""
Trade Frequency Limiter - Prevents repeated losses on same symbol (revenge trading protection)
Part of the Market Protection System
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import json
import os
from pathlib import Path
from loguru import logger
from src.config.config_loader import ConfigLoader


class TradeLimiter:
    """
    Prevents repeated losses on same symbol (revenge trading protection)
    Implements tier-based cooldowns and consecutive stop tracking
    """

    def __init__(
        self,
        config_path: str = "configs/paper_trading_config_unified.json",
        state_file: str = "data/trade_limiter_state.json",
    ):
        """
        Initialize the trade limiter with configuration

        Args:
            config_path: Path to configuration file
            state_file: Path to persistent state file
        """
        # Load configuration using ConfigLoader
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.load()
        self.market_protection = self.config.get("market_protection", {})
        self.limiter_config = self.market_protection.get("trade_limiter", {})

        # Track last stop loss time per symbol
        self.stop_loss_history: Dict[str, datetime] = {}

        # Track consecutive stops per symbol
        self.consecutive_stops: Dict[str, int] = {}

        # Track successful trades for reset logic
        self.last_trade_outcomes: Dict[str, str] = {}

        # Configuration from file or defaults
        self.cooldown_hours = self.limiter_config.get(
            "cooldown_hours_by_tier",
            {"large_cap": 4, "mid_cap": 6, "small_cap": 12, "memecoin": 24},
        )
        self.max_consecutive_stops = self.limiter_config.get("max_consecutive_stops", 3)
        self.ban_duration_hours = self.limiter_config.get("ban_duration_hours", 24)
        self.reset_on_50pct_tp = self.limiter_config.get("reset_on_50pct_tp", True)
        self.reset_on_trailing_stop = self.limiter_config.get(
            "reset_on_trailing_stop", True
        )

        # Market cap tiers for determining cooldowns
        self.market_cap_tiers = self.config.get("market_cap_tiers", {})

        # State persistence
        self.state_file = Path(state_file)
        self.persist_state = self.limiter_config.get("persist_state", True)

        # Load previous state if exists
        if self.persist_state:
            self.load_state()

        logger.info(
            f"Trade Limiter initialized with max {self.max_consecutive_stops} consecutive stops"
        )
        logger.info(f"Cooldowns: {self.cooldown_hours}")

    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file"""
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load config from {config_path}: {e}")
        return {}

    def get_symbol_tier(self, symbol: str) -> str:
        """
        Determine the market cap tier of a symbol

        Args:
            symbol: Trading symbol

        Returns:
            Tier name (large_cap, mid_cap, small_cap, or memecoin)
        """
        # Check each tier
        if symbol in self.market_cap_tiers.get("large_cap", []):
            return "large_cap"
        elif symbol in self.market_cap_tiers.get("mid_cap", []):
            return "mid_cap"
        elif symbol in self.market_cap_tiers.get("memecoin", []):
            return "memecoin"
        else:
            return "small_cap"  # Default for anything not explicitly listed

    def record_stop_loss(self, symbol: str):
        """
        Record that a stop loss occurred

        Args:
            symbol: Symbol that hit stop loss
        """
        now = datetime.now()
        self.stop_loss_history[symbol] = now

        # Increment consecutive stops
        self.consecutive_stops[symbol] = self.consecutive_stops.get(symbol, 0) + 1

        # Record outcome
        self.last_trade_outcomes[symbol] = "stop_loss"

        logger.warning(
            f"Stop loss recorded for {symbol}. Consecutive: {self.consecutive_stops[symbol]}"
        )

        # Check if this triggers a ban
        if self.consecutive_stops[symbol] >= self.max_consecutive_stops:
            logger.error(
                f"🚫 {symbol} BANNED - {self.consecutive_stops[symbol]} consecutive stop losses!"
            )

        # Save state if enabled
        if self.persist_state:
            self.save_state()

    def record_successful_trade(
        self,
        symbol: str,
        exit_reason: str,
        profit_pct: Optional[float] = None,
        take_profit_target: Optional[float] = None,
    ):
        """
        Record a successful trade that might reset consecutive stops

        Args:
            symbol: Trading symbol
            exit_reason: How the trade exited (take_profit, trailing_stop, time_exit)
            profit_pct: Profit percentage if available
            take_profit_target: Original take profit target for 50% calculation
        """
        should_reset = False
        reset_reason = ""

        # Check reset conditions based on exit reason
        if exit_reason == "take_profit":
            should_reset = True
            reset_reason = "full take profit reached"

        elif exit_reason == "trailing_stop" and self.reset_on_trailing_stop:
            should_reset = True
            reset_reason = "trailing stop (profitable exit)"

        elif exit_reason == "time_exit" and profit_pct and profit_pct > 0:
            # Profitable timeout exit
            should_reset = True
            reset_reason = f"profitable timeout ({profit_pct:.2f}%)"

        elif self.reset_on_50pct_tp and profit_pct and take_profit_target:
            # Check if we reached 50% of take profit target
            if profit_pct >= (take_profit_target * 0.5):
                should_reset = True
                reset_reason = f"50% of TP target reached ({profit_pct:.2f}%)"

        # Reset consecutive stops if conditions met
        if should_reset and symbol in self.consecutive_stops:
            old_count = self.consecutive_stops[symbol]
            self.consecutive_stops[symbol] = 0
            logger.info(
                f"✅ Reset consecutive stops for {symbol} (was {old_count}) - {reset_reason}"
            )

        # Record outcome
        self.last_trade_outcomes[symbol] = exit_reason

        # Save state if enabled
        if self.persist_state:
            self.save_state()

    def can_trade_symbol(self, symbol: str) -> Tuple[bool, str]:
        """
        Check if we can trade this symbol based on cooldowns and bans

        Args:
            symbol: Symbol to check

        Returns:
            Tuple of (can_trade, reason_if_not)
        """
        # Check if protection is enabled
        if not self.market_protection.get("enabled", False):
            return True, "Protection disabled"

        if not self.market_protection.get("trade_limiter", False):
            return True, "Trade limiter disabled"

        # Check if banned due to consecutive stops
        consecutive = self.consecutive_stops.get(symbol, 0)
        if consecutive >= self.max_consecutive_stops:
            last_stop = self.stop_loss_history.get(symbol)
            if last_stop:
                ban_until = last_stop + timedelta(hours=self.ban_duration_hours)
                if datetime.now() < ban_until:
                    time_left = (ban_until - datetime.now()).total_seconds() / 3600
                    return (
                        False,
                        f"BANNED for {time_left:.1f}h after {consecutive} stops",
                    )
                else:
                    # Ban expired, reset counter
                    self.consecutive_stops[symbol] = 0
                    logger.info(f"Ban expired for {symbol}, resetting counter")
                    if self.persist_state:
                        self.save_state()

        # Check cooldown after stop loss
        if symbol in self.stop_loss_history:
            last_stop = self.stop_loss_history[symbol]

            # Get tier-specific cooldown
            tier = self.get_symbol_tier(symbol)
            cooldown_hours = self.cooldown_hours.get(tier, 6)  # Default 6 hours

            cooldown_until = last_stop + timedelta(hours=cooldown_hours)

            if datetime.now() < cooldown_until:
                time_left = (cooldown_until - datetime.now()).total_seconds() / 3600
                return (
                    False,
                    f"Cooldown for {time_left:.1f}h after stop loss ({tier}: {cooldown_hours}h cooldown)",
                )

        return True, "OK"

    def get_limiter_stats(self) -> Dict:
        """Get current limiter statistics for monitoring"""
        stats = {
            "symbols_on_cooldown": [],
            "symbols_banned": [],
            "consecutive_stops": {},
            "total_stops_recorded": len(self.stop_loss_history),
        }

        # Check each symbol's status
        for symbol in set(
            list(self.stop_loss_history.keys()) + list(self.consecutive_stops.keys())
        ):
            can_trade, reason = self.can_trade_symbol(symbol)

            if not can_trade:
                if "BANNED" in reason:
                    stats["symbols_banned"].append(
                        {
                            "symbol": symbol,
                            "consecutive_stops": self.consecutive_stops.get(symbol, 0),
                            "reason": reason,
                        }
                    )
                elif "Cooldown" in reason:
                    stats["symbols_on_cooldown"].append(
                        {
                            "symbol": symbol,
                            "reason": reason,
                            "consecutive_stops": self.consecutive_stops.get(symbol, 0),
                        }
                    )

            # Add consecutive stops if any
            if symbol in self.consecutive_stops and self.consecutive_stops[symbol] > 0:
                stats["consecutive_stops"][symbol] = self.consecutive_stops[symbol]

        return stats

    def save_state(self):
        """Save limiter state to JSON file for persistence"""
        if not self.persist_state:
            return

        state = {
            "stop_loss_history": {
                k: v.isoformat() for k, v in self.stop_loss_history.items()
            },
            "consecutive_stops": self.consecutive_stops,
            "last_trade_outcomes": self.last_trade_outcomes,
            "last_updated": datetime.now().isoformat(),
        }

        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)
            logger.debug(f"Trade limiter state saved to {self.state_file}")
        except Exception as e:
            logger.error(f"Failed to save trade limiter state: {e}")

    def load_state(self):
        """Load limiter state from JSON file"""
        if not self.state_file.exists():
            logger.info("No previous trade limiter state found")
            return

        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)

            # Restore stop loss history with datetime conversion
            self.stop_loss_history = {
                k: datetime.fromisoformat(v)
                for k, v in state.get("stop_loss_history", {}).items()
            }

            # Restore consecutive stops
            self.consecutive_stops = state.get("consecutive_stops", {})

            # Restore last trade outcomes
            self.last_trade_outcomes = state.get("last_trade_outcomes", {})

            logger.info(
                f"Loaded trade limiter state: {len(self.stop_loss_history)} symbols tracked"
            )

            # Clean up old entries (> 48 hours)
            self._cleanup_old_entries()

        except Exception as e:
            logger.error(f"Failed to load trade limiter state: {e}")

    def _cleanup_old_entries(self):
        """Remove old entries that are no longer relevant"""
        cutoff = datetime.now() - timedelta(hours=48)

        # Clean up old stop losses
        old_symbols = [
            symbol
            for symbol, timestamp in self.stop_loss_history.items()
            if timestamp < cutoff and self.consecutive_stops.get(symbol, 0) == 0
        ]

        for symbol in old_symbols:
            del self.stop_loss_history[symbol]
            if symbol in self.last_trade_outcomes:
                del self.last_trade_outcomes[symbol]

        if old_symbols:
            logger.info(f"Cleaned up {len(old_symbols)} old entries from trade limiter")
            if self.persist_state:
                self.save_state()

    def reset(self):
        """Reset all limiter state (useful for testing)"""
        self.stop_loss_history.clear()
        self.consecutive_stops.clear()
        self.last_trade_outcomes.clear()
        logger.info("Trade limiter state reset")

        if self.persist_state:
            self.save_state()

    def clear_symbol_cooldown(self, symbol: str):
        """
        Manually clear cooldown for a specific symbol (override command)

        Args:
            symbol: Symbol to clear
        """
        if symbol in self.stop_loss_history:
            del self.stop_loss_history[symbol]
        if symbol in self.consecutive_stops:
            self.consecutive_stops[symbol] = 0
        if symbol in self.last_trade_outcomes:
            del self.last_trade_outcomes[symbol]

        logger.info(f"Manually cleared all cooldowns and counters for {symbol}")

        if self.persist_state:
            self.save_state()
