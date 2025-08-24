"""
Enhanced Paper Trading System with Adaptive Exit Rules and Database Persistence
"""

import json
import os
import random
import string
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from loguru import logger
from pathlib import Path
from src.data.supabase_client import SupabaseClient
from src.notifications.paper_trading_notifier import PaperTradingNotifier


@dataclass
class Position:
    """Represents an open position"""

    symbol: str
    entry_price: float
    amount: float  # In crypto units
    usd_value: float
    entry_time: datetime
    strategy: str
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trailing_stop_pct: Optional[float] = None
    highest_price: Optional[float] = None  # For trailing stop
    fees_paid: float = 0.0
    trade_group_id: Optional[str] = None  # Links related trades together


@dataclass
class Trade:
    """Represents a completed trade"""

    symbol: str
    entry_price: float
    exit_price: float
    amount: float
    entry_time: datetime
    exit_time: datetime
    pnl_usd: float
    pnl_percent: float
    fees_paid: float
    strategy: str
    trade_type: str  # 'win' or 'loss'
    exit_reason: str  # 'stop_loss', 'take_profit', 'trailing_stop', 'time_exit'
    trade_group_id: Optional[str] = None  # Links related trades together


class SimplePaperTraderV2:
    """
    Enhanced paper trading system with adaptive exit rules and DB persistence

    Kraken Fees (Maker/Taker):
    - < $50k volume: 0.16% / 0.26%
    - We'll use taker fees (0.26%) as we're doing market orders

    Slippage by Market Cap:
    - Large-cap (BTC, ETH): 0.05-0.1%
    - Mid-cap: 0.1-0.2%
    - Small-cap/Meme: 0.2-0.5%

    Adaptive Exit Rules by Market Cap:
    - Large-cap: TP 3-5%, SL 5-7%, Trail 2%
    - Mid-cap: TP 5-10%, SL 7-10%, Trail 3.5%
    - Small-cap: TP 7-15%, SL 10-12%, Trail 6%
    """

    def __init__(
        self,
        initial_balance: float = 10000.0,
        max_positions: int = 50,
        max_positions_per_strategy: int = 50,
        config_path: str = "configs/paper_trading.json",
    ):
        # Load configuration
        self.config = self._load_config(config_path)
        
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.pending_orders: Dict[str, dict] = {}
        self.max_positions = max_positions  # Total max positions
        self.max_positions_per_strategy = max_positions_per_strategy  # Max per strategy

        # Load fee from config
        self.base_fee_rate = self.config.get("fees", {}).get("kraken_taker", 0.0026)

        # Initialize Slack notifier
        self.notifier = None
        try:
            self.notifier = PaperTradingNotifier()
        except Exception as e:
            logger.warning(f"Could not initialize Slack notifier: {e}")

        # Load market cap tiers from config
        market_cap_config = self.config.get("market_cap_tiers", {})
        self.large_cap = market_cap_config.get("large_cap", ["BTC", "ETH"])
        self.mid_cap = market_cap_config.get(
            "mid_cap",
            [
                "SOL", "BNB", "XRP", "ADA", "AVAX", "DOT",
                "LINK", "ATOM", "UNI", "NEAR", "ICP", "ARB",
                "OP", "AAVE", "CRV", "MKR", "LDO", "SUSHI", "COMP",
            ],
        )

        # Load slippage rates from config
        self.slippage_rates = self.config.get(
            "slippage_rates",
            {"large": 0.0008, "mid": 0.0015, "small": 0.0035},
        )

        # Stats tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.total_fees = 0.0
        self.total_slippage = 0.0

        # Database client for persistence
        self.db_client = None
        try:
            self.db_client = SupabaseClient()
        except Exception as e:
            logger.warning(f"Could not initialize Supabase client: {e}")
            logger.info("Will use local file persistence only")

        # Persistence files
        self.state_file = Path("data/paper_trading_state.json")
        self.trades_file = Path("data/paper_trading_trades.json")
        self.load_state()

    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file"""
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load config from {config_path}: {e}")
        
        # Return default config if file doesn't exist or can't be loaded
        return {
            "strategies": {},
            "fees": {"kraken_taker": 0.0026},
            "slippage_rates": {"large": 0.0008, "mid": 0.0015, "small": 0.0035},
            "market_cap_tiers": {},
        }

    def get_market_cap_tier(self, symbol: str) -> str:
        """Get market cap tier for adaptive rules"""
        if symbol in self.large_cap:
            return "large_cap"
        elif symbol in self.mid_cap:
            return "mid_cap"
        else:
            return "small_cap"

    def get_adaptive_exits(self, symbol: str, strategy: str) -> Dict:
        """
        Get adaptive exit parameters based on market cap and strategy

        Returns dict with take_profit, stop_loss, and trailing_stop percentages
        """
        tier = self.get_market_cap_tier(symbol)
        strategy_lower = strategy.lower()
        strategy_upper = strategy.upper()

        # Try to get exits from config first
        strategy_config = self.config.get("strategies", {}).get(strategy_upper, {})
        if "exits_by_tier" in strategy_config:
            exits_config = strategy_config["exits_by_tier"].get(tier, {})
            if exits_config:
                logger.debug(f"Using config exits for {symbol}/{strategy}: {exits_config}")
                return exits_config

        # Fallback to hardcoded defaults if not in config
        logger.debug(f"Using hardcoded exits for {symbol}/{strategy} (config not found)")
        
        # Comprehensive exit rules by tier and strategy
        exits = {
            "large_cap": {
                "dca": {
                    "take_profit": 0.04,
                    "stop_loss": 0.06,
                    "trailing_stop": 0.02,
                },  # 4%  # 6%  # 2%
                "swing": {
                    "take_profit": 0.05,
                    "stop_loss": 0.05,
                    "trailing_stop": 0.02,
                },  # 5%  # 5%  # 2%
                "channel": {
                    "take_profit": 0.015,  # 1.5% - Conservative
                    "stop_loss": 0.02,  # 2% - Tighter stop
                    "trailing_stop": 0.005,  # 0.5% - Quick protection
                },  # Updated based on backtest analysis
            },
            "mid_cap": {
                "dca": {
                    "take_profit": 0.07,
                    "stop_loss": 0.08,
                    "trailing_stop": 0.035,
                },  # 7%  # 8%  # 3.5%
                "swing": {
                    "take_profit": 0.10,
                    "stop_loss": 0.07,
                    "trailing_stop": 0.04,
                },  # 10%  # 7%  # 4%
                "channel": {
                    "take_profit": 0.02,  # 2% - Conservative for mid-cap
                    "stop_loss": 0.025,  # 2.5% - Slightly looser than large-cap
                    "trailing_stop": 0.007,  # 0.7% - Quick protection
                },  # Updated based on backtest analysis
            },
            "small_cap": {
                "dca": {
                    "take_profit": 0.10,
                    "stop_loss": 0.11,
                    "trailing_stop": 0.06,
                },  # 10%  # 11%  # 6%
                "swing": {
                    "take_profit": 0.15,
                    "stop_loss": 0.10,
                    "trailing_stop": 0.07,
                },  # 15%  # 10%  # 7%
                "channel": {
                    "take_profit": 0.025,  # 2.5% - Conservative for small-cap
                    "stop_loss": 0.03,  # 3% - More room for volatility
                    "trailing_stop": 0.01,  # 1% - Still tight protection
                },  # Updated based on backtest analysis
            },
        }

        # Default to DCA if strategy not recognized
        if strategy_lower not in exits[tier]:
            strategy_lower = "dca"

        return exits[tier][strategy_lower]

    def get_slippage_rate(self, symbol: str) -> float:
        """Get slippage rate based on market cap"""
        tier = self.get_market_cap_tier(symbol)

        if tier == "large_cap":
            return self.slippage_rates["large"]
        elif tier == "mid_cap":
            return self.slippage_rates["mid"]
        else:
            return self.slippage_rates["small"]

    def calculate_entry_price(
        self, symbol: str, market_price: float, is_buy: bool = True
    ) -> tuple[float, float]:
        """
        Calculate actual entry price with slippage
        Returns: (actual_price, slippage_cost)
        """
        slippage_rate = self.get_slippage_rate(symbol)

        if is_buy:
            # Buying pushes price up
            actual_price = market_price * (1 + slippage_rate)
        else:
            # Selling pushes price down
            actual_price = market_price * (1 - slippage_rate)

        slippage_cost = abs(actual_price - market_price) * market_price
        return actual_price, slippage_cost

    def calculate_fees(self, usd_value: float) -> float:
        """Calculate Kraken taker fees"""
        return usd_value * self.base_fee_rate

    def generate_trade_group_id(self, strategy: str, symbol: str) -> str:
        """Generate a unique trade group ID for linking related trades"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = "".join(
            random.choices(string.ascii_lowercase + string.digits, k=6)
        )
        return f"{strategy}_{symbol}_{timestamp}_{random_suffix}"

    async def open_position(
        self,
        symbol: str,
        usd_amount: float,
        market_price: float,
        strategy: str,
        stop_loss_pct: Optional[float] = None,
        take_profit_pct: Optional[float] = None,
        use_adaptive: bool = True,
    ) -> Dict:
        """
        Open a new position with adaptive exit rules

        Args:
            symbol: Trading symbol
            usd_amount: Position size in USD
            market_price: Current market price
            strategy: Trading strategy (dca, swing, channel)
            stop_loss_pct: Override stop loss (if None, uses adaptive)
            take_profit_pct: Override take profit (if None, uses adaptive)
            use_adaptive: Whether to use adaptive exits (default True)
        """
        # Check if we already have a position
        if symbol in self.positions:
            logger.warning(f"Position already exists for {symbol}")
            return {"success": False, "error": "Position already exists"}

        # Check max positions limit
        if len(self.positions) >= self.max_positions:
            logger.warning(f"Max positions limit reached ({self.max_positions})")
            return {
                "success": False,
                "error": f"Max {self.max_positions} positions reached",
            }

        # Check strategy-specific position limit
        strategy_positions = sum(
            1 for p in self.positions.values() if p.strategy == strategy
        )
        if strategy_positions >= self.max_positions_per_strategy:
            logger.warning(
                f"Max {strategy} positions limit reached ({self.max_positions_per_strategy})"
            )
            return {
                "success": False,
                "error": f"Max {self.max_positions_per_strategy} {strategy} positions reached",
            }

        # Check balance
        if usd_amount > self.balance * 0.5:  # Max 50% of balance per trade
            logger.warning(
                f"Position size ${usd_amount} too large for balance ${self.balance}"
            )
            return {"success": False, "error": "Insufficient balance"}

        # Get adaptive exit parameters if not overridden
        if use_adaptive:
            exits = self.get_adaptive_exits(symbol, strategy)
            if stop_loss_pct is None:
                stop_loss_pct = exits["stop_loss"]
            if take_profit_pct is None:
                take_profit_pct = exits["take_profit"]
            trailing_stop_pct = exits["trailing_stop"]
        else:
            # Use defaults if not adaptive and not specified
            if stop_loss_pct is None:
                stop_loss_pct = 0.05  # 5% default
            if take_profit_pct is None:
                take_profit_pct = 0.10  # 10% default
            trailing_stop_pct = 0.05  # 5% default trailing

        # Calculate actual entry price with slippage
        actual_price, slippage_cost = self.calculate_entry_price(
            symbol, market_price, is_buy=True
        )

        # Calculate fees
        fees = self.calculate_fees(usd_amount)

        # Total cost including fees
        total_cost = usd_amount + fees

        if total_cost > self.balance:
            logger.warning(
                f"Insufficient balance for {symbol}. Need ${total_cost:.2f}, have ${self.balance:.2f}"
            )
            return {"success": False, "error": "Insufficient balance"}

        # Calculate position amount in crypto units
        crypto_amount = usd_amount / actual_price

        # Generate trade group ID for this position
        trade_group_id = self.generate_trade_group_id(strategy, symbol)

        # Create position
        position = Position(
            symbol=symbol,
            entry_price=actual_price,
            amount=crypto_amount,
            usd_value=usd_amount,
            entry_time=datetime.now(),
            strategy=strategy,
            stop_loss=actual_price * (1 - stop_loss_pct),
            take_profit=actual_price * (1 + take_profit_pct),
            trailing_stop_pct=trailing_stop_pct,
            highest_price=actual_price,  # Initialize for trailing stop
            fees_paid=fees,
            trade_group_id=trade_group_id,  # Link all related trades
        )

        # Update state
        self.positions[symbol] = position
        self.balance -= total_cost
        self.total_fees += fees
        self.total_slippage += slippage_cost

        # Save to database if available
        await self.save_position_to_db(position, actual_price, market_price)

        # Save state locally
        self.save_state()

        logger.info(f"📈 Opened {strategy.upper()} position: {symbol}")
        logger.info(f"   Entry: ${actual_price:.4f} (market: ${market_price:.4f})")
        logger.info(f"   Amount: {crypto_amount:.6f} {symbol}")
        logger.info(f"   Value: ${usd_amount:.2f}")
        logger.info(
            f"   Stop Loss: ${position.stop_loss:.4f} (-{stop_loss_pct*100:.1f}%)"
        )
        logger.info(
            f"   Take Profit: ${position.take_profit:.4f} (+{take_profit_pct*100:.1f}%)"
        )
        logger.info(f"   Trailing Stop: {trailing_stop_pct*100:.1f}%")
        logger.info(f"   Fees: ${fees:.2f}, Slippage: ${slippage_cost:.2f}")

        # Send Slack notification
        if self.notifier:
            try:
                await self.notifier.notify_position_opened(
                    symbol=symbol,
                    strategy=strategy,
                    entry_price=actual_price,
                    position_size=usd_amount,
                    stop_loss=position.stop_loss,
                    take_profit=position.take_profit,
                    trailing_stop_pct=trailing_stop_pct,
                    market_cap_tier=self.get_market_cap_tier(symbol),
                )
            except Exception as e:
                logger.error(f"Failed to send Slack notification: {e}")

        return {
            "success": True,
            "position": asdict(position),
            "fees": fees,
            "slippage": slippage_cost,
        }

    async def check_and_close_positions(
        self,
        current_prices: Dict[str, float],
        max_hold_hours: float = 72,  # 3 days default
    ) -> List[Trade]:
        """
        Check all positions for exit conditions including trailing stops

        Exit conditions checked in order:
        1. Stop loss
        2. Trailing stop
        3. Take profit
        4. Time exit (3 days default)
        """
        closed_trades = []

        for symbol, position in list(self.positions.items()):
            if symbol not in current_prices:
                continue

            current_price = current_prices[symbol]
            hold_duration = (
                datetime.now() - position.entry_time
            ).total_seconds() / 3600

            # Update highest price for trailing stop
            if current_price > position.highest_price:
                position.highest_price = current_price
                logger.debug(f"{symbol} new high: ${current_price:.4f}")

            # Calculate trailing stop price
            trailing_stop_price = position.highest_price * (
                1 - position.trailing_stop_pct
            )

            # Check exit conditions
            exit_reason = None

            # First check for stop loss
            if current_price <= position.stop_loss:
                exit_reason = "stop_loss"
            # Only use trailing stop if position went profitable first
            elif (
                current_price <= trailing_stop_price
                and position.highest_price
                > position.entry_price * 1.001  # Was profitable (0.1% buffer for fees)
            ):
                exit_reason = "trailing_stop"
            elif current_price >= position.take_profit:
                exit_reason = "take_profit"
            elif hold_duration >= max_hold_hours:
                exit_reason = "time_exit"

            if exit_reason:
                trade = await self.close_position(symbol, current_price, exit_reason)
                if trade:
                    closed_trades.append(trade)

        return closed_trades

    async def close_position(
        self, symbol: str, current_price: float, exit_reason: str = "manual"
    ) -> Optional[Trade]:
        """Close a position and record the trade"""
        if symbol not in self.positions:
            logger.warning(f"No position found for {symbol}")
            return None

        position = self.positions[symbol]

        # Calculate exit with slippage
        exit_price, slippage_cost = self.calculate_entry_price(
            symbol, current_price, is_buy=False
        )

        # Calculate exit value and fees
        exit_value = position.amount * exit_price
        exit_fees = self.calculate_fees(exit_value)

        # Calculate P&L
        entry_value = position.usd_value
        pnl_gross = exit_value - entry_value
        total_fees = position.fees_paid + exit_fees
        pnl_net = pnl_gross - total_fees
        pnl_percent = (pnl_net / entry_value) * 100

        # Create trade record
        trade = Trade(
            symbol=symbol,
            entry_price=position.entry_price,
            exit_price=exit_price,
            amount=position.amount,
            entry_time=position.entry_time,
            exit_time=datetime.now(),
            pnl_usd=pnl_net,
            pnl_percent=pnl_percent,
            fees_paid=total_fees,
            strategy=position.strategy,
            trade_type="win" if pnl_net > 0 else "loss",
            exit_reason=exit_reason,
            trade_group_id=position.trade_group_id,  # Link to same trade group
        )

        # Update stats
        self.total_trades += 1
        if pnl_net > 0:
            self.winning_trades += 1
        self.balance += exit_value - exit_fees
        self.total_fees += exit_fees
        self.total_slippage += slippage_cost

        # Remove position
        del self.positions[symbol]
        self.trades.append(trade)

        # Save to database if available
        await self.save_trade_to_db(trade)

        # Save state
        self.save_state()
        self.save_trades()

        # Log the exit
        emoji = "✅" if pnl_net > 0 else "❌"
        logger.info(f"{emoji} Closed {position.strategy.upper()} position: {symbol}")
        logger.info(f"   Exit: ${exit_price:.4f} (market: ${current_price:.4f})")
        logger.info(f"   P&L: ${pnl_net:.2f} ({pnl_percent:+.2f}%)")
        logger.info(f"   Reason: {exit_reason}")
        logger.info(
            f"   Duration: {(trade.exit_time - trade.entry_time).total_seconds()/3600:.1f} hours"
        )

        # Send Slack notification
        if self.notifier:
            try:
                await self.notifier.notify_position_closed(
                    symbol=symbol,
                    strategy=position.strategy,
                    entry_price=position.entry_price,
                    exit_price=exit_price,
                    pnl_usd=pnl_net,
                    pnl_percent=pnl_percent,
                    exit_reason=exit_reason,
                    duration_hours=(trade.exit_time - trade.entry_time).total_seconds()
                    / 3600,
                    highest_price=position.highest_price
                    if hasattr(position, "highest_price")
                    else None,
                )
            except Exception as e:
                logger.error(f"Failed to send Slack notification: {e}")

        return trade

    async def save_position_to_db(
        self, position: Position, actual_price: float, market_price: float
    ):
        """Save position opening to database"""
        if not self.db_client:
            return

        try:
            # Core data that should always exist
            data = {
                "trading_engine": "simple_paper_trader",
                "symbol": position.symbol,
                "side": "BUY",
                "order_type": "MARKET",
                "price": actual_price,
                "amount": position.amount,
                "status": "FILLED",
                "created_at": position.entry_time.isoformat(),
                "filled_at": position.entry_time.isoformat(),
                "strategy_name": position.strategy,
                "fees": position.fees_paid,
                "slippage": actual_price - market_price,
                # Now including stop loss, take profit, and trailing stop
                "stop_loss": position.stop_loss,
                "take_profit": position.take_profit,
                "trailing_stop_pct": position.trailing_stop_pct,
                "trade_group_id": position.trade_group_id,  # Link to trade group
            }

            self.db_client.client.table("paper_trades").insert(data).execute()
            logger.debug(f"Saved position to DB: {position.symbol}")
        except Exception as e:
            logger.error(f"Failed to save position to DB: {e}")

    async def save_trade_to_db(self, trade: Trade):
        """Save completed trade to database"""
        if not self.db_client:
            return

        try:
            # Update the original trade record with exit info
            data = {
                "trading_engine": "simple_paper_trader",
                "symbol": trade.symbol,
                "side": "SELL",
                "order_type": "MARKET",
                "price": trade.exit_price,
                "amount": trade.amount,
                "status": "CLOSED",
                "created_at": trade.entry_time.isoformat(),
                "filled_at": trade.exit_time.isoformat(),
                "strategy_name": trade.strategy,
                "fees": trade.fees_paid,
                "pnl": trade.pnl_usd,
                "exit_reason": trade.exit_reason,
                "trade_group_id": trade.trade_group_id,  # Link to same trade group
            }

            self.db_client.client.table("paper_trades").insert(data).execute()

            # Also update daily performance
            await self.update_daily_performance(trade)

            logger.debug(f"Saved trade to DB: {trade.symbol}")
        except Exception as e:
            logger.error(f"Failed to save trade to DB: {e}")

    async def update_daily_performance(self, trade: Trade):
        """Update daily performance metrics"""
        if not self.db_client:
            return

        try:
            date = trade.exit_time.date().isoformat()

            # Try to get existing record for today
            existing = (
                self.db_client.client.table("paper_performance")
                .select("*")
                .eq("date", date)
                .eq("strategy_name", trade.strategy)
                .eq("trading_engine", "simple_paper_trader")
                .execute()
            )

            if existing.data:
                # Update existing record
                record = existing.data[0]
                updated = {
                    "trades_count": record["trades_count"] + 1,
                    "wins": record["wins"] + (1 if trade.trade_type == "win" else 0),
                    "losses": record["losses"]
                    + (1 if trade.trade_type == "loss" else 0),
                    "net_pnl": record["net_pnl"] + trade.pnl_usd,
                }

                self.db_client.client.table("paper_performance").update(updated).eq(
                    "date", date
                ).eq("strategy_name", trade.strategy).eq(
                    "trading_engine", "simple_paper_trader"
                ).execute()
            else:
                # Create new record
                data = {
                    "date": date,
                    "strategy_name": trade.strategy,
                    "trading_engine": "simple_paper_trader",
                    "trades_count": 1,
                    "wins": 1 if trade.trade_type == "win" else 0,
                    "losses": 1 if trade.trade_type == "loss" else 0,
                    "net_pnl": trade.pnl_usd,
                    "setups_detected": 0,  # Will be updated by strategy scanner
                    "setups_taken": 0,  # Will be updated by strategy scanner
                    "ml_accuracy": 0.0,  # Not using ML in simplified mode
                }

                self.db_client.client.table("paper_performance").insert(data).execute()

        except Exception as e:
            logger.error(f"Failed to update daily performance: {e}")

    def get_trades_today(self) -> List[Dict]:
        """Get trades closed today"""
        today = datetime.now().date()
        trades_today = []

        for trade in self.trades:
            if trade.exit_time.date() == today:
                trades_today.append(
                    {
                        "symbol": trade.symbol,
                        "pnl_usd": trade.pnl_usd,
                        "pnl_percent": trade.pnl_percent,
                        "strategy": trade.strategy,
                        "exit_reason": trade.exit_reason,
                    }
                )

        return trades_today

    def get_open_positions_summary(self) -> List[Dict]:
        """Get summary of open positions"""
        positions_summary = []

        for symbol, position in self.positions.items():
            positions_summary.append(
                {
                    "symbol": symbol,
                    "entry_price": position.entry_price,
                    "usd_value": position.usd_value,
                    "strategy": position.strategy,
                    "entry_time": position.entry_time,
                }
            )

        return positions_summary

    def get_portfolio_stats(self) -> Dict:
        """Get current portfolio statistics"""
        # Calculate current portfolio value
        positions_value = sum(p.usd_value for p in self.positions.values())
        total_value = self.balance + positions_value

        # Calculate overall P&L
        total_pnl = total_value - self.initial_balance
        total_pnl_pct = (total_pnl / self.initial_balance) * 100

        # Win rate
        win_rate = (
            (self.winning_trades / self.total_trades * 100)
            if self.total_trades > 0
            else 0
        )

        return {
            "balance": self.balance,
            "positions": len(self.positions),
            "positions_value": positions_value,
            "total_value": total_value,
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl_pct,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "win_rate": win_rate,
            "total_fees": self.total_fees,
            "total_slippage": self.total_slippage,
            "max_positions": self.max_positions,
        }

    def save_state(self):
        """Save current state to file"""
        state = {
            "balance": self.balance,
            "initial_balance": self.initial_balance,
            "positions": {
                symbol: {
                    "entry_price": p.entry_price,
                    "amount": p.amount,
                    "usd_value": p.usd_value,
                    "entry_time": p.entry_time.isoformat(),
                    "strategy": p.strategy,
                    "stop_loss": p.stop_loss,
                    "take_profit": p.take_profit,
                    "trailing_stop_pct": p.trailing_stop_pct,
                    "highest_price": p.highest_price,
                    "fees_paid": p.fees_paid,
                }
                for symbol, p in self.positions.items()
            },
            "stats": {
                "total_trades": self.total_trades,
                "winning_trades": self.winning_trades,
                "total_fees": self.total_fees,
                "total_slippage": self.total_slippage,
            },
        }

        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2)

    def load_state(self):
        """Load state from file"""
        if not self.state_file.exists():
            return

        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)

            self.balance = state.get("balance", self.initial_balance)
            self.initial_balance = state.get("initial_balance", self.initial_balance)

            # Restore positions
            for symbol, pos_data in state.get("positions", {}).items():
                self.positions[symbol] = Position(
                    symbol=symbol,
                    entry_price=pos_data["entry_price"],
                    amount=pos_data["amount"],
                    usd_value=pos_data["usd_value"],
                    entry_time=datetime.fromisoformat(pos_data["entry_time"]),
                    strategy=pos_data["strategy"],
                    stop_loss=pos_data.get("stop_loss"),
                    take_profit=pos_data.get("take_profit"),
                    trailing_stop_pct=pos_data.get("trailing_stop_pct", 0.05),
                    highest_price=pos_data.get(
                        "highest_price", pos_data["entry_price"]
                    ),
                    fees_paid=pos_data.get("fees_paid", 0),
                )

            # Restore stats
            stats = state.get("stats", {})
            self.total_trades = stats.get("total_trades", 0)
            self.winning_trades = stats.get("winning_trades", 0)
            self.total_fees = stats.get("total_fees", 0)
            self.total_slippage = stats.get("total_slippage", 0)

            logger.info(
                f"Loaded state: ${self.balance:.2f} balance, {len(self.positions)} positions"
            )

        except Exception as e:
            logger.error(f"Failed to load state: {e}")

    def save_trades(self):
        """Save completed trades to file"""
        trades_data = [
            {
                "symbol": t.symbol,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "amount": t.amount,
                "entry_time": t.entry_time.isoformat(),
                "exit_time": t.exit_time.isoformat(),
                "pnl_usd": t.pnl_usd,
                "pnl_percent": t.pnl_percent,
                "fees_paid": t.fees_paid,
                "strategy": t.strategy,
                "trade_type": t.trade_type,
                "exit_reason": t.exit_reason,
            }
            for t in self.trades
        ]

        self.trades_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.trades_file, "w") as f:
            json.dump(trades_data, f, indent=2)
