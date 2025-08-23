"""
Channel Trading Strategy Executor
Executes trades based on detected channels
"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from loguru import logger
from dataclasses import dataclass

from .detector import Channel, ChannelDetector


@dataclass
class ChannelPosition:
    """Represents an active channel trade"""

    symbol: str
    channel: Channel
    entry_price: float
    entry_time: datetime
    position_size: float
    side: str  # 'LONG' or 'SHORT'
    take_profit: float
    stop_loss: float
    status: str  # 'OPEN', 'CLOSED', 'CANCELLED'
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: Optional[float] = None
    exit_reason: Optional[str] = None


class ChannelExecutor:
    """
    Executes channel trading strategy
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.detector = ChannelDetector(config)

        # Trading parameters
        self.position_size = self.config.get("position_size", 100)  # Base position size
        self.max_positions = self.config.get("max_positions", 3)  # Max concurrent channel trades
        self.min_risk_reward = self.config.get("min_risk_reward", 1.5)  # Minimum R:R ratio
        self.channel_break_exit = self.config.get("channel_break_exit", True)  # Exit on channel break
        self.time_exit_hours = self.config.get("time_exit_hours", 48)  # Max hold time

        # Active positions
        self.positions: Dict[str, ChannelPosition] = {}

        logger.info("Channel Executor initialized")

    async def scan_and_execute(self, market_data: Dict[str, List[Dict]]) -> List[Dict]:
        """
        Scan market for channel opportunities and execute trades

        Args:
            market_data: Dictionary of symbol -> OHLC data

        Returns:
            List of trading signals generated
        """
        signals = []

        for symbol, ohlc_data in market_data.items():
            # Skip if already have position
            if symbol in self.positions:
                continue

            # Skip if max positions reached
            if len(self.positions) >= self.max_positions:
                break

            # Detect channel
            channel = self.detector.detect_channel(symbol, ohlc_data)

            if not channel:
                continue

            # Get trading signal
            signal = self.detector.get_trading_signal(channel)

            if signal:
                # Calculate targets
                current_price = ohlc_data[0]["close"]  # Most recent price
                targets = self.detector.calculate_targets(channel, current_price, signal)

                # Check risk/reward
                if targets.get("risk_reward", 0) < self.min_risk_reward:
                    logger.debug(
                        f"Skipping {symbol}: R:R {targets['risk_reward']:.2f} " f"< minimum {self.min_risk_reward}"
                    )
                    continue

                # Create position
                position = await self._create_position(symbol, channel, signal, current_price, targets)

                if position:
                    self.positions[symbol] = position
                    signals.append(
                        {
                            "symbol": symbol,
                            "strategy": "CHANNEL",
                            "signal": signal,
                            "channel_type": channel.channel_type,
                            "channel_width": channel.width,
                            "channel_strength": channel.strength,
                            "position_in_channel": channel.current_position,
                            "entry_price": current_price,
                            "take_profit": targets["take_profit"],
                            "stop_loss": targets["stop_loss"],
                            "risk_reward": targets["risk_reward"],
                        }
                    )

                    logger.info(
                        f"Channel trade opened: {symbol} {signal} at ${current_price:.2f}, "
                        f"TP=${targets['take_profit']:.2f} ({targets['take_profit_pct']:.1f}%), "
                        f"SL=${targets['stop_loss']:.2f} ({targets['stop_loss_pct']:.1f}%), "
                        f"R:R={targets['risk_reward']:.2f}"
                    )

        return signals

    async def _create_position(
        self,
        symbol: str,
        channel: Channel,
        signal: str,
        entry_price: float,
        targets: Dict,
    ) -> Optional[ChannelPosition]:
        """
        Create a new channel position
        """
        try:
            position = ChannelPosition(
                symbol=symbol,
                channel=channel,
                entry_price=entry_price,
                entry_time=datetime.now(),
                position_size=self.position_size,
                side="LONG" if signal == "BUY" else "SHORT",
                take_profit=targets["take_profit"],
                stop_loss=targets["stop_loss"],
                status="OPEN",
            )

            return position

        except Exception as e:
            logger.error(f"Error creating position for {symbol}: {e}")
            return None

    async def monitor_positions(self, market_data: Dict[str, List[Dict]]) -> List[Dict]:
        """
        Monitor open positions and handle exits

        Returns:
            List of closed positions
        """
        closed_positions = []

        for symbol, position in list(self.positions.items()):
            if position.status != "OPEN":
                continue

            # Get current data
            ohlc_data = market_data.get(symbol)
            if not ohlc_data:
                continue

            current_price = ohlc_data[0]["close"]

            # Check exit conditions
            exit_reason = self._check_exit_conditions(position, current_price, ohlc_data)

            if exit_reason:
                # Close position
                await self._close_position(position, current_price, exit_reason)
                closed_positions.append(
                    {
                        "symbol": symbol,
                        "entry_price": position.entry_price,
                        "exit_price": current_price,
                        "pnl": position.pnl,
                        "exit_reason": exit_reason,
                        "hold_time": (datetime.now() - position.entry_time).total_seconds() / 3600,
                    }
                )

                # Remove from active positions
                del self.positions[symbol]

                logger.info(
                    f"Channel position closed: {symbol} at ${current_price:.2f}, "
                    f"P&L: ${position.pnl:.2f}, Reason: {exit_reason}"
                )

        return closed_positions

    def _check_exit_conditions(
        self, position: ChannelPosition, current_price: float, ohlc_data: List[Dict]
    ) -> Optional[str]:
        """
        Check if position should be exited
        """
        # Check take profit
        if position.side == "LONG":
            if current_price >= position.take_profit:
                return "TAKE_PROFIT"
            if current_price <= position.stop_loss:
                return "STOP_LOSS"
        else:  # SHORT
            if current_price <= position.take_profit:
                return "TAKE_PROFIT"
            if current_price >= position.stop_loss:
                return "STOP_LOSS"

        # Check time exit
        hold_time = datetime.now() - position.entry_time
        if hold_time > timedelta(hours=self.time_exit_hours):
            return "TIME_EXIT"

        # Check channel break
        if self.channel_break_exit:
            # Re-detect channel
            new_channel = self.detector.detect_channel(position.symbol, ohlc_data)

            # Exit if channel no longer valid
            if not new_channel or not new_channel.is_valid:
                return "CHANNEL_BREAK"

            # Exit if channel has changed significantly
            if abs(new_channel.upper_line - position.channel.upper_line) / position.channel.upper_line > 0.02:
                return "CHANNEL_CHANGE"

        return None

    async def _close_position(self, position: ChannelPosition, exit_price: float, exit_reason: str):
        """
        Close a position and calculate P&L
        """
        position.exit_price = exit_price
        position.exit_time = datetime.now()
        position.exit_reason = exit_reason
        position.status = "CLOSED"

        # Calculate P&L
        if position.side == "LONG":
            position.pnl = (exit_price - position.entry_price) * position.position_size / position.entry_price
        else:  # SHORT
            position.pnl = (position.entry_price - exit_price) * position.position_size / position.entry_price

    def get_active_positions(self) -> List[Dict]:
        """
        Get summary of active positions
        """
        positions = []

        for symbol, position in self.positions.items():
            if position.status == "OPEN":
                current_pnl = 0  # Would calculate based on current price

                positions.append(
                    {
                        "symbol": symbol,
                        "side": position.side,
                        "entry_price": position.entry_price,
                        "position_size": position.position_size,
                        "channel_type": position.channel.channel_type,
                        "take_profit": position.take_profit,
                        "stop_loss": position.stop_loss,
                        "hold_time": (datetime.now() - position.entry_time).total_seconds() / 3600,
                        "current_pnl": current_pnl,
                    }
                )

        return positions

    def get_performance_stats(self) -> Dict:
        """
        Calculate performance statistics
        """
        closed_positions = [p for p in self.positions.values() if p.status == "CLOSED"]

        if not closed_positions:
            return {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0,
                "total_pnl": 0,
                "avg_win": 0,
                "avg_loss": 0,
            }

        wins = [p for p in closed_positions if p.pnl > 0]
        losses = [p for p in closed_positions if p.pnl <= 0]

        total_pnl = sum(p.pnl for p in closed_positions)
        avg_win = sum(p.pnl for p in wins) / len(wins) if wins else 0
        avg_loss = sum(p.pnl for p in losses) / len(losses) if losses else 0

        return {
            "total_trades": len(closed_positions),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(closed_positions) if closed_positions else 0,
            "total_pnl": total_pnl,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": abs(avg_win / avg_loss) if avg_loss != 0 else 0,
        }
