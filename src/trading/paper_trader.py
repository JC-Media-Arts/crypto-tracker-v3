"""
Paper trading module for simulated trading based on ML predictions.
Implements risk management and position tracking.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from decimal import Decimal
from loguru import logger

from src.config import Settings
from src.data.supabase_client import SupabaseClient
from src.ml.predictor import MLPredictor


class PaperTrader:
    """Handles paper trading based on ML predictions."""

    # Trading rules from master plan
    TRADING_RULES = {
        "entry_conditions": {
            "ml_confidence_minimum": 0.60,
            "max_open_positions": 5,
            "max_positions_per_coin": 1,
            "position_size": 100,  # $100 fixed
            "no_new_trades_if_daily_loss": -10.0,  # Stop at -10% day
        },
        "exit_conditions": {
            "stop_loss": -5.0,  # -5% fixed
            "take_profit": 10.0,  # +10% fixed
            "time_exit": 24,  # Exit after 24 hours
        },
        "risk_limits": {
            "max_daily_loss": -10.0,  # Percent
            "max_open_risk": 500,  # $500 total (5 x $100)
        },
    }

    def __init__(self, settings: Settings, ml_predictor: MLPredictor):
        """Initialize paper trader."""
        self.settings = settings
        self.ml_predictor = ml_predictor
        self.db_client: Optional[SupabaseClient] = None
        self.running = False

        # Trading state
        self.open_positions: Dict[str, Dict] = {}
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.consecutive_losses = 0
        self.trading_enabled = True

    async def initialize(self):
        """Initialize paper trader."""
        logger.info("Initializing paper trader...")

        try:
            # Initialize database client
            self.db_client = SupabaseClient(self.settings)
            await self.db_client.initialize()

            # Load open positions
            await self._load_open_positions()

            logger.success("Paper trader initialized")

        except Exception as e:
            logger.error(f"Failed to initialize paper trader: {e}")
            raise

    async def _load_open_positions(self):
        """Load open positions from database."""
        try:
            open_trades = await self.db_client.get_open_trades()

            for trade in open_trades:
                self.open_positions[trade["symbol"]] = trade

            logger.info(f"Loaded {len(self.open_positions)} open positions")

        except Exception as e:
            logger.error(f"Failed to load open positions: {e}")

    async def start(self):
        """Start paper trading."""
        logger.info("Starting paper trading...")
        self.running = True

        # Start trading loop
        asyncio.create_task(self._trading_loop())

        # Start position monitoring
        asyncio.create_task(self._monitor_positions())

        # Start daily reset
        asyncio.create_task(self._daily_reset())

        logger.success("Paper trading started")

    async def _trading_loop(self):
        """Main trading loop."""
        while self.running:
            try:
                if not self.trading_enabled:
                    logger.warning("Trading disabled due to risk limits")
                    await asyncio.sleep(60)
                    continue

                # Check if we can open new positions
                if not await self._can_open_position():
                    await asyncio.sleep(60)
                    continue

                # Get ML predictions
                predictions = await self._get_trading_signals()

                for prediction in predictions:
                    await self._process_signal(prediction)

                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                await asyncio.sleep(60)

    async def _can_open_position(self) -> bool:
        """Check if we can open new positions."""
        # Check max positions
        if (
            len(self.open_positions)
            >= self.TRADING_RULES["entry_conditions"]["max_open_positions"]
        ):
            return False

        # Check daily loss limit
        if (
            self.daily_pnl
            <= self.TRADING_RULES["entry_conditions"]["no_new_trades_if_daily_loss"]
        ):
            return False

        # Check consecutive losses
        if self.consecutive_losses >= 5:
            logger.warning("Too many consecutive losses")
            return False

        return True

    async def _get_trading_signals(self) -> List[Dict]:
        """Get trading signals from ML predictions."""
        signals = []

        # Get symbols to check
        from src.data.collector import DataCollector

        symbols = DataCollector.TIER_1_COINS[:10]  # Start with top 10

        for symbol in symbols:
            # Skip if already have position
            if symbol in self.open_positions:
                continue

            # Get prediction
            prediction = self.ml_predictor.get_last_prediction(symbol)

            if (
                prediction
                and prediction["confidence"]
                >= self.TRADING_RULES["entry_conditions"]["ml_confidence_minimum"]
            ):
                signals.append(prediction)

        return signals

    async def _process_signal(self, signal: Dict):
        """Process a trading signal."""
        try:
            symbol = signal["symbol"]

            # Get current price (mock for now)
            current_price = await self._get_current_price(symbol)
            if not current_price:
                return

            # Calculate position details
            position_size = self.TRADING_RULES["entry_conditions"]["position_size"]
            stop_loss_price = current_price * (
                1 - self.TRADING_RULES["exit_conditions"]["stop_loss"] / 100
            )
            take_profit_price = current_price * (
                1 + self.TRADING_RULES["exit_conditions"]["take_profit"] / 100
            )

            # Create trade record
            trade = {
                "symbol": symbol,
                "entry_time": datetime.utcnow().isoformat(),
                "entry_price": current_price,
                "position_size": position_size,
                "stop_loss": stop_loss_price,
                "take_profit": take_profit_price,
                "ml_confidence": signal["confidence"],
                "prediction": signal["direction"],
            }

            # Store in database
            result = await self.db_client.insert_paper_trade(trade)

            if result:
                trade["trade_id"] = result[0]["trade_id"]
                self.open_positions[symbol] = trade
                self.daily_trades += 1

                logger.info(
                    f"Opened position: {symbol} @ ${current_price:.2f} "
                    f"(SL: ${stop_loss_price:.2f}, TP: ${take_profit_price:.2f})"
                )

        except Exception as e:
            logger.error(f"Failed to process signal for {symbol}: {e}")

    async def _monitor_positions(self):
        """Monitor open positions for exit conditions."""
        while self.running:
            try:
                for symbol, position in list(self.open_positions.items()):
                    should_exit, reason = await self._check_exit_conditions(position)

                    if should_exit:
                        await self._close_position(symbol, reason)

                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception as e:
                logger.error(f"Error monitoring positions: {e}")
                await asyncio.sleep(30)

    async def _check_exit_conditions(self, position: Dict) -> tuple[bool, str]:
        """Check if position should be closed."""
        try:
            current_price = await self._get_current_price(position["symbol"])
            if not current_price:
                return False, ""

            entry_price = position["entry_price"]
            pnl_pct = (current_price - entry_price) / entry_price * 100

            # Check stop loss
            if pnl_pct <= -self.TRADING_RULES["exit_conditions"]["stop_loss"]:
                return True, "stop_loss"

            # Check take profit
            if pnl_pct >= self.TRADING_RULES["exit_conditions"]["take_profit"]:
                return True, "take_profit"

            # Check time exit
            entry_time = datetime.fromisoformat(
                position["entry_time"].replace("Z", "+00:00")
            )
            hours_open = (
                datetime.utcnow() - entry_time.replace(tzinfo=None)
            ).total_seconds() / 3600

            if hours_open >= self.TRADING_RULES["exit_conditions"]["time_exit"]:
                return True, "time_exit"

            return False, ""

        except Exception as e:
            logger.error(f"Error checking exit conditions: {e}")
            return False, ""

    async def _close_position(self, symbol: str, reason: str):
        """Close a position."""
        try:
            position = self.open_positions[symbol]
            current_price = await self._get_current_price(symbol)

            if not current_price:
                return

            # Calculate P&L
            entry_price = position["entry_price"]
            position_size = position["position_size"]
            pnl = (current_price - entry_price) / entry_price * position_size
            pnl_pct = (current_price - entry_price) / entry_price * 100

            # Update trade record
            await self.db_client.update_paper_trade(
                position["trade_id"],
                {
                    "exit_time": datetime.utcnow().isoformat(),
                    "exit_price": current_price,
                    "exit_reason": reason,
                    "pnl": pnl,
                },
            )

            # Update tracking
            self.daily_pnl += pnl

            if pnl < 0:
                self.consecutive_losses += 1
            else:
                self.consecutive_losses = 0

            # Remove from open positions
            del self.open_positions[symbol]

            logger.info(
                f"Closed position: {symbol} @ ${current_price:.2f} "
                f"(P&L: ${pnl:.2f} / {pnl_pct:+.2f}%) - Reason: {reason}"
            )

        except Exception as e:
            logger.error(f"Failed to close position for {symbol}: {e}")

    async def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol."""
        try:
            # Get from database (most recent price)
            prices = await self.db_client.get_recent_prices(symbol, hours=1)

            if prices:
                return float(prices[0]["price"])

            return None

        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
            return None

    async def _daily_reset(self):
        """Reset daily metrics at midnight."""
        while self.running:
            try:
                # Calculate time until midnight
                now = datetime.utcnow()
                midnight = (now + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                seconds_until_midnight = (midnight - now).total_seconds()

                await asyncio.sleep(seconds_until_midnight)

                # Store daily performance
                await self.db_client.upsert_daily_performance(
                    {
                        "date": now.date().isoformat(),
                        "trades_count": self.daily_trades,
                        "net_pnl": self.daily_pnl,
                        "ml_accuracy": self.ml_predictor.model_accuracy,
                    }
                )

                # Reset daily metrics
                self.daily_pnl = 0.0
                self.daily_trades = 0
                self.trading_enabled = True

                logger.info("Daily metrics reset")

            except Exception as e:
                logger.error(f"Error in daily reset: {e}")
                await asyncio.sleep(3600)

    async def stop(self):
        """Stop paper trading."""
        logger.info("Stopping paper trading...")
        self.running = False

        # Close all positions
        for symbol in list(self.open_positions.keys()):
            await self._close_position(symbol, "system_shutdown")

        logger.info("Paper trading stopped")

    def get_status(self) -> Dict:
        """Get trading status."""
        return {
            "trading_enabled": self.trading_enabled,
            "open_positions": len(self.open_positions),
            "daily_pnl": self.daily_pnl,
            "daily_trades": self.daily_trades,
            "consecutive_losses": self.consecutive_losses,
        }
