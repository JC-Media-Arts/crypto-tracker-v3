#!/usr/bin/env python3
"""
Main Paper Trading System
Connects simplified strategies to paper trading execution
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger
import signal

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.strategies.manager import StrategyManager
from src.data.hybrid_fetcher import HybridDataFetcher
from src.trading.simple_paper_trader import SimplePaperTrader
from src.config.settings import Settings
from src.data.supabase_client import SupabaseClient

class PaperTradingSystem:
    """Main paper trading system orchestrator"""
    
    def __init__(self):
        self.settings = Settings()
        
        # Initialize components
        self.data_fetcher = HybridDataFetcher()
        self.paper_trader = SimplePaperTrader(initial_balance=1000.0)  # Start with $1000
        
        # Strategy config for simplified mode
        strategy_config = {
            "ml_enabled": False,
            "shadow_enabled": False,
            "base_position_usd": 50.0,  # $50 per position
            "max_open_positions": 10,
            "dca_drop_threshold": -1.0,  # Aggressive for testing
            "swing_breakout_threshold": 0.3,
            "channel_position_threshold": 0.35
        }
        
        self.strategy_manager = StrategyManager(strategy_config, self.settings)
        
        # Trading parameters
        self.min_confidence = 0.0  # Accept all signals in test mode
        self.scan_interval = 60  # Scan every minute
        self.position_size = 50.0  # $50 per trade
        
        # Risk management
        self.stop_loss_pct = 0.05  # 5% stop loss
        self.take_profit_pct = 0.10  # 10% take profit
        
        # Track active positions
        self.active_positions = {}
        
        # Shutdown flag
        self.shutdown = False
        
        logger.info("=" * 80)
        logger.info("📊 PAPER TRADING SYSTEM INITIALIZED")
        logger.info(f"   Balance: ${self.paper_trader.balance:.2f}")
        logger.info(f"   Position Size: ${self.position_size}")
        logger.info(f"   Stop Loss: {self.stop_loss_pct*100:.1f}%")
        logger.info(f"   Take Profit: {self.take_profit_pct*100:.1f}%")
        logger.info("=" * 80)
    
    def get_symbols(self) -> List[str]:
        """Get symbols to monitor"""
        # Full list of 90 symbols we're tracking
        return [
            # Major coins
            "BTC", "ETH", "SOL", "XRP", "ADA", "AVAX", "DOGE", "DOT", "LINK", "MATIC",
            "UNI", "LTC", "BCH", "ATOM", "ETC", "XLM", "FIL", "ICP", "NEAR", "VET",
            "ALGO", "FTM", "HBAR", "MANA", "SAND", "AXS", "THETA", "EGLD", "XTZ", "EOS",
            "AAVE", "MKR", "CRV", "LDO", "SNX", "COMP", "GRT", "ENJ", "CHZ", "BAT",
            "DASH", "ZEC", "KSM", "RUNE", "SUSHI", "YFI", "UMA", "ZRX", "QTUM", "OMG",
            "WAVES", "BAL", "KNC", "REN", "ANKR", "STORJ", "OCEAN", "BAND", "NMR", "SRM",
            # Newer/Trending coins
            "APT", "ARB", "OP", "INJ", "TIA", "SEI", "SUI", "BLUR", "FET", "RNDR",
            "WLD", "ARKM", "PENDLE", "JUP", "PYTH", "STRK", "MANTA", "ALT", "PIXEL", "DYM",
            # Meme coins
            "SHIB", "PEPE", "FLOKI", "BONK", "WIF", "MEME", "MYRO", "PONKE", "POPCAT", "TRUMP"
        ]
    
    async def fetch_market_data(self) -> Dict:
        """Fetch recent market data for all symbols"""
        market_data = {}
        symbols = self.get_symbols()
        
        # Fetch data in parallel for better performance
        tasks = []
        for symbol in symbols:
            task = self.data_fetcher.get_recent_data(
                symbol=symbol,
                hours=24,  # Last 24 hours for better signal detection
                timeframe="15m"
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.debug(f"Failed to fetch {symbol}: {result}")
                continue
            # Check if result is a DataFrame (has 'empty' attribute)
            if result is not None:
                if hasattr(result, 'empty'):
                    if not result.empty:
                        market_data[symbol] = result
                elif isinstance(result, list) and len(result) > 0:
                    # If it's a list, we still add it
                    market_data[symbol] = result
        
        logger.info(f"Fetched data for {len(market_data)} symbols")
        return market_data
    
    async def get_current_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Get current prices for symbols"""
        prices = {}
        
        for symbol in symbols:
            try:
                data = await self.data_fetcher.get_recent_data(
                    symbol=symbol,
                    hours=1,
                    timeframe="15m"
                )
                if data is not None:
                    if hasattr(data, 'empty') and not data.empty:
                        prices[symbol] = float(data.iloc[-1]['close'])
                    elif isinstance(data, list) and len(data) > 0:
                        # If it's a list of records, get the last one
                        prices[symbol] = float(data[-1]['close'])
            except Exception as e:
                logger.debug(f"Failed to get price for {symbol}: {e}")
        
        return prices
    
    async def execute_signal(self, signal) -> None:
        """Execute a trading signal"""
        try:
            symbol = signal.symbol
            
            # Skip if we already have a position
            if symbol in self.paper_trader.positions:
                logger.debug(f"Already have position in {symbol}, skipping")
                return
            
            # Get current price
            prices = await self.get_current_prices([symbol])
            if symbol not in prices:
                logger.warning(f"Could not get price for {symbol}")
                return
            
            current_price = prices[symbol]
            
            # Open position
            result = await self.paper_trader.open_position(
                symbol=symbol,
                usd_amount=self.position_size,
                market_price=current_price,
                strategy=signal.strategy_type.value,  # Convert enum to string
                stop_loss_pct=self.stop_loss_pct,
                take_profit_pct=self.take_profit_pct
            )
            
            if result["success"]:
                self.active_positions[symbol] = {
                    "signal": signal,
                    "entry_time": datetime.now()
                }
                
        except Exception as e:
            logger.error(f"Error executing signal for {signal.symbol}: {e}")
    
    async def check_exit_conditions(self) -> None:
        """Check if any positions should be closed"""
        if not self.paper_trader.positions:
            return
        
        # Get current prices for all positions
        symbols = list(self.paper_trader.positions.keys())
        prices = await self.get_current_prices(symbols)
        
        # Check stop loss and take profit
        await self.paper_trader.check_stop_loss_take_profit(prices)
        
        # Check strategy exit signals
        for symbol in list(self.paper_trader.positions.keys()):
            if symbol not in prices:
                continue
                
            position = self.paper_trader.positions.get(symbol)
            if not position:
                continue
            
            # Simple time-based exit after 4 hours
            if datetime.now() - position.entry_time > timedelta(hours=4):
                logger.info(f"⏰ Time-based exit for {symbol}")
                await self.paper_trader.close_position(symbol, prices[symbol], "time_exit")
    
    async def run_trading_loop(self) -> None:
        """Main trading loop"""
        logger.info("🚀 Starting paper trading loop...")
        
        while not self.shutdown:
            try:
                # Fetch market data
                market_data = await self.fetch_market_data()
                
                if not market_data:
                    logger.warning("No market data available, skipping scan")
                    await asyncio.sleep(self.scan_interval)
                    continue
                
                # Scan for opportunities
                signals = await self.strategy_manager.scan_for_opportunities(market_data)
                
                # Get portfolio stats
                stats = self.paper_trader.get_portfolio_stats()
                
                logger.info(f"Scan complete: {len(signals)} signals, {stats['positions']} positions")
                logger.info(f"Portfolio: ${stats['total_value']:.2f} ({stats['total_pnl_percent']:+.2f}%)")
                
                # Execute new signals
                for signal in signals:
                    await self.execute_signal(signal)
                
                # Check exit conditions
                await self.check_exit_conditions()
                
                # Display current positions
                if self.paper_trader.positions:
                    logger.info("Current positions:")
                    prices = await self.get_current_prices(list(self.paper_trader.positions.keys()))
                    
                    for symbol, position in self.paper_trader.positions.items():
                        current_price = prices.get(symbol, position.entry_price)
                        pnl = (current_price - position.entry_price) / position.entry_price * 100
                        emoji = "🟢" if pnl > 0 else "🔴"
                        logger.info(f"  {emoji} {symbol}: Entry ${position.entry_price:.4f} → ${current_price:.4f} ({pnl:+.2f}%)")
                
                # Display stats every 5 scans
                if self.paper_trader.total_trades > 0 and self.paper_trader.total_trades % 5 == 0:
                    logger.info("=" * 60)
                    logger.info("📈 TRADING STATISTICS:")
                    logger.info(f"   Total Trades: {stats['total_trades']}")
                    logger.info(f"   Win Rate: {stats['win_rate']:.1f}%")
                    logger.info(f"   Total P&L: ${stats['total_pnl']:.2f}")
                    logger.info(f"   Total Fees: ${stats['total_fees']:.2f}")
                    logger.info(f"   Total Slippage: ${stats['total_slippage']:.2f}")
                    logger.info("=" * 60)
                
                # Wait for next scan
                await asyncio.sleep(self.scan_interval)
                
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                await asyncio.sleep(self.scan_interval)
    
    def handle_shutdown(self, signum, frame):
        """Handle shutdown signal"""
        logger.info("\n🛑 Shutdown signal received...")
        self.shutdown = True
        
        # Display final stats
        stats = self.paper_trader.get_portfolio_stats()
        logger.info("=" * 80)
        logger.info("📊 FINAL TRADING STATISTICS:")
        logger.info(f"   Initial Balance: ${stats['initial_balance']:.2f}")
        logger.info(f"   Final Balance: ${stats['total_value']:.2f}")
        logger.info(f"   Total P&L: ${stats['total_pnl']:.2f} ({stats['total_pnl_percent']:+.2f}%)")
        logger.info(f"   Total Trades: {stats['total_trades']}")
        logger.info(f"   Win Rate: {stats['win_rate']:.1f}%")
        logger.info(f"   Total Fees Paid: ${stats['total_fees']:.2f}")
        logger.info(f"   Total Slippage Cost: ${stats['total_slippage']:.2f}")
        if stats['profit_factor'] > 0:
            logger.info(f"   Profit Factor: {stats['profit_factor']:.2f}")
        logger.info("=" * 80)
        
        sys.exit(0)
    
    async def run(self):
        """Main entry point"""
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        
        try:
            await self.run_trading_loop()
        except KeyboardInterrupt:
            self.handle_shutdown(None, None)

async def main():
    """Main function"""
    system = PaperTradingSystem()
    await system.run()

if __name__ == "__main__":
    # Configure logging
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # Run the system
    asyncio.run(main())
