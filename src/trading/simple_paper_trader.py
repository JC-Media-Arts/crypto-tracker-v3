"""
Simple Paper Trading System with Realistic Kraken Fees and Slippage
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from loguru import logger
import asyncio
from pathlib import Path


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
    fees_paid: float = 0.0


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


class SimplePaperTrader:
    """
    Paper trading system with realistic fee and slippage simulation

    Kraken Fees (Maker/Taker):
    - < $50k volume: 0.16% / 0.26%
    - $50k-$100k: 0.14% / 0.24%
    - We'll use taker fees (0.26%) as we're doing market orders

    Slippage:
    - Major pairs (BTC, ETH): 0.05-0.1%
    - Mid-cap: 0.1-0.2%
    - Small-cap/Meme: 0.2-0.5%
    """

    def __init__(self, initial_balance: float = 10000.0):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.pending_orders: Dict[str, dict] = {}

        # Kraken taker fee
        self.base_fee_rate = 0.0026  # 0.26%

        # Slippage rates by market cap
        self.slippage_rates = {
            "major": 0.0008,  # 0.08% for BTC, ETH, SOL, etc.
            "mid": 0.0015,  # 0.15% for mid-caps
            "small": 0.0035,  # 0.35% for small/meme coins
        }

        # Define coin categories
        self.major_coins = [
            "BTC",
            "ETH",
            "SOL",
            "XRP",
            "ADA",
            "AVAX",
            "DOGE",
            "DOT",
            "LINK",
            "MATIC",
        ]
        self.meme_coins = [
            "SHIB",
            "PEPE",
            "FLOKI",
            "BONK",
            "WIF",
            "MEME",
            "MYRO",
            "PONKE",
            "POPCAT",
            "TRUMP",
        ]

        # Stats tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.total_fees = 0.0
        self.total_slippage = 0.0

        # Persistence
        self.state_file = Path("data/paper_trading_state.json")
        self.trades_file = Path("data/paper_trading_trades.json")
        self.load_state()

    def get_slippage_rate(self, symbol: str) -> float:
        """Get slippage rate based on coin type"""
        if symbol in self.major_coins:
            return self.slippage_rates["major"]
        elif symbol in self.meme_coins:
            return self.slippage_rates["small"]
        else:
            return self.slippage_rates["mid"]

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

    async def open_position(
        self,
        symbol: str,
        usd_amount: float,
        market_price: float,
        strategy: str,
        stop_loss_pct: Optional[float] = None,
        take_profit_pct: Optional[float] = None,
    ) -> Dict:
        """
        Open a new position with realistic fees and slippage
        """
        # Check if we already have a position
        if symbol in self.positions:
            logger.warning(f"Position already exists for {symbol}")
            return {"success": False, "error": "Position already exists"}

        # Check balance
        if usd_amount > self.balance * 0.5:  # Max 50% of balance per trade
            logger.warning(
                f"Position size ${usd_amount} too large for balance ${self.balance}"
            )
            return {"success": False, "error": "Insufficient balance"}

        # Calculate actual entry price with slippage
        actual_price, slippage_cost = self.calculate_entry_price(
            symbol, market_price, is_buy=True
        )

        # Calculate fees
        fees = self.calculate_fees(usd_amount)

        # Total cost including fees
        total_cost = usd_amount + fees

        # Check if we have enough balance
        if total_cost > self.balance:
            logger.warning(
                f"Insufficient balance: need ${total_cost:.2f}, have ${self.balance:.2f}"
            )
            return {"success": False, "error": "Insufficient balance after fees"}

        # Calculate amount of crypto we get
        crypto_amount = usd_amount / actual_price

        # Create position
        position = Position(
            symbol=symbol,
            entry_price=actual_price,
            amount=crypto_amount,
            usd_value=usd_amount,
            entry_time=datetime.now(),
            strategy=strategy,
            stop_loss=actual_price * (1 - stop_loss_pct) if stop_loss_pct else None,
            take_profit=actual_price * (1 + take_profit_pct)
            if take_profit_pct
            else None,
            fees_paid=fees,
        )

        # Update state
        self.positions[symbol] = position
        self.balance -= total_cost
        self.total_fees += fees
        self.total_slippage += slippage_cost

        # Save state
        self.save_state()

        logger.info(f"📈 Opened {strategy} position: {symbol}")
        logger.info(f"   Market Price: ${market_price:.4f}")
        logger.info(
            f"   Actual Price: ${actual_price:.4f} (slippage: ${slippage_cost:.2f})"
        )
        logger.info(f"   Amount: {crypto_amount:.6f} {symbol}")
        logger.info(f"   Value: ${usd_amount:.2f}")
        logger.info(f"   Fees: ${fees:.2f}")
        logger.info(f"   Balance: ${self.balance:.2f}")

        return {
            "success": True,
            "position": position,
            "actual_price": actual_price,
            "fees": fees,
            "slippage": slippage_cost,
        }

    async def close_position(
        self, symbol: str, market_price: float, reason: str = "signal"
    ) -> Dict:
        """
        Close a position with realistic fees and slippage
        """
        if symbol not in self.positions:
            logger.warning(f"No position found for {symbol}")
            return {"success": False, "error": "No position found"}

        position = self.positions[symbol]

        # Calculate actual exit price with slippage
        actual_price, slippage_cost = self.calculate_entry_price(
            symbol, market_price, is_buy=False
        )

        # Calculate proceeds
        gross_proceeds = position.amount * actual_price

        # Calculate fees
        fees = self.calculate_fees(gross_proceeds)

        # Net proceeds
        net_proceeds = gross_proceeds - fees

        # Calculate P&L
        pnl_usd = net_proceeds - position.usd_value - position.fees_paid
        pnl_percent = (pnl_usd / position.usd_value) * 100

        # Create trade record
        trade = Trade(
            symbol=symbol,
            entry_price=position.entry_price,
            exit_price=actual_price,
            amount=position.amount,
            entry_time=position.entry_time,
            exit_time=datetime.now(),
            pnl_usd=pnl_usd,
            pnl_percent=pnl_percent,
            fees_paid=position.fees_paid + fees,
            strategy=position.strategy,
            trade_type="win" if pnl_usd > 0 else "loss",
        )

        # Update state
        self.trades.append(trade)
        self.balance += net_proceeds
        self.total_trades += 1
        if pnl_usd > 0:
            self.winning_trades += 1
        self.total_fees += fees
        self.total_slippage += slippage_cost

        # Remove position
        del self.positions[symbol]

        # Save state
        self.save_state()
        self.save_trade(trade)

        # Log results
        emoji = "🟢" if pnl_usd > 0 else "🔴"
        logger.info(f"{emoji} Closed {position.strategy} position: {symbol}")
        logger.info(
            f"   Entry: ${position.entry_price:.4f} → Exit: ${actual_price:.4f}"
        )
        logger.info(
            f"   Market Exit: ${market_price:.4f} (slippage: ${slippage_cost:.2f})"
        )
        logger.info(f"   P&L: ${pnl_usd:.2f} ({pnl_percent:+.2f}%)")
        logger.info(f"   Total Fees: ${position.fees_paid + fees:.2f}")
        logger.info(f"   Balance: ${self.balance:.2f}")

        return {
            "success": True,
            "trade": trade,
            "pnl_usd": pnl_usd,
            "pnl_percent": pnl_percent,
            "fees": fees,
            "slippage": slippage_cost,
        }

    async def check_stop_loss_take_profit(self, market_prices: Dict[str, float]):
        """Check if any positions hit stop loss or take profit"""
        positions_to_close = []

        for symbol, position in self.positions.items():
            if symbol not in market_prices:
                continue

            current_price = market_prices[symbol]

            # Check stop loss
            if position.stop_loss and current_price <= position.stop_loss:
                logger.warning(
                    f"⛔ Stop loss triggered for {symbol} at ${current_price:.4f}"
                )
                positions_to_close.append((symbol, current_price, "stop_loss"))

            # Check take profit
            elif position.take_profit and current_price >= position.take_profit:
                logger.info(
                    f"🎯 Take profit triggered for {symbol} at ${current_price:.4f}"
                )
                positions_to_close.append((symbol, current_price, "take_profit"))

        # Close triggered positions
        for symbol, price, reason in positions_to_close:
            await self.close_position(symbol, price, reason)

    def get_portfolio_stats(self) -> Dict:
        """Get current portfolio statistics"""
        total_position_value = sum(p.usd_value for p in self.positions.values())
        total_value = self.balance + total_position_value

        win_rate = (
            (self.winning_trades / self.total_trades * 100)
            if self.total_trades > 0
            else 0
        )

        total_pnl = sum(t.pnl_usd for t in self.trades)
        avg_win = sum(t.pnl_usd for t in self.trades if t.pnl_usd > 0) / max(
            1, self.winning_trades
        )
        avg_loss = sum(t.pnl_usd for t in self.trades if t.pnl_usd < 0) / max(
            1, (self.total_trades - self.winning_trades)
        )

        return {
            "balance": self.balance,
            "positions": len(self.positions),
            "position_value": total_position_value,
            "total_value": total_value,
            "initial_balance": self.initial_balance,
            "total_pnl": total_value - self.initial_balance,
            "total_pnl_percent": (
                (total_value - self.initial_balance) / self.initial_balance * 100
            ),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "win_rate": win_rate,
            "total_fees": self.total_fees,
            "total_slippage": self.total_slippage,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": abs(avg_win / avg_loss) if avg_loss != 0 else 0,
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

        self.state_file.parent.mkdir(exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2)

    def save_trade(self, trade: Trade):
        """Save trade to history file"""
        self.trades_file.parent.mkdir(exist_ok=True)

        trade_dict = {
            "symbol": trade.symbol,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "amount": trade.amount,
            "entry_time": trade.entry_time.isoformat(),
            "exit_time": trade.exit_time.isoformat(),
            "pnl_usd": trade.pnl_usd,
            "pnl_percent": trade.pnl_percent,
            "fees_paid": trade.fees_paid,
            "strategy": trade.strategy,
            "trade_type": trade.trade_type,
        }

        # Append to file
        trades = []
        if self.trades_file.exists():
            with open(self.trades_file, "r") as f:
                trades = json.load(f)

        trades.append(trade_dict)

        with open(self.trades_file, "w") as f:
            json.dump(trades, f, indent=2)

    def load_state(self):
        """Load state from file if exists"""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    state = json.load(f)

                self.balance = state["balance"]
                self.initial_balance = state["initial_balance"]

                # Load positions
                for symbol, p_data in state["positions"].items():
                    self.positions[symbol] = Position(
                        symbol=symbol,
                        entry_price=p_data["entry_price"],
                        amount=p_data["amount"],
                        usd_value=p_data["usd_value"],
                        entry_time=datetime.fromisoformat(p_data["entry_time"]),
                        strategy=p_data["strategy"],
                        stop_loss=p_data.get("stop_loss"),
                        take_profit=p_data.get("take_profit"),
                        fees_paid=p_data.get("fees_paid", 0),
                    )

                # Load stats
                stats = state.get("stats", {})
                self.total_trades = stats.get("total_trades", 0)
                self.winning_trades = stats.get("winning_trades", 0)
                self.total_fees = stats.get("total_fees", 0)
                self.total_slippage = stats.get("total_slippage", 0)

                logger.info(
                    f"📂 Loaded paper trading state: Balance ${self.balance:.2f}, {len(self.positions)} positions"
                )
            except Exception as e:
                logger.error(f"Failed to load state: {e}")

    def reset(self):
        """Reset paper trading account"""
        self.balance = self.initial_balance
        self.positions = {}
        self.trades = []
        self.total_trades = 0
        self.winning_trades = 0
        self.total_fees = 0
        self.total_slippage = 0

        # Clear files
        if self.state_file.exists():
            self.state_file.unlink()
        if self.trades_file.exists():
            self.trades_file.unlink()

        self.save_state()
        logger.info("🔄 Paper trading account reset")
