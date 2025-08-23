"""
DCA Strategy Executor

Manages the execution lifecycle of DCA trades:
- Places grid orders based on calculated levels
- Monitors positions for price movements
- Handles exits (take profit/stop loss)
- Tracks position state and P&L
- Manages partial fills
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
from loguru import logger
import pandas as pd

from src.data.supabase_client import SupabaseClient
from src.strategies.dca.grid import GridCalculator
from src.trading.position_sizer import AdaptivePositionSizer


class OrderStatus(Enum):
    """Order status enumeration."""

    PENDING = "PENDING"
    PLACED = "PLACED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class PositionStatus(Enum):
    """Position status enumeration."""

    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"
    STOPPED_OUT = "STOPPED_OUT"
    TAKE_PROFIT = "TAKE_PROFIT"


class DCAExecutor:
    """Executes and manages DCA trading strategies."""

    def __init__(
        self,
        supabase_client: SupabaseClient,
        position_sizer: AdaptivePositionSizer,
        paper_trader=None,  # Will be injected when paper_trader is created
        config: Optional[Dict] = None,
    ):
        """
        Initialize DCA Executor.

        Args:
            supabase_client: Database client
            position_sizer: Position sizing calculator
            paper_trader: Paper trading interface (optional)
            config: Executor configuration
        """
        self.supabase = supabase_client
        self.position_sizer = position_sizer
        self.paper_trader = paper_trader
        self.config = config or self._default_config()

        # Active positions tracking
        self.active_positions = {}
        self.pending_orders = {}

        # Monitoring control
        self.monitoring_active = False
        self.monitor_task = None

    def _default_config(self) -> Dict:
        """Default executor configuration."""
        return {
            "max_positions": 5,
            "max_position_size": 1000,  # Maximum USD per position
            "min_order_size": 10,  # Minimum order size
            "monitor_interval": 5,  # Seconds between price checks
            "slippage_tolerance": 0.002,  # 0.2% slippage tolerance
            "partial_fill_threshold": 0.8,  # 80% fill to consider position active
            "time_exit_enabled": True,
            "max_hold_hours": 72,
        }

    async def execute_grid(self, symbol: str, grid: Dict, ml_predictions: Dict, setup_data: Dict) -> Dict:
        """
        Execute a DCA grid strategy.

        Args:
            symbol: Trading symbol
            grid: Grid configuration from GridCalculator
            ml_predictions: ML model predictions
            setup_data: Setup detection data

        Returns:
            Execution result with position ID
        """
        try:
            # Validate execution conditions
            is_valid, error = self._validate_execution(symbol, grid)
            if not is_valid:
                logger.warning(f"Grid execution validation failed for {symbol}: {error}")
                return {"success": False, "error": error}

            # Create position entry
            position_id = await self._create_position(symbol, grid, ml_predictions, setup_data)

            # Place grid orders
            orders = await self._place_grid_orders(position_id, symbol, grid)

            # Store position in active tracking
            self.active_positions[position_id] = {
                "symbol": symbol,
                "grid": grid,
                "orders": orders,
                "ml_predictions": ml_predictions,
                "setup_data": setup_data,
                "status": PositionStatus.ACTIVE,
                "created_at": datetime.now(),
                "filled_levels": 0,
                "total_invested": 0,
                "current_value": 0,
                "pnl": 0,
                "pnl_percent": 0,
            }

            logger.info(f"Executed DCA grid for {symbol}: " f"{len(orders)} orders placed, position ID: {position_id}")

            return {
                "success": True,
                "position_id": position_id,
                "orders_placed": len(orders),
                "total_investment": grid["total_investment"],
                "average_entry": grid["average_entry"],
                "take_profit": grid["take_profit"],
                "stop_loss": grid["stop_loss"],
            }

        except Exception as e:
            logger.error(f"Error executing grid for {symbol}: {e}")
            return {"success": False, "error": str(e)}

    def _validate_execution(self, symbol: str, grid: Dict) -> Tuple[bool, Optional[str]]:
        """
        Validate if grid can be executed.

        Args:
            symbol: Trading symbol
            grid: Grid configuration

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check max positions
        active_count = sum(1 for p in self.active_positions.values() if p["status"] == PositionStatus.ACTIVE)
        if active_count >= self.config["max_positions"]:
            return False, f"Max positions reached ({self.config['max_positions']})"

        # Check if symbol already has active position
        for position in self.active_positions.values():
            if position["symbol"] == symbol and position["status"] == PositionStatus.ACTIVE:
                return False, f"Already have active position for {symbol}"

        # Check position size limits
        if grid["total_investment"] > self.config["max_position_size"]:
            return (
                False,
                f"Position size exceeds limit: ${grid['total_investment']:.2f}",
            )

        # Check minimum order sizes
        for level in grid["levels"]:
            if level["size"] < self.config["min_order_size"]:
                return False, f"Order size below minimum: ${level['size']:.2f}"

        return True, None

    async def _create_position(self, symbol: str, grid: Dict, ml_predictions: Dict, setup_data: Dict) -> str:
        """
        Create position entry in database.

        Args:
            symbol: Trading symbol
            grid: Grid configuration
            ml_predictions: ML predictions
            setup_data: Setup data

        Returns:
            Position ID
        """
        position_data = {
            "strategy_name": "DCA",
            "symbol": symbol,
            "status": PositionStatus.PENDING.value,
            "entry_time": datetime.now().isoformat(),
            "grid_config": json.dumps(grid),
            "ml_predictions": json.dumps(ml_predictions),
            "setup_data": json.dumps(setup_data),
            "planned_investment": grid["total_investment"],
            "target_profit": grid["take_profit"],
            "stop_loss": grid["stop_loss"],
            "expected_hold_hours": ml_predictions.get("hold_time", 24),
        }

        if self.paper_trader:
            # Use paper trader for position creation
            result = await self.paper_trader.create_position(position_data)
            return result["position_id"]
        else:
            # Direct database insertion for testing
            result = self.supabase.client.table("positions").insert(position_data).execute()
            return result.data[0]["position_id"]

    async def _place_grid_orders(self, position_id: str, symbol: str, grid: Dict) -> List[Dict]:
        """
        Place orders for all grid levels.

        Args:
            position_id: Position ID
            symbol: Trading symbol
            grid: Grid configuration

        Returns:
            List of order details
        """
        orders = []

        for level in grid["levels"]:
            order = {
                "position_id": position_id,
                "symbol": symbol,
                "side": "BUY",
                "order_type": "LIMIT",
                "price": level["price"],
                "quantity": level["size_crypto"],
                "size_usd": level["size"],
                "status": OrderStatus.PENDING.value,
                "level": level["level"],
                "created_at": datetime.now().isoformat(),
            }

            if self.paper_trader:
                # Use paper trader to place order
                result = await self.paper_trader.place_order(order)
                order["order_id"] = result["order_id"]
                order["status"] = OrderStatus.PLACED.value
            else:
                # Simulate order placement
                order["order_id"] = f"SIM_{position_id}_{level['level']}"
                order["status"] = OrderStatus.PLACED.value

            orders.append(order)

            # Store in pending orders
            self.pending_orders[order["order_id"]] = order

        return orders

    async def monitor_positions(self):
        """
        Monitor active positions for exit conditions.
        Runs continuously while monitoring is active.
        """
        logger.info("Starting position monitoring")
        self.monitoring_active = True

        while self.monitoring_active:
            try:
                # Check each active position
                for position_id, position in list(self.active_positions.items()):
                    if position["status"] != PositionStatus.ACTIVE:
                        continue

                    # Get current price
                    current_price = await self._get_current_price(position["symbol"])
                    if not current_price:
                        continue

                    # Check for exit conditions
                    exit_reason = await self._check_exit_conditions(position, current_price)

                    if exit_reason:
                        await self.handle_exit(position_id, exit_reason, current_price)
                    else:
                        # Update position metrics
                        await self._update_position_metrics(position_id, current_price)

                    # Check for fill opportunities
                    await self._check_pending_fills(position_id, current_price)

                # Wait before next check
                await asyncio.sleep(self.config["monitor_interval"])

            except Exception as e:
                logger.error(f"Error in position monitoring: {e}")
                await asyncio.sleep(self.config["monitor_interval"])

    async def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for symbol."""
        try:
            if self.paper_trader:
                return await self.paper_trader.get_price(symbol)
            else:
                # Get from database (most recent price)
                result = (
                    self.supabase.client.table("unified_ohlc")
                    .select("close")
                    .eq("symbol", symbol)
                    .order("timestamp", desc=True)
                    .limit(1)
                    .execute()
                )
                if result.data:
                    return result.data[0]["close"]
        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")
        return None

    async def _check_exit_conditions(self, position: Dict, current_price: float) -> Optional[str]:
        """
        Check if position should be exited.

        Args:
            position: Position data
            current_price: Current market price

        Returns:
            Exit reason if should exit, None otherwise
        """
        grid = position["grid"]

        # Check take profit
        if current_price >= grid["take_profit"]:
            return "TAKE_PROFIT"

        # Check stop loss
        if current_price <= grid["stop_loss"]:
            return "STOP_LOSS"

        # Check time exit
        if self.config["time_exit_enabled"]:
            hold_time = datetime.now() - position["created_at"]
            max_hold = timedelta(hours=self.config["max_hold_hours"])
            if hold_time > max_hold:
                return "TIME_EXIT"

        return None

    async def _check_pending_fills(self, position_id: str, current_price: float):
        """
        Check if any pending orders should be filled.

        Args:
            position_id: Position ID
            current_price: Current market price
        """
        position = self.active_positions.get(position_id)
        if not position:
            return

        for order in position["orders"]:
            if order["status"] != OrderStatus.PLACED.value:
                continue

            # Check if price has reached order level
            if current_price <= order["price"] * (1 + self.config["slippage_tolerance"]):
                # Simulate fill
                order["status"] = OrderStatus.FILLED.value
                order["filled_at"] = datetime.now().isoformat()
                order["filled_price"] = current_price

                # Update position
                position["filled_levels"] += 1
                position["total_invested"] += order["size_usd"]

                logger.info(f"Filled level {order['level']} for {position['symbol']} " f"at ${current_price:.2f}")

    async def handle_exit(self, position_id: str, exit_reason: str, exit_price: float) -> Dict:
        """
        Handle position exit.

        Args:
            position_id: Position ID
            exit_reason: Reason for exit
            exit_price: Exit price

        Returns:
            Exit result
        """
        try:
            position = self.active_positions.get(position_id)
            if not position:
                return {"success": False, "error": "Position not found"}

            # Calculate P&L
            total_quantity = sum(o["quantity"] for o in position["orders"] if o["status"] == OrderStatus.FILLED.value)
            exit_value = total_quantity * exit_price
            pnl = exit_value - position["total_invested"]
            pnl_percent = (pnl / position["total_invested"] * 100) if position["total_invested"] > 0 else 0

            # Update position status
            position["status"] = PositionStatus.CLOSED
            position["exit_time"] = datetime.now()
            position["exit_reason"] = exit_reason
            position["exit_price"] = exit_price
            position["pnl"] = pnl
            position["pnl_percent"] = pnl_percent

            # Cancel remaining orders
            await self._cancel_remaining_orders(position_id)

            # Log exit
            logger.info(
                f"Exited {position['symbol']} position: "
                f"{exit_reason} at ${exit_price:.2f}, "
                f"P&L: ${pnl:.2f} ({pnl_percent:.1f}%)"
            )

            # Store exit in database
            if self.paper_trader:
                await self.paper_trader.close_position(position_id, exit_reason, pnl)

            return {
                "success": True,
                "exit_reason": exit_reason,
                "exit_price": exit_price,
                "pnl": pnl,
                "pnl_percent": pnl_percent,
                "hold_time_hours": (position["exit_time"] - position["created_at"]).total_seconds() / 3600,
            }

        except Exception as e:
            logger.error(f"Error handling exit for position {position_id}: {e}")
            return {"success": False, "error": str(e)}

    async def _cancel_remaining_orders(self, position_id: str):
        """Cancel all remaining orders for a position."""
        position = self.active_positions.get(position_id)
        if not position:
            return

        for order in position["orders"]:
            if order["status"] in [OrderStatus.PENDING.value, OrderStatus.PLACED.value]:
                order["status"] = OrderStatus.CANCELLED.value
                order["cancelled_at"] = datetime.now().isoformat()

                # Remove from pending orders
                self.pending_orders.pop(order["order_id"], None)

    async def _update_position_metrics(self, position_id: str, current_price: float):
        """Update position metrics (current value, unrealized P&L)."""
        position = self.active_positions.get(position_id)
        if not position:
            return

        # Calculate current value
        total_quantity = sum(o["quantity"] for o in position["orders"] if o["status"] == OrderStatus.FILLED.value)
        current_value = total_quantity * current_price

        # Update metrics
        position["current_value"] = current_value
        position["pnl"] = current_value - position["total_invested"]
        position["pnl_percent"] = (
            (position["pnl"] / position["total_invested"] * 100) if position["total_invested"] > 0 else 0
        )

    async def start_monitoring(self):
        """Start position monitoring task."""
        if not self.monitoring_active:
            self.monitor_task = asyncio.create_task(self.monitor_positions())
            logger.info("Position monitoring started")

    async def stop_monitoring(self):
        """Stop position monitoring task."""
        self.monitoring_active = False
        if self.monitor_task:
            await self.monitor_task
            logger.info("Position monitoring stopped")

    def get_active_positions(self) -> List[Dict]:
        """Get list of active positions."""
        return [
            {
                "position_id": pid,
                "symbol": p["symbol"],
                "status": (p["status"].value if isinstance(p["status"], PositionStatus) else p["status"]),
                "filled_levels": p["filled_levels"],
                "total_invested": p["total_invested"],
                "current_value": p["current_value"],
                "pnl": p["pnl"],
                "pnl_percent": p["pnl_percent"],
                "created_at": (
                    p["created_at"].isoformat() if isinstance(p["created_at"], datetime) else p["created_at"]
                ),
            }
            for pid, p in self.active_positions.items()
            if p["status"] in [PositionStatus.ACTIVE, PositionStatus.ACTIVE.value]
        ]

    def get_position_details(self, position_id: str) -> Optional[Dict]:
        """Get detailed information about a specific position."""
        return self.active_positions.get(position_id)
