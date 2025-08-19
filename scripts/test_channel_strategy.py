#!/usr/bin/env python3
"""
Test script for Channel Trading Strategy
"""

import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger
import sys
sys.path.append('.')

from src.strategies.channel.detector import ChannelDetector, Channel
from src.strategies.channel.executor import ChannelExecutor

# Configure logger
logger.add("logs/channel_strategy_test.log", rotation="10 MB")


class ChannelStrategyTest:
    def __init__(self):
        self.config = {
            'min_touches': 2,
            'lookback_periods': 100,
            'touch_tolerance': 0.002,
            'min_channel_width': 0.01,
            'max_channel_width': 0.10,
            'buy_zone': 0.25,
            'sell_zone': 0.75,
            'position_size': 100,
            'max_positions': 3,
            'min_risk_reward': 1.5
        }
        
        self.detector = ChannelDetector(self.config)
        self.executor = ChannelExecutor(self.config)
    
    def generate_channel_data(self, channel_type: str = 'HORIZONTAL') -> List[Dict]:
        """
        Generate synthetic OHLC data with a clear channel pattern
        """
        data = []
        base_price = 100
        num_bars = 120
        
        for i in range(num_bars):
            timestamp = datetime.now() - timedelta(hours=num_bars-i)
            
            if channel_type == 'HORIZONTAL':
                # Horizontal channel between 98 and 102
                center = 100
                amplitude = 2
                price = center + amplitude * np.sin(i * 0.3)
                
            elif channel_type == 'ASCENDING':
                # Ascending channel
                center = 98 + (i * 0.05)  # Upward slope
                amplitude = 2
                price = center + amplitude * np.sin(i * 0.3)
                
            elif channel_type == 'DESCENDING':
                # Descending channel
                center = 102 - (i * 0.05)  # Downward slope
                amplitude = 2
                price = center + amplitude * np.sin(i * 0.3)
            
            else:  # RANDOM
                # Random walk (no clear channel)
                price = base_price + np.random.randn() * 2
                base_price = price
            
            # Create OHLC bar
            high = price + abs(np.random.randn() * 0.3)
            low = price - abs(np.random.randn() * 0.3)
            open_price = price + np.random.randn() * 0.1
            close = price + np.random.randn() * 0.1
            
            data.append({
                'timestamp': timestamp.isoformat(),
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': 1000000 * (1 + np.random.rand())
            })
        
        return list(reversed(data))  # Most recent first
    
    def test_channel_detection(self):
        """Test channel detection on different patterns"""
        logger.info("="*60)
        logger.info("Testing Channel Detection")
        logger.info("="*60)
        
        test_cases = ['HORIZONTAL', 'ASCENDING', 'DESCENDING', 'RANDOM']
        
        for channel_type in test_cases:
            logger.info(f"\nTesting {channel_type} pattern...")
            
            # Generate test data
            ohlc_data = self.generate_channel_data(channel_type)
            
            # Detect channel
            channel = self.detector.detect_channel('TEST', ohlc_data)
            
            if channel:
                logger.info(f"✅ Channel detected!")
                logger.info(f"  Type: {channel.channel_type}")
                logger.info(f"  Width: {channel.width:.2%}")
                logger.info(f"  Strength: {channel.strength:.2f}")
                logger.info(f"  Upper: ${channel.upper_line:.2f}")
                logger.info(f"  Lower: ${channel.lower_line:.2f}")
                logger.info(f"  Touches: {channel.touches_upper} upper, {channel.touches_lower} lower")
                logger.info(f"  Current position: {channel.current_position:.2f}")
                logger.info(f"  Valid: {channel.is_valid}")
                
                # Get trading signal
                signal = self.detector.get_trading_signal(channel)
                if signal:
                    logger.info(f"  Signal: {signal}")
                    
                    # Calculate targets
                    current_price = ohlc_data[0]['close']
                    targets = self.detector.calculate_targets(channel, current_price, signal)
                    logger.info(f"  Targets: TP=${targets['take_profit']:.2f} "
                               f"({targets['take_profit_pct']:.1f}%), "
                               f"SL=${targets['stop_loss']:.2f} "
                               f"({targets['stop_loss_pct']:.1f}%), "
                               f"R:R={targets['risk_reward']:.2f}")
            else:
                if channel_type == 'RANDOM':
                    logger.info("✅ Correctly did not detect channel in random data")
                else:
                    logger.warning(f"❌ Failed to detect {channel_type} channel")
    
    async def test_execution(self):
        """Test channel execution with multiple symbols"""
        logger.info("\n" + "="*60)
        logger.info("Testing Channel Execution")
        logger.info("="*60)
        
        # Create market data with different channel patterns
        market_data = {
            'BTC': self.generate_channel_data('HORIZONTAL'),
            'ETH': self.generate_channel_data('ASCENDING'),
            'SOL': self.generate_channel_data('DESCENDING'),
            'ADA': self.generate_channel_data('RANDOM')
        }
        
        # Scan and execute
        logger.info("\n📊 Scanning for channel opportunities...")
        signals = await self.executor.scan_and_execute(market_data)
        
        logger.info(f"Found {len(signals)} trading signals:")
        for signal in signals:
            logger.info(f"  {signal['symbol']}: {signal['signal']} in {signal['channel_type']} channel")
            logger.info(f"    Channel width: {signal['channel_width']:.2%}")
            logger.info(f"    Channel strength: {signal['channel_strength']:.2f}")
            logger.info(f"    Position in channel: {signal['position_in_channel']:.2f}")
            logger.info(f"    R:R ratio: {signal['risk_reward']:.2f}")
        
        # Show active positions
        positions = self.executor.get_active_positions()
        logger.info(f"\n📈 Active positions: {len(positions)}")
        for pos in positions:
            logger.info(f"  {pos['symbol']}: {pos['side']} @ ${pos['entry_price']:.2f}")
            logger.info(f"    Channel type: {pos['channel_type']}")
            logger.info(f"    TP: ${pos['take_profit']:.2f}, SL: ${pos['stop_loss']:.2f}")
        
        # Simulate price movement and monitor positions
        logger.info("\n⏰ Simulating price movements...")
        
        # Move prices to trigger exits
        for symbol in market_data:
            if symbol in ['BTC', 'ETH']:  # Move these to take profit
                for bar in market_data[symbol][:5]:  # Modify first 5 bars
                    bar['close'] *= 1.05  # 5% increase
                    bar['high'] *= 1.05
        
        # Monitor positions
        closed = await self.executor.monitor_positions(market_data)
        
        if closed:
            logger.info(f"\n💰 Closed {len(closed)} positions:")
            for pos in closed:
                logger.info(f"  {pos['symbol']}: Exit @ ${pos['exit_price']:.2f}")
                logger.info(f"    P&L: ${pos['pnl']:.2f}")
                logger.info(f"    Exit reason: {pos['exit_reason']}")
                logger.info(f"    Hold time: {pos['hold_time']:.1f} hours")
        
        # Performance stats
        stats = self.executor.get_performance_stats()
        logger.info("\n📊 Performance Statistics:")
        logger.info(f"  Total trades: {stats['total_trades']}")
        logger.info(f"  Win rate: {stats['win_rate']:.1%}")
        logger.info(f"  Total P&L: ${stats['total_pnl']:.2f}")
        if 'profit_factor' in stats:
            logger.info(f"  Profit factor: {stats['profit_factor']:.2f}")
    
    def test_edge_cases(self):
        """Test edge cases and error handling"""
        logger.info("\n" + "="*60)
        logger.info("Testing Edge Cases")
        logger.info("="*60)
        
        # Test 1: Insufficient data
        logger.info("\nTest 1: Insufficient data")
        short_data = self.generate_channel_data('HORIZONTAL')[:50]
        channel = self.detector.detect_channel('TEST', short_data)
        if channel is None:
            logger.info("✅ Correctly handled insufficient data")
        else:
            logger.warning("❌ Should not detect channel with insufficient data")
        
        # Test 2: Very narrow channel
        logger.info("\nTest 2: Very narrow channel")
        narrow_data = []
        for i in range(100):
            price = 100 + np.random.randn() * 0.1  # Very small variation
            narrow_data.append({
                'timestamp': (datetime.now() - timedelta(hours=100-i)).isoformat(),
                'open': price,
                'high': price + 0.05,
                'low': price - 0.05,
                'close': price,
                'volume': 1000000
            })
        channel = self.detector.detect_channel('TEST', list(reversed(narrow_data)))
        if channel and not channel.is_valid:
            logger.info("✅ Correctly identified invalid narrow channel")
        
        # Test 3: Channel breakout
        logger.info("\nTest 3: Channel with breakout")
        breakout_data = self.generate_channel_data('HORIZONTAL')
        # Add breakout in recent bars
        for bar in breakout_data[:10]:
            bar['close'] *= 1.1  # 10% breakout
            bar['high'] *= 1.1
        channel = self.detector.detect_channel('TEST', breakout_data)
        if channel:
            logger.info(f"Channel detected despite breakout")
            logger.info(f"  Current position: {channel.current_position:.2f}")
            signal = self.detector.get_trading_signal(channel)
            if signal is None:
                logger.info("✅ Correctly no signal when price outside trading zones")
    
    async def run_all_tests(self):
        """Run all tests"""
        logger.info("Starting Channel Strategy Tests")
        logger.info("="*80)
        
        # Test detection
        self.test_channel_detection()
        
        # Test execution
        await self.test_execution()
        
        # Test edge cases
        self.test_edge_cases()
        
        logger.info("\n" + "="*80)
        logger.info("✅ All Channel Strategy Tests Complete!")


async def main():
    test = ChannelStrategyTest()
    await test.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
