"""
Paper Trading Module

Simulates real trading without using actual money:
- Maintains virtual portfolio and balances
- Executes orders at current market prices
- Tracks positions, P&L, and performance metrics
- Records all trades for analysis
- Provides realistic slippage and fee simulation
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, asdict
from loguru import logger
import pandas as pd

from src.data.supabase_client import SupabaseClient


class OrderType(Enum):
    """Order type enumeration."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderSide(Enum):
    """Order side enumeration."""

    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    """Order status enumeration."""

    PENDING = "PENDING"
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class Order:
    """Order data structure."""

    order_id: str
    position_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float]
    stop_price: Optional[float]
    status: OrderStatus
    created_at: datetime
    filled_at: Optional[datetime] = None
    filled_price: Optional[float] = None
    filled_quantity: float = 0.0
    fees: float = 0.0
    slippage: float = 0.0


@dataclass
class Position:
    """Position data structure."""

    position_id: str
    symbol: str
    strategy: str
    side: str  # LONG or SHORT
    quantity: float
    entry_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float
    created_at: datetime
    status: str  # OPEN, CLOSED
    closed_at: Optional[datetime] = None

    def update_price(self, current_price: float):
        """Update position with current price."""
        self.current_price = current_price
        self.market_value = self.quantity * current_price
        if self.side == "LONG":
            self.unrealized_pnl = (current_price - self.entry_price) * self.quantity
        else:  # SHORT
            self.unrealized_pnl = (self.entry_price - current_price) * self.quantity


class PaperTrader:
    """Simulates trading without real money."""

    def __init__(
        self,
        supabase_client: SupabaseClient,
        initial_balance: float = 10000.0,
        config: Optional[Dict] = None,
    ):
        """
        Initialize Paper Trader.

        Args:
            supabase_client: Database client
            initial_balance: Starting virtual balance
            config: Trading configuration
        """
        self.supabase = supabase_client
        self.config = config or self._default_config()

        # Portfolio state
        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.positions = {}  # position_id -> Position
        self.orders = {}  # order_id -> Order
        self.holdings = {}  # symbol -> quantity

        # Performance tracking
        self.trades = []
        self.daily_balances = []
        self.peak_balance = initial_balance
        self.max_drawdown = 0.0

        # Order management
        self.pending_orders = {}
        self.order_history = []

    def _default_config(self) -> Dict:
        """Default paper trading configuration."""
        return {
            "trading_fee": 0.001,  # 0.1% trading fee
            "slippage_pct": 0.0005,  # 0.05% slippage
            "max_position_size": 0.1,  # Max 10% of portfolio per position
            "max_positions": 10,  # Maximum concurrent positions
            "allow_shorting": False,  # Whether to allow short positions
            "margin_enabled": False,  # Whether to allow margin trading
            "margin_multiplier": 1.0,  # Leverage multiplier
            "stop_loss_enabled": True,  # Auto stop-loss orders
            "take_profit_enabled": True,  # Auto take-profit orders
        }

    async def create_position(self, position_data: Dict) -> Dict:
        """
        Create a new position entry.

        Args:
            position_data: Position details

        Returns:
            Position creation result
        """
        try:
            position_id = f"PAPER_{uuid.uuid4().hex[:8]}"

            position = Position(
                position_id=position_id,
                symbol=position_data["symbol"],
                strategy=position_data.get("strategy_name", "UNKNOWN"),
                side="LONG",  # Default to long positions
                quantity=0.0,  # Will be filled by orders
                entry_price=0.0,
                current_price=0.0,
                market_value=0.0,
                unrealized_pnl=0.0,
                realized_pnl=0.0,
                created_at=datetime.now(),
                closed_at=None,
                status="OPEN",
            )

            self.positions[position_id] = position

            # Store in database
            await self._store_position(position)

            logger.info(f"Created paper position {position_id} for {position.symbol}")

            return {
                "success": True,
                "position_id": position_id,
                "message": f"Position created for {position.symbol}",
            }

        except Exception as e:
            logger.error(f"Error creating position: {e}")
            return {"success": False, "error": str(e)}

    async def place_order(self, order_data: Dict) -> Dict:
        """
        Place a simulated order.

        Args:
            order_data: Order details

        Returns:
            Order placement result
        """
        try:
            # Validate order
            validation = self._validate_order(order_data)
            if not validation["valid"]:
                return {"success": False, "error": validation["error"]}

            # Create order
            order_id = f"ORDER_{uuid.uuid4().hex[:8]}"

            order = Order(
                order_id=order_id,
                position_id=order_data.get("position_id", ""),
                symbol=order_data["symbol"],
                side=OrderSide[order_data["side"]],
                order_type=OrderType[order_data.get("order_type", "LIMIT")],
                quantity=order_data.get("quantity", 0),
                price=order_data.get("price"),
                stop_price=order_data.get("stop_price"),
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )

            self.orders[order_id] = order

            # Process order based on type
            if order.order_type == OrderType.MARKET:
                await self._execute_market_order(order)
            else:
                await self._add_pending_order(order)

            logger.info(
                f"Placed {order.order_type.value} order {order_id}: "
                f"{order.side.value} {order.quantity} {order.symbol} @ ${order.price}"
            )

            return {"success": True, "order_id": order_id, "status": order.status.value}

        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return {"success": False, "error": str(e)}

    def _validate_order(self, order_data: Dict) -> Dict:
        """
        Validate order parameters.

        Args:
            order_data: Order details

        Returns:
            Validation result
        """
        # Check required fields
        if "symbol" not in order_data:
            return {"valid": False, "error": "Symbol required"}

        if "side" not in order_data:
            return {"valid": False, "error": "Side (BUY/SELL) required"}

        # Check balance for buy orders
        if order_data["side"] == "BUY":
            order_value = order_data.get("quantity", 0) * order_data.get("price", 0)
            if order_value > self.balance:
                return {
                    "valid": False,
                    "error": f"Insufficient balance: need ${order_value:.2f}, have ${self.balance:.2f}",
                }

        # Check holdings for sell orders
        if order_data["side"] == "SELL":
            symbol = order_data["symbol"]
            quantity = order_data.get("quantity", 0)
            if symbol not in self.holdings or self.holdings[symbol] < quantity:
                return {
                    "valid": False,
                    "error": f"Insufficient holdings: need {quantity}, have {self.holdings.get(symbol, 0)}",
                }

        # Check position limits
        if len(self.positions) >= self.config["max_positions"]:
            open_positions = sum(
                1 for p in self.positions.values() if p.status == "OPEN"
            )
            if open_positions >= self.config["max_positions"]:
                return {
                    "valid": False,
                    "error": f"Maximum positions reached ({self.config['max_positions']})",
                }

        return {"valid": True}

    async def _execute_market_order(self, order: Order):
        """Execute a market order immediately."""
        try:
            # Get current price
            current_price = await self.get_price(order.symbol)
            if not current_price:
                order.status = OrderStatus.REJECTED
                return

            # Apply slippage
            slippage = current_price * self.config["slippage_pct"]
            if order.side == OrderSide.BUY:
                execution_price = current_price + slippage
            else:
                execution_price = current_price - slippage

            # Calculate fees
            order_value = order.quantity * execution_price
            fees = order_value * self.config["trading_fee"]

            # Execute order
            order.filled_price = execution_price
            order.filled_quantity = order.quantity
            order.filled_at = datetime.now()
            order.fees = fees
            order.slippage = slippage * order.quantity
            order.status = OrderStatus.FILLED

            # Update portfolio
            if order.side == OrderSide.BUY:
                self.balance -= order_value + fees
                if order.symbol not in self.holdings:
                    self.holdings[order.symbol] = 0
                self.holdings[order.symbol] += order.quantity

                # Update position
                if order.position_id in self.positions:
                    position = self.positions[order.position_id]
                    position.quantity += order.quantity
                    # Update weighted average entry price
                    if position.entry_price == 0:
                        position.entry_price = execution_price
                    else:
                        total_cost = position.entry_price * (
                            position.quantity - order.quantity
                        )
                        total_cost += execution_price * order.quantity
                        position.entry_price = total_cost / position.quantity
                    position.update_price(current_price)
            else:  # SELL
                self.balance += order_value - fees
                self.holdings[order.symbol] -= order.quantity
                if self.holdings[order.symbol] <= 0:
                    del self.holdings[order.symbol]

                # Update position P&L
                if order.position_id in self.positions:
                    position = self.positions[order.position_id]
                    position.quantity -= order.quantity
                    profit = (
                        execution_price - position.entry_price
                    ) * order.quantity - fees
                    position.realized_pnl += profit

                    if position.quantity <= 0:
                        position.status = "CLOSED"
                        position.closed_at = datetime.now()

            # Record trade
            self._record_trade(order)

        except Exception as e:
            logger.error(f"Error executing market order: {e}")
            order.status = OrderStatus.REJECTED

    async def _add_pending_order(self, order: Order):
        """Add order to pending queue for limit/stop orders."""
        order.status = OrderStatus.OPEN

        if order.symbol not in self.pending_orders:
            self.pending_orders[order.symbol] = []

        self.pending_orders[order.symbol].append(order)

    async def check_pending_orders(self, symbol: str, current_price: float):
        """
        Check if any pending orders should be executed.

        Args:
            symbol: Symbol to check
            current_price: Current market price
        """
        if symbol not in self.pending_orders:
            return

        orders_to_execute = []

        for order in self.pending_orders[symbol]:
            should_execute = False

            if order.order_type == OrderType.LIMIT:
                if order.side == OrderSide.BUY and current_price <= order.price:
                    should_execute = True
                elif order.side == OrderSide.SELL and current_price >= order.price:
                    should_execute = True

            elif order.order_type == OrderType.STOP:
                if order.side == OrderSide.BUY and current_price >= order.stop_price:
                    should_execute = True
                elif order.side == OrderSide.SELL and current_price <= order.stop_price:
                    should_execute = True

            if should_execute:
                orders_to_execute.append(order)

        # Execute triggered orders
        for order in orders_to_execute:
            self.pending_orders[symbol].remove(order)
            await self._execute_market_order(order)

    async def get_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol."""
        try:
            # Get latest price from database
            result = (
                self.supabase.client.table("unified_ohlc")
                .select("close")
                .eq("symbol", symbol)
                .eq("timeframe", "1min")
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )

            if result.data:
                return result.data[0]["close"]

            # Fallback to 15min if 1min not available
            result = (
                self.supabase.client.table("unified_ohlc")
                .select("close")
                .eq("symbol", symbol)
                .eq("timeframe", "15min")
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )

            if result.data:
                return result.data[0]["close"]

        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")

        return None

    async def close_position(
        self,
        position_id: str,
        reason: str = "MANUAL",
        exit_price: Optional[float] = None,
    ) -> Dict:
        """
        Close a position.

        Args:
            position_id: Position to close
            reason: Reason for closing
            exit_price: Exit price (uses current if not provided)

        Returns:
            Close result
        """
        try:
            if position_id not in self.positions:
                return {"success": False, "error": "Position not found"}

            position = self.positions[position_id]

            if position.status == "CLOSED":
                return {"success": False, "error": "Position already closed"}

            # Get exit price
            if not exit_price:
                exit_price = await self.get_price(position.symbol)
                if not exit_price:
                    return {"success": False, "error": "Could not get current price"}

            # Create sell order to close position
            sell_order = {
                "position_id": position_id,
                "symbol": position.symbol,
                "side": "SELL",
                "order_type": "MARKET",
                "quantity": position.quantity,
                "price": exit_price,
            }

            # Place the sell order
            result = await self.place_order(sell_order)

            if result["success"]:
                position.status = "CLOSED"
                position.closed_at = datetime.now()

                # Calculate final P&L
                final_pnl = position.realized_pnl + position.unrealized_pnl

                logger.info(
                    f"Closed position {position_id}: {position.symbol} "
                    f"P&L: ${final_pnl:.2f} ({reason})"
                )

                return {
                    "success": True,
                    "final_pnl": final_pnl,
                    "exit_price": exit_price,
                    "reason": reason,
                }
            else:
                return result

        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return {"success": False, "error": str(e)}

    def _record_trade(self, order: Order):
        """Record completed trade."""
        trade = {
            "trade_id": f"TRADE_{uuid.uuid4().hex[:8]}",
            "order_id": order.order_id,
            "position_id": order.position_id,
            "symbol": order.symbol,
            "side": order.side.value,
            "quantity": order.filled_quantity,
            "price": order.filled_price,
            "fees": order.fees,
            "slippage": order.slippage,
            "timestamp": order.filled_at.isoformat() if order.filled_at else None,
        }

        self.trades.append(trade)
        self.order_history.append(order)

        # Update performance metrics
        self._update_performance_metrics()

    def _update_performance_metrics(self):
        """Update portfolio performance metrics."""
        # Calculate total portfolio value
        portfolio_value = self.balance

        for position in self.positions.values():
            if position.status == "OPEN":
                portfolio_value += position.market_value

        # Update peak and drawdown
        if portfolio_value > self.peak_balance:
            self.peak_balance = portfolio_value

        drawdown = (self.peak_balance - portfolio_value) / self.peak_balance
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown

        # Record daily balance
        today = datetime.now().date()
        if not self.daily_balances or self.daily_balances[-1]["date"] != today:
            self.daily_balances.append(
                {
                    "date": today,
                    "balance": portfolio_value,
                    "cash": self.balance,
                    "positions_value": portfolio_value - self.balance,
                }
            )

    async def _store_position(self, position: Position):
        """Store position in database."""
        try:
            data = {
                "position_id": position.position_id,
                "symbol": position.symbol,
                "strategy": position.strategy,
                "side": position.side,
                "quantity": position.quantity,
                "entry_price": position.entry_price,
                "status": position.status,
                "created_at": position.created_at.isoformat(),
                "is_paper": True,  # Mark as paper trade
            }

            self.supabase.client.table("positions").insert(data).execute()

        except Exception as e:
            logger.error(f"Error storing position: {e}")

    def get_portfolio_summary(self) -> Dict:
        """Get current portfolio summary."""
        portfolio_value = self.balance
        open_positions = []

        for position in self.positions.values():
            if position.status == "OPEN":
                portfolio_value += position.market_value
                open_positions.append(
                    {
                        "symbol": position.symbol,
                        "quantity": position.quantity,
                        "entry_price": position.entry_price,
                        "current_price": position.current_price,
                        "unrealized_pnl": position.unrealized_pnl,
                        "unrealized_pnl_pct": (
                            position.unrealized_pnl
                            / (position.entry_price * position.quantity)
                            * 100
                        )
                        if position.entry_price > 0
                        else 0,
                    }
                )

        total_return = (
            (portfolio_value - self.initial_balance) / self.initial_balance * 100
        )

        return {
            "portfolio_value": portfolio_value,
            "cash_balance": self.balance,
            "positions_value": portfolio_value - self.balance,
            "total_return": total_return,
            "max_drawdown": self.max_drawdown * 100,
            "open_positions": len(open_positions),
            "total_trades": len(self.trades),
            "positions": open_positions,
        }

    def get_performance_stats(self) -> Dict:
        """Calculate detailed performance statistics."""
        if not self.trades:
            return {
                "total_trades": 0,
                "win_rate": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "profit_factor": 0,
                "sharpe_ratio": 0,
                "total_pnl": 0,
            }

        # Calculate P&L for each closed position
        closed_pnls = []
        for position in self.positions.values():
            if position.status == "CLOSED":
                closed_pnls.append(position.realized_pnl)

        if not closed_pnls:
            return {
                "total_trades": len(self.trades),
                "win_rate": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "profit_factor": 0,
                "sharpe_ratio": 0,
                "total_pnl": 0,
            }

        wins = [pnl for pnl in closed_pnls if pnl > 0]
        losses = [pnl for pnl in closed_pnls if pnl < 0]

        win_rate = len(wins) / len(closed_pnls) * 100 if closed_pnls else 0
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0

        # Profit factor
        total_wins = sum(wins) if wins else 0
        total_losses = abs(sum(losses)) if losses else 1
        profit_factor = total_wins / total_losses if total_losses > 0 else 0

        # Sharpe ratio (simplified)
        if len(self.daily_balances) > 1:
            daily_returns = []
            for i in range(1, len(self.daily_balances)):
                prev = self.daily_balances[i - 1]["balance"]
                curr = self.daily_balances[i]["balance"]
                daily_returns.append((curr - prev) / prev)

            if daily_returns:
                avg_return = sum(daily_returns) / len(daily_returns)
                std_return = pd.Series(daily_returns).std()
                sharpe_ratio = (
                    (avg_return / std_return * (252**0.5)) if std_return > 0 else 0
                )
            else:
                sharpe_ratio = 0
        else:
            sharpe_ratio = 0

        return {
            "total_trades": len(self.trades),
            "closed_positions": len(closed_pnls),
            "win_rate": win_rate,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "sharpe_ratio": sharpe_ratio,
            "total_pnl": sum(closed_pnls),
            "max_drawdown": self.max_drawdown * 100,
        }
