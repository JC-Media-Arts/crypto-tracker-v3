"""
ML Signal Strategy for Hummingbot
Reads ML predictions and executes trades based on signals
"""

import json
import os
from decimal import Decimal
from typing import Dict, Optional
from pathlib import Path

from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.core.data_type.common import OrderType, TradeType


class MLSignalStrategy(ScriptStrategyBase):
    """
    Custom Hummingbot strategy that executes trades based on ML signals.
    Reads signals from a JSON file updated by the ML system.
    """
    
    # Strategy parameters
    signal_file_path = "/data/ml_signals.json"
    check_interval = 30  # Check for signals every 30 seconds
    position_size_usd = Decimal("100")  # $100 per trade
    max_positions = 5
    stop_loss_pct = Decimal("0.05")  # 5% stop loss
    take_profit_pct = Decimal("0.10")  # 10% take profit
    min_confidence = Decimal("0.60")  # 60% minimum confidence
    
    # Markets to trade (configure based on your needs)
    markets = {"kraken_paper_trade": ["BTC-USDT", "ETH-USDT", "SOL-USDT"]}
    
    def __init__(self):
        super().__init__()
        self.last_check_timestamp = 0
        self.open_positions = {}
        self.processed_signals = set()
    
    def on_tick(self):
        """Called on every tick."""
        current_time = self.current_timestamp
        
        # Check for new signals every check_interval seconds
        if current_time - self.last_check_timestamp > self.check_interval:
            self.check_ml_signals()
            self.last_check_timestamp = current_time
        
        # Monitor open positions
        self.monitor_positions()
    
    def check_ml_signals(self):
        """Check for new ML signals and execute trades."""
        try:
            # Read signal file
            signal_path = Path(self.signal_file_path)
            if not signal_path.exists():
                return
            
            with open(signal_path, 'r') as f:
                data = json.load(f)
            
            signals = data.get("signals", [])
            
            for signal in signals:
                # Skip if already processed
                signal_id = f"{signal['symbol']}_{signal['timestamp']}"
                if signal_id in self.processed_signals:
                    continue
                
                # Check confidence threshold
                if Decimal(str(signal['confidence'])) < self.min_confidence:
                    continue
                
                # Check if we have room for more positions
                if len(self.open_positions) >= self.max_positions:
                    self.logger().info("Max positions reached, skipping signal")
                    continue
                
                # Execute trade based on signal
                self.execute_signal(signal)
                self.processed_signals.add(signal_id)
                
        except Exception as e:
            self.logger().error(f"Error reading ML signals: {e}")
    
    def execute_signal(self, signal: Dict):
        """Execute a trade based on ML signal."""
        symbol = signal['symbol']
        action = signal['action']  # UP or DOWN
        confidence = Decimal(str(signal['confidence']))
        
        # Convert symbol to trading pair format
        trading_pair = f"{symbol}-USDT"
        
        # Check if we already have a position in this symbol
        if symbol in self.open_positions:
            self.logger().info(f"Already have position in {symbol}, skipping")
            return
        
        # Get current price
        connector_name = list(self.markets.keys())[0]
        current_price = self.connectors[connector_name].get_mid_price(trading_pair)
        
        if current_price is None:
            self.logger().error(f"Could not get price for {trading_pair}")
            return
        
        # Calculate order size
        order_size = self.position_size_usd / current_price
        
        # Place order based on signal
        if action == "UP":
            # Buy signal - place market buy order
            self.buy(
                connector_name=connector_name,
                trading_pair=trading_pair,
                amount=order_size,
                order_type=OrderType.MARKET
            )
            
            # Track position
            self.open_positions[symbol] = {
                "side": "BUY",
                "entry_price": current_price,
                "amount": order_size,
                "stop_loss": current_price * (1 - self.stop_loss_pct),
                "take_profit": current_price * (1 + self.take_profit_pct),
                "confidence": confidence
            }
            
            self.logger().info(
                f"ML Signal BUY: {symbol} @ {current_price:.2f} "
                f"(confidence: {confidence:.2%})"
            )
            
        elif action == "DOWN" and symbol in self.open_positions:
            # Sell signal - close position if we have one
            position = self.open_positions[symbol]
            self.sell(
                connector_name=connector_name,
                trading_pair=trading_pair,
                amount=position["amount"],
                order_type=OrderType.MARKET
            )
            
            del self.open_positions[symbol]
            
            self.logger().info(
                f"ML Signal SELL: {symbol} @ {current_price:.2f}"
            )
    
    def monitor_positions(self):
        """Monitor open positions for stop loss and take profit."""
        connector_name = list(self.markets.keys())[0]
        
        for symbol, position in list(self.open_positions.items()):
            trading_pair = f"{symbol}-USDT"
            current_price = self.connectors[connector_name].get_mid_price(trading_pair)
            
            if current_price is None:
                continue
            
            # Check stop loss
            if current_price <= position["stop_loss"]:
                self.sell(
                    connector_name=connector_name,
                    trading_pair=trading_pair,
                    amount=position["amount"],
                    order_type=OrderType.MARKET
                )
                
                loss = (current_price - position["entry_price"]) / position["entry_price"]
                self.logger().info(
                    f"Stop Loss Hit: {symbol} @ {current_price:.2f} "
                    f"(loss: {loss:.2%})"
                )
                
                del self.open_positions[symbol]
            
            # Check take profit
            elif current_price >= position["take_profit"]:
                self.sell(
                    connector_name=connector_name,
                    trading_pair=trading_pair,
                    amount=position["amount"],
                    order_type=OrderType.MARKET
                )
                
                profit = (current_price - position["entry_price"]) / position["entry_price"]
                self.logger().info(
                    f"Take Profit Hit: {symbol} @ {current_price:.2f} "
                    f"(profit: {profit:.2%})"
                )
                
                del self.open_positions[symbol]
    
    def format_status(self) -> str:
        """Return formatted status of the strategy."""
        lines = []
        lines.append("\nML Signal Strategy Status:")
        lines.append(f"Open Positions: {len(self.open_positions)}/{self.max_positions}")
        
        if self.open_positions:
            lines.append("\nPositions:")
            for symbol, pos in self.open_positions.items():
                pnl = (self.connectors[list(self.markets.keys())[0]].get_mid_price(f"{symbol}-USDT") - pos["entry_price"]) / pos["entry_price"] * 100
                lines.append(
                    f"  {symbol}: Entry ${pos['entry_price']:.2f}, "
                    f"P&L: {pnl:+.2f}%, Confidence: {pos['confidence']:.2%}"
                )
        
        return "\n".join(lines)
