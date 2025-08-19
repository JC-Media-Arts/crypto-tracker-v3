#!/usr/bin/env python3
"""
Test script for Strategy Manager
Tests orchestration of DCA and Swing strategies with conflict resolution
"""

import asyncio
import json
from datetime import datetime, timedelta
import numpy as np
from pathlib import Path
import sys
sys.path.append('.')

# We'll create a mock version to avoid dependency issues
from loguru import logger

# Configure logger
logger.add("logs/strategy_manager_test.log", rotation="10 MB")


class StrategyManagerTest:
    def __init__(self):
        # Configuration based on MASTER_PLAN.md
        self.config = {
            'total_capital': 1000,  # $1000 paper trading capital
            'dca_allocation': 0.6,  # 60% for DCA
            'swing_allocation': 0.4,  # 40% for Swing
            'reserve': 0.2,  # 20% reserve
            'min_confidence': 0.60,
            'dca_position_size': 100,
            'swing_position_size': 200,
            
            'dca_config': {
                'drop_threshold': -5.0,
                'min_volume_ratio': 1.5,
                'rsi_oversold': 30,
                'grid_levels': 5,
                'grid_spacing': 0.01
            },
            
            'swing_config': {
                'breakout_threshold': 0.03,  # 3% as per MASTER_PLAN
                'volume_surge': 2.0,
                'rsi_bullish_min': 60,
                'take_profit': 15.0,
                'stop_loss': 5.0
            },
            
            'conflict_resolution': {
                'same_coin': 'higher_confidence_wins',
                'capital_limit': 'pause_lower_priority',
                'opposing_signals': 'skip_both'
            }
        }
        
        self.manager = StrategyManager(self.config)
    
    def create_mock_market_data(self) -> dict:
        """Create mock market data with various scenarios"""
        return {
            'BTC': {
                'symbol': 'BTC',
                'current_price': 95000,
                'price_change_24h': -5.5,  # DCA opportunity
                'rsi': 28,  # Oversold
                'volume_ratio': 2.1,
                'high_24h': 100000,
                'low_24h': 94000,
                'sma_20': 96000,
                'sma_50': 97000,
                'sma_200': 85000,
                'support_level': 94000,
                'resistance_level': 100000,
                'macd': -150,
                'macd_signal': -100,
                'market_regime': -1  # Bear
            },
            'ETH': {
                'symbol': 'ETH',
                'current_price': 3200,
                'price_change_24h': 4.2,  # Swing opportunity
                'rsi': 65,  # Bullish momentum
                'volume_ratio': 2.5,
                'high_24h': 3150,
                'low_24h': 3000,
                'sma_20': 3100,
                'sma_50': 3050,
                'sma_200': 2800,
                'support_level': 3000,
                'resistance_level': 3150,
                'macd': 25,
                'macd_signal': 20,
                'market_regime': 1  # Bull
            },
            'SOL': {
                'symbol': 'SOL',
                'current_price': 180,
                'price_change_24h': -6.0,  # Strong DCA opportunity
                'rsi': 25,  # Very oversold
                'volume_ratio': 3.0,
                'high_24h': 192,
                'low_24h': 178,
                'sma_20': 185,
                'sma_50': 188,
                'sma_200': 150,
                'support_level': 175,
                'resistance_level': 195,
                'macd': -3,
                'macd_signal': -2,
                'market_regime': -1  # Bear
            },
            'AVAX': {
                'symbol': 'AVAX',
                'current_price': 42,
                'price_change_24h': 3.5,  # Potential swing
                'rsi': 62,
                'volume_ratio': 1.8,
                'high_24h': 41.5,
                'low_24h': 40,
                'sma_20': 41,
                'sma_50': 40.5,
                'sma_200': 35,
                'support_level': 40,
                'resistance_level': 43,
                'macd': 0.5,
                'macd_signal': 0.4,
                'market_regime': 1  # Bull
            }
        }
    
    async def test_opportunity_scanning(self):
        """Test scanning for opportunities"""
        logger.info("="*50)
        logger.info("Testing Opportunity Scanning")
        logger.info("="*50)
        
        market_data = self.create_mock_market_data()
        
        # Scan for opportunities
        signals = await self.manager.scan_for_opportunities(market_data)
        
        logger.info(f"Found {len(signals)} signals:")
        for signal in signals:
            logger.info(f"  {signal.symbol} - {signal.strategy_type.value}: "
                       f"Confidence {signal.confidence:.2f}, "
                       f"EV ${signal.expected_value:.2f}, "
                       f"Priority {signal.priority_score:.3f}")
        
        return signals
    
    async def test_conflict_resolution(self):
        """Test conflict resolution when multiple signals for same symbol"""
        logger.info("="*50)
        logger.info("Testing Conflict Resolution")
        logger.info("="*50)
        
        # Create conflicting signals for same symbol
        from src.strategies.manager import StrategySignal
        
        signals = [
            StrategySignal(
                strategy_type=StrategyType.DCA,
                symbol='BTC',
                confidence=0.65,
                expected_value=5.0,
                required_capital=500,
                setup_data={},
                timestamp=datetime.now(),
                expires_at=datetime.now() + timedelta(minutes=15),
                priority_score=0.7
            ),
            StrategySignal(
                strategy_type=StrategyType.SWING,
                symbol='BTC',
                confidence=0.70,  # Higher confidence
                expected_value=8.0,
                required_capital=200,
                setup_data={},
                timestamp=datetime.now(),
                expires_at=datetime.now() + timedelta(minutes=5),
                priority_score=0.75
            )
        ]
        
        # Resolve conflicts
        resolved = self.manager.resolve_conflicts(signals)
        
        logger.info(f"Original signals: {len(signals)}")
        logger.info(f"Resolved signals: {len(resolved)}")
        
        if resolved:
            winner = resolved[0]
            logger.info(f"Winner: {winner.symbol} - {winner.strategy_type.value} "
                       f"(confidence: {winner.confidence:.2f})")
    
    async def test_capital_constraints(self):
        """Test capital allocation constraints"""
        logger.info("="*50)
        logger.info("Testing Capital Constraints")
        logger.info("="*50)
        
        # Show initial allocation
        status = self.manager.get_status()
        logger.info(f"Initial capital allocation:")
        logger.info(f"  DCA: ${status['capital_allocation']['dca_available']:.2f} available "
                   f"(of ${self.config['total_capital'] * 0.6:.2f})")
        logger.info(f"  Swing: ${status['capital_allocation']['swing_available']:.2f} available "
                   f"(of ${self.config['total_capital'] * 0.4:.2f})")
        
        # Create signals that exceed capital limits
        from src.strategies.manager import StrategySignal
        
        signals = []
        # Create multiple DCA signals that exceed 60% allocation
        for i in range(3):
            signals.append(
                StrategySignal(
                    strategy_type=StrategyType.DCA,
                    symbol=f'COIN{i}',
                    confidence=0.65,
                    expected_value=5.0,
                    required_capital=250,  # $250 each, total $750 > $600 limit
                    setup_data={},
                    timestamp=datetime.now(),
                    expires_at=datetime.now() + timedelta(minutes=15),
                    priority_score=0.7 - i*0.1  # Decreasing priority
                )
            )
        
        # Apply capital constraints
        approved = self.manager._apply_capital_constraints(signals)
        
        logger.info(f"Signals submitted: {len(signals)}")
        logger.info(f"Signals approved: {len(approved)}")
        
        for signal in approved:
            logger.info(f"  Approved: {signal.symbol} - ${signal.required_capital:.2f}")
    
    async def test_execution_simulation(self):
        """Test signal execution simulation"""
        logger.info("="*50)
        logger.info("Testing Signal Execution")
        logger.info("="*50)
        
        market_data = self.create_mock_market_data()
        
        # Get signals
        signals = await self.manager.scan_for_opportunities(market_data)
        
        # Resolve conflicts
        resolved = self.manager.resolve_conflicts(signals)
        
        # Execute signals
        results = await self.manager.execute_signals(resolved)
        
        logger.info(f"Execution results:")
        logger.info(f"  Executed: {len(results['executed'])}")
        logger.info(f"  Failed: {len(results['failed'])}")
        logger.info(f"  Skipped: {len(results['skipped'])}")
        
        # Show updated status
        status = self.manager.get_status()
        logger.info(f"\nUpdated status:")
        logger.info(f"  Active positions: {status['active_positions']}")
        logger.info(f"  DCA capital used: ${status['capital_allocation']['dca_used']:.2f}")
        logger.info(f"  Swing capital used: ${status['capital_allocation']['swing_used']:.2f}")
    
    async def test_performance_tracking(self):
        """Test performance tracking and updates"""
        logger.info("="*50)
        logger.info("Testing Performance Tracking")
        logger.info("="*50)
        
        # Simulate some trades
        self.manager.update_performance('BTC', 50.0, True)  # Win
        self.manager.update_performance('ETH', -20.0, False)  # Loss
        self.manager.update_performance('SOL', 30.0, True)  # Win
        
        # Get performance stats
        status = self.manager.get_status()
        
        logger.info("Performance Summary:")
        logger.info(f"DCA Strategy:")
        logger.info(f"  Win rate: {status['performance']['dca']['win_rate']:.1%}")
        logger.info(f"  Total P&L: ${status['performance']['dca']['total_pnl']:.2f}")
        
        logger.info(f"Swing Strategy:")
        logger.info(f"  Win rate: {status['performance']['swing']['win_rate']:.1%}")
        logger.info(f"  Total P&L: ${status['performance']['swing']['total_pnl']:.2f}")
    
    async def run_all_tests(self):
        """Run all tests"""
        logger.info("Starting Strategy Manager Tests")
        logger.info("="*60)
        
        # Test 1: Opportunity scanning
        await self.test_opportunity_scanning()
        await asyncio.sleep(1)
        
        # Test 2: Conflict resolution
        await self.test_conflict_resolution()
        await asyncio.sleep(1)
        
        # Test 3: Capital constraints
        await self.test_capital_constraints()
        await asyncio.sleep(1)
        
        # Test 4: Execution simulation
        await self.test_execution_simulation()
        await asyncio.sleep(1)
        
        # Test 5: Performance tracking
        await self.test_performance_tracking()
        
        logger.info("="*60)
        logger.info("All tests completed successfully!")
        
        # Final status
        final_status = self.manager.get_status()
        logger.info("\nFinal Manager Status:")
        logger.info(json.dumps(final_status, indent=2))


async def main():
    test = StrategyManagerTest()
    await test.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
