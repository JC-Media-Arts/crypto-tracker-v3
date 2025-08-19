"""
ML Signal Strategy for Hummingbot

This custom strategy connects our ML predictions to Hummingbot's trading engine.
It reads signals from our Signal Generator and executes trades through Hummingbot.
"""

from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionSide
from hummingbot.core.event.events import OrderFilledEvent

# Import our modules
try:
    from src.data.supabase_client import SupabaseClient
    from src.strategies.signal_generator import SignalGenerator
    from src.strategies.dca.executor import DCAExecutor
    MODULES_AVAILABLE = True
except ImportError:
    MODULES_AVAILABLE = False
    print("Warning: Custom modules not available. Running in standalone mode.")


class MLSignalStrategy(ScriptStrategyBase):
    """
    Hummingbot strategy that executes trades based on ML signals.
    
    This strategy:
    1. Monitors for ML signals from our Signal Generator
    2. Executes DCA grids when signals are approved
    3. Manages positions with stop loss and take profit
    4. Tracks performance and reports to Slack
    """
    
    # Strategy configuration
    markets = {"kraken_paper_trade": {"BTC-USD", "ETH-USD", "SOL-USD"}}  # Start with top 3
    
    def __init__(self):
        super().__init__()
        
        # Configuration
        self.check_interval = 60  # Check for signals every 60 seconds
        self.position_size_usd = Decimal("100")  # $100 per position
        self.max_positions = 5
        self.stop_loss_pct = Decimal("0.05")  # 5% stop loss
        self.take_profit_pct = Decimal("0.10")  # 10% take profit
        self.min_confidence = 0.60
        
        # State tracking
        self.active_positions = {}
        self.pending_orders = {}
        self.last_signal_check = datetime.now()
        
        # Initialize connections if modules available
        if MODULES_AVAILABLE:
            self._initialize_connections()
        else:
            self.signal_generator = None
            self.dca_executor = None
            
    def _initialize_connections(self):
        """Initialize connections to our ML system."""
        try:
            # Initialize Supabase client
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_KEY")
            
            if supabase_url and supabase_key:
                self.supabase = SupabaseClient(supabase_url, supabase_key)
                
                # Initialize Signal Generator
                self.signal_generator = SignalGenerator(
                    supabase_client=self.supabase,
                    config={
                        "scan_interval": 60,
                        "min_confidence": self.min_confidence,
                        "enable_ml_filtering": True,
                        "auto_execute": False,  # We'll handle execution
                    }
                )
                
                # Initialize DCA Executor
                self.dca_executor = DCAExecutor(
                    supabase_client=self.supabase,
                    position_sizer=None,  # Will use Hummingbot's position sizing
                    paper_trader=None,  # Using Hummingbot instead
                )
                
                self.logger.info("ML Signal Strategy initialized with database connection")
            else:
                self.logger.warning("No database credentials found, running in standalone mode")
                self.signal_generator = None
                self.dca_executor = None
                
        except Exception as e:
            self.logger.error(f"Error initializing connections: {e}")
            self.signal_generator = None
            self.dca_executor = None
    
    def on_tick(self):
        """
        Called on every tick (1 second).
        Check for ML signals periodically.
        """
        # Check for signals every check_interval seconds
        if (datetime.now() - self.last_signal_check).total_seconds() >= self.check_interval:
            self._check_ml_signals()
            self.last_signal_check = datetime.now()
        
        # Monitor active positions
        self._monitor_positions()
        
    def _check_ml_signals(self):
        """Check for new ML signals and execute trades."""
        try:
            if not self.signal_generator:
                # Demo mode: generate fake signals for testing
                self._generate_demo_signals()
                return
            
            # Get active signals from Signal Generator
            signals = self.signal_generator.get_active_signals()
            
            for signal in signals:
                if signal["status"] == "APPROVED" and signal["confidence"] >= self.min_confidence:
                    # Check if we already have a position for this symbol
                    trading_pair = self._convert_symbol_to_pair(signal["symbol"])
                    
                    if trading_pair not in self.active_positions:
                        # Execute the signal
                        self._execute_ml_signal(signal)
                        
        except Exception as e:
            self.logger.error(f"Error checking ML signals: {e}")
    
    def _execute_ml_signal(self, signal: Dict):
        """
        Execute a trade based on ML signal.
        
        Args:
            signal: Signal data from Signal Generator
        """
        try:
            symbol = signal["symbol"]
            trading_pair = self._convert_symbol_to_pair(symbol)
            
            # Check if we have room for more positions
            if len(self.active_positions) >= self.max_positions:
                self.logger.info(f"Max positions reached, skipping {symbol}")
                return
            
            # Get current market price
            mid_price = self.connectors["kraken_paper_trade"].get_mid_price(trading_pair)
            
            if not mid_price:
                self.logger.warning(f"No price available for {trading_pair}")
                return
            
            # Calculate order amount
            amount = self.position_size_usd / mid_price
            
            # If we have grid configuration, place grid orders
            if signal.get("grid_config"):
                self._execute_dca_grid(signal, trading_pair, mid_price)
            else:
                # Simple market buy
                self.logger.info(
                    f"Placing BUY order for {trading_pair}: "
                    f"{amount:.8f} @ {mid_price:.2f} "
                    f"(confidence: {signal['confidence']:.1%})"
                )
                
                # Place market buy order
                order_id = self.buy(
                    connector_name="kraken_paper_trade",
                    trading_pair=trading_pair,
                    amount=amount,
                    order_type=OrderType.MARKET,
                    price=mid_price,
                )
                
                # Track position
                self.active_positions[trading_pair] = {
                    "signal": signal,
                    "entry_price": float(mid_price),
                    "amount": float(amount),
                    "order_id": order_id,
                    "stop_loss": float(mid_price * (1 - self.stop_loss_pct)),
                    "take_profit": float(mid_price * (1 + self.take_profit_pct)),
                    "created_at": datetime.now(),
                }
                
        except Exception as e:
            self.logger.error(f"Error executing ML signal: {e}")
    
    def _execute_dca_grid(self, signal: Dict, trading_pair: str, current_price: Decimal):
        """
        Execute a DCA grid based on ML signal.
        
        Args:
            signal: Signal with grid configuration
            trading_pair: Hummingbot trading pair
            current_price: Current market price
        """
        try:
            grid = signal["grid_config"]
            
            self.logger.info(
                f"Executing DCA grid for {trading_pair}: "
                f"{len(grid['levels'])} levels, "
                f"total investment: ${grid['total_investment']:.2f}"
            )
            
            # Place orders for each grid level
            order_ids = []
            for level in grid["levels"]:
                # Calculate order amount for this level
                level_amount = Decimal(str(level["size"])) / Decimal(str(level["price"]))
                
                # Place limit buy order
                order_id = self.buy(
                    connector_name="kraken_paper_trade",
                    trading_pair=trading_pair,
                    amount=level_amount,
                    order_type=OrderType.LIMIT,
                    price=Decimal(str(level["price"])),
                )
                
                order_ids.append(order_id)
                
                self.logger.info(
                    f"  Level {level['level']}: "
                    f"BUY {level_amount:.8f} @ ${level['price']:.2f}"
                )
            
            # Track grid position
            self.active_positions[trading_pair] = {
                "signal": signal,
                "grid": grid,
                "order_ids": order_ids,
                "entry_price": float(grid["average_entry"]),
                "stop_loss": float(grid["stop_loss"]),
                "take_profit": float(grid["take_profit"]),
                "created_at": datetime.now(),
                "type": "DCA_GRID",
            }
            
        except Exception as e:
            self.logger.error(f"Error executing DCA grid: {e}")
    
    def _monitor_positions(self):
        """Monitor active positions for exit conditions."""
        for trading_pair, position in list(self.active_positions.items()):
            try:
                # Get current price
                mid_price = self.connectors["kraken_paper_trade"].get_mid_price(trading_pair)
                
                if not mid_price:
                    continue
                
                current_price = float(mid_price)
                
                # Check stop loss
                if current_price <= position["stop_loss"]:
                    self.logger.info(
                        f"Stop loss triggered for {trading_pair}: "
                        f"${current_price:.2f} <= ${position['stop_loss']:.2f}"
                    )
                    self._close_position(trading_pair, "STOP_LOSS")
                
                # Check take profit
                elif current_price >= position["take_profit"]:
                    self.logger.info(
                        f"Take profit triggered for {trading_pair}: "
                        f"${current_price:.2f} >= ${position['take_profit']:.2f}"
                    )
                    self._close_position(trading_pair, "TAKE_PROFIT")
                
                # Check time exit (24 hours)
                elif (datetime.now() - position["created_at"]).total_seconds() > 86400:
                    self.logger.info(f"Time exit triggered for {trading_pair} (24 hours)")
                    self._close_position(trading_pair, "TIME_EXIT")
                    
            except Exception as e:
                self.logger.error(f"Error monitoring position {trading_pair}: {e}")
    
    def _close_position(self, trading_pair: str, reason: str):
        """
        Close a position.
        
        Args:
            trading_pair: Trading pair to close
            reason: Reason for closing
        """
        try:
            position = self.active_positions.get(trading_pair)
            if not position:
                return
            
            # Cancel any pending orders for DCA grids
            if position.get("type") == "DCA_GRID":
                for order_id in position.get("order_ids", []):
                    try:
                        self.cancel(
                            connector_name="kraken_paper_trade",
                            trading_pair=trading_pair,
                            order_id=order_id
                        )
                    except:
                        pass  # Order might already be filled
            
            # Get current balance
            balance = self.connectors["kraken_paper_trade"].get_balance(trading_pair.split("-")[0])
            
            if balance > 0:
                # Place market sell order
                self.logger.info(f"Closing position {trading_pair}: {balance:.8f} units")
                
                self.sell(
                    connector_name="kraken_paper_trade",
                    trading_pair=trading_pair,
                    amount=balance,
                    order_type=OrderType.MARKET,
                )
            
            # Calculate P&L
            current_price = float(self.connectors["kraken_paper_trade"].get_mid_price(trading_pair))
            entry_price = position["entry_price"]
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
            
            self.logger.info(
                f"Position closed: {trading_pair} "
                f"P&L: {pnl_pct:+.2f}% "
                f"Reason: {reason}"
            )
            
            # Remove from active positions
            del self.active_positions[trading_pair]
            
            # Log to database if available
            if self.supabase:
                self._log_trade_to_database(trading_pair, position, reason, pnl_pct)
                
        except Exception as e:
            self.logger.error(f"Error closing position: {e}")
    
    def _log_trade_to_database(self, trading_pair: str, position: Dict, exit_reason: str, pnl_pct: float):
        """Log completed trade to database."""
        try:
            trade_data = {
                "hummingbot_order_id": position.get("order_id", ""),
                "strategy_name": "DCA" if position.get("type") == "DCA_GRID" else "ML_SIGNAL",
                "symbol": trading_pair.split("-")[0],
                "side": "BUY",
                "order_type": "MARKET",
                "price": position["entry_price"],
                "amount": position.get("amount", 0),
                "status": "CLOSED",
                "created_at": position["created_at"].isoformat(),
                "filled_at": datetime.now().isoformat(),
                "ml_confidence": position.get("signal", {}).get("confidence", 0),
                "pnl": pnl_pct,
            }
            
            self.supabase.client.table("hummingbot_trades").insert(trade_data).execute()
            
        except Exception as e:
            self.logger.error(f"Error logging trade to database: {e}")
    
    def _convert_symbol_to_pair(self, symbol: str) -> str:
        """
        Convert our symbol format to Hummingbot trading pair.
        
        Args:
            symbol: Symbol like "BTC" or "ETH"
            
        Returns:
            Trading pair like "BTC-USD"
        """
        return f"{symbol}-USD"
    
    def _generate_demo_signals(self):
        """Generate demo signals for testing without database connection."""
        # Only generate a signal occasionally
        import random
        if random.random() > 0.95:  # 5% chance per check
            symbols = ["BTC", "ETH", "SOL"]
            symbol = random.choice(symbols)
            
            self.logger.info(f"Demo signal generated for {symbol}")
            
            # Create a fake signal
            signal = {
                "symbol": symbol,
                "confidence": 0.65,
                "status": "APPROVED",
                "ml_predictions": {
                    "take_profit_percent": 10.0,
                    "stop_loss_percent": -5.0,
                }
            }
            
            self._execute_ml_signal(signal)
    
    def did_fill_order(self, event: OrderFilledEvent):
        """
        Called when an order is filled.
        
        Args:
            event: Order filled event
        """
        self.logger.info(
            f"Order filled: {event.trading_pair} "
            f"{event.trade_type.name} "
            f"{event.amount} @ {event.price}"
        )
    
    def format_status(self) -> str:
        """
        Format strategy status for display.
        
        Returns:
            Formatted status string
        """
        lines = []
        lines.append("\n╔══════════════════════════════════════╗")
        lines.append("║     ML Signal Strategy Status        ║")
        lines.append("╠══════════════════════════════════════╣")
        
        # Active positions
        lines.append(f"║ Active Positions: {len(self.active_positions):18} ║")
        
        for pair, position in self.active_positions.items():
            entry = position['entry_price']
            current = float(self.connectors["kraken_paper_trade"].get_mid_price(pair) or entry)
            pnl = ((current - entry) / entry) * 100
            
            lines.append(f"║  {pair:10} P&L: {pnl:+6.2f}%        ║")
        
        # Configuration
        lines.append("╠══════════════════════════════════════╣")
        lines.append(f"║ Position Size: ${float(self.position_size_usd):20.2f} ║")
        lines.append(f"║ Max Positions: {self.max_positions:21} ║")
        lines.append(f"║ Stop Loss: {float(self.stop_loss_pct)*100:23.1f}% ║")
        lines.append(f"║ Take Profit: {float(self.take_profit_pct)*100:20.1f}% ║")
        lines.append(f"║ Min Confidence: {self.min_confidence*100:18.0f}% ║")
        
        # Connection status
        lines.append("╠══════════════════════════════════════╣")
        if self.signal_generator:
            lines.append("║ ML System: Connected                 ║")
        else:
            lines.append("║ ML System: Demo Mode                 ║")
        
        lines.append("╚══════════════════════════════════════╝")
        
        return "\n".join(lines)