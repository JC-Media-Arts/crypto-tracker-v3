#!/usr/bin/env python3
"""
Unit tests for the Adaptive Position Sizing System.
"""

import sys
from pathlib import Path
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dateutil import tz

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.trading.position_sizer import (
    AdaptivePositionSizer, 
    PositionSizingConfig,
    PortfolioRiskManager
)


class TestAdaptivePositionSizer:
    """Test suite for AdaptivePositionSizer."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = PositionSizingConfig(
            base_position_usd=100.0,
            bear_market_mult=2.0,
            bull_market_mult=0.5,
            high_volatility_mult=1.2,
            underperform_mult=1.3
        )
        self.sizer = AdaptivePositionSizer(self.config)
        
    def test_bear_market_sizing(self):
        """Test position sizing in bear market conditions."""
        market_data = {
            'btc_regime': 'BEAR',
            'btc_volatility_7d': 0.4,  # Normal volatility
            'symbol_vs_btc_7d': 0,      # Neutral performance
            'market_cap_tier': 1        # Mid-cap
        }
        
        size, multipliers = self.sizer.calculate_position_size(
            symbol='TEST',
            portfolio_value=10000,
            market_data=market_data
        )
        
        # Base 100 * 2.0 (bear) = 200
        assert size == 200.0
        assert multipliers['regime'] == 2.0
        
    def test_bull_market_sizing(self):
        """Test position sizing in bull market conditions."""
        market_data = {
            'btc_regime': 'BULL',
            'btc_volatility_7d': 0.4,
            'symbol_vs_btc_7d': 0,
            'market_cap_tier': 1
        }
        
        size, multipliers = self.sizer.calculate_position_size(
            symbol='TEST',
            portfolio_value=10000,
            market_data=market_data
        )
        
        # Base 100 * 0.5 (bull) = 50
        assert size == 50.0
        assert multipliers['regime'] == 0.5
        
    def test_high_volatility_adjustment(self):
        """Test position sizing with high volatility."""
        market_data = {
            'btc_regime': 'NEUTRAL',
            'btc_volatility_7d': 0.8,  # High volatility
            'symbol_vs_btc_7d': 0,
            'market_cap_tier': 1
        }
        
        size, multipliers = self.sizer.calculate_position_size(
            symbol='TEST',
            portfolio_value=10000,
            market_data=market_data
        )
        
        # Base 100 * 1.0 (neutral) * 1.2 (high vol) = 120
        assert size == 120.0
        assert multipliers['volatility'] == 1.2
        
    def test_underperformance_boost(self):
        """Test position sizing when symbol underperforms BTC."""
        market_data = {
            'btc_regime': 'NEUTRAL',
            'btc_volatility_7d': 0.4,
            'symbol_vs_btc_7d': -10,  # Underperforming by 10%
            'market_cap_tier': 1
        }
        
        size, multipliers = self.sizer.calculate_position_size(
            symbol='TEST',
            portfolio_value=10000,
            market_data=market_data
        )
        
        # Base 100 * 1.0 (neutral) * 1.0 (normal vol) * 1.3 (underperform) = 130
        assert size == 130.0
        assert multipliers['performance'] == 1.3
        
    def test_ml_confidence_adjustment(self):
        """Test position sizing with ML confidence."""
        market_data = {
            'btc_regime': 'NEUTRAL',
            'btc_volatility_7d': 0.4,
            'symbol_vs_btc_7d': 0,
            'market_cap_tier': 1
        }
        
        # High confidence
        size, multipliers = self.sizer.calculate_position_size(
            symbol='TEST',
            portfolio_value=10000,
            market_data=market_data,
            ml_confidence=0.8
        )
        
        # Base 100 * 1.0 * 1.0 * 1.0 * 1.0 * 1.3 (80% confidence)
        # ML mult = 0.5 + (1.5 - 0.5) * 0.8 = 1.3
        assert size == 130.0
        assert multipliers['ml_confidence'] == 1.3
        
        # Low confidence
        size, multipliers = self.sizer.calculate_position_size(
            symbol='TEST',
            portfolio_value=10000,
            market_data=market_data,
            ml_confidence=0.2
        )
        
        # ML mult = 0.5 + (1.5 - 0.5) * 0.2 = 0.7
        assert size == 70.0
        assert multipliers['ml_confidence'] == 0.7
        
    def test_combined_multipliers(self):
        """Test position sizing with all multipliers combined."""
        market_data = {
            'btc_regime': 'BEAR',        # 2.0x
            'btc_volatility_7d': 0.8,     # 1.2x
            'symbol_vs_btc_7d': -10,       # 1.3x
            'market_cap_tier': 2           # 1.2x (small cap)
        }
        
        size, multipliers = self.sizer.calculate_position_size(
            symbol='TEST',
            portfolio_value=10000,
            market_data=market_data,
            ml_confidence=0.7  # 1.2x
        )
        
        # Base 100 * 2.0 * 1.2 * 1.3 * 1.2 * 1.2 = 449.28
        # But capped by max_portfolio_exposure / max_concurrent_positions
        # = 10000 * 0.5 / 20 = 250
        assert size == 250.0  # Capped at avg position size
        
    def test_max_position_constraint(self):
        """Test that position size is capped at max percentage."""
        market_data = {
            'btc_regime': 'BEAR',
            'btc_volatility_7d': 0.8,
            'symbol_vs_btc_7d': -20,
            'market_cap_tier': 2
        }
        
        # Small portfolio should cap position
        size, _ = self.sizer.calculate_position_size(
            symbol='TEST',
            portfolio_value=1000,  # Small portfolio
            market_data=market_data,
            ml_confidence=1.0
        )
        
        # Max position = 1000 * 0.1 = 100
        # But also capped by max_portfolio_exposure / max_concurrent_positions
        # = 1000 * 0.5 / 20 = 25
        assert size == 25.0  # Capped at avg position size
        
    def test_min_position_constraint(self):
        """Test that position size meets minimum."""
        market_data = {
            'btc_regime': 'BULL',  # 0.5x - very small
            'btc_volatility_7d': 0.2,  # 0.8x - low vol
            'symbol_vs_btc_7d': 20,  # 0.7x - outperforming
            'market_cap_tier': 0  # 0.8x - large cap
        }
        
        size, _ = self.sizer.calculate_position_size(
            symbol='TEST',
            portfolio_value=10000,
            market_data=market_data,
            ml_confidence=0.0  # 0.5x - no confidence
        )
        
        # Would be 100 * 0.5 * 0.8 * 0.7 * 0.8 * 0.5 = 11.2
        # But should be at least min_position_usd = 10
        # Actually it's 11.2, which is above 10
        assert size >= self.config.min_position_usd
        
    def test_kelly_criterion_sizing(self):
        """Test Kelly criterion position sizing."""
        # Favorable conditions
        kelly_size = self.sizer.calculate_kelly_size(
            win_probability=0.6,
            avg_win=100,
            avg_loss=50,
            portfolio_value=10000
        )
        
        # Kelly = (0.6 * 2 - 0.4) / 2 = 0.4
        # With safety factor 0.25: 0.4 * 0.25 = 0.1
        # Position = 10000 * 0.1 = 1000
        assert abs(kelly_size - 1000.0) < 0.01  # Allow for floating point precision
        
        # Unfavorable conditions
        kelly_size = self.sizer.calculate_kelly_size(
            win_probability=0.3,
            avg_win=100,
            avg_loss=100,
            portfolio_value=10000
        )
        
        # Kelly = (0.3 * 1 - 0.7) / 1 = -0.4 (negative, so 0)
        assert kelly_size == self.config.min_position_usd  # Minimum size
        
    def test_market_regime_detection(self):
        """Test market regime detection from price data."""
        # Create sample price data
        dates = pd.date_range(end=datetime.now(tz.UTC), periods=250, freq='D')
        
        # Bull market: uptrending
        prices_bull = pd.Series(
            100 * (1 + np.random.randn(250) * 0.01).cumprod(),
            index=dates
        )
        prices_bull = prices_bull * (1.5 ** (np.arange(250) / 250))  # Uptrend
        df_bull = pd.DataFrame({'close': prices_bull})
        
        regime = self.sizer.get_market_regime(df_bull)
        # This might be BULL or NEUTRAL depending on exact SMA crossover
        assert regime in ['BULL', 'NEUTRAL']
        
        # Bear market: downtrending
        prices_bear = pd.Series(
            100 * (1 + np.random.randn(250) * 0.01).cumprod(),
            index=dates
        )
        prices_bear = prices_bear * (0.7 ** (np.arange(250) / 250))  # Downtrend
        df_bear = pd.DataFrame({'close': prices_bear})
        
        regime = self.sizer.get_market_regime(df_bear)
        # This might be BEAR or NEUTRAL depending on exact SMA crossover
        assert regime in ['BEAR', 'NEUTRAL']
        
    def test_volatility_calculation(self):
        """Test volatility calculation."""
        # Create sample price data with known volatility
        dates = pd.date_range(end=datetime.now(tz.UTC), periods=30, freq='D')
        
        # Low volatility
        prices_low = pd.Series(
            100 * (1 + np.random.randn(30) * 0.005),  # 0.5% daily vol
            index=dates
        )
        df_low = pd.DataFrame({'close': prices_low})
        
        vol_low = self.sizer.calculate_volatility(df_low, window_days=7)
        assert 0.05 < vol_low < 0.15  # Should be low
        
        # High volatility
        prices_high = pd.Series(
            100 * (1 + np.random.randn(30) * 0.05),  # 5% daily vol
            index=dates
        )
        df_high = pd.DataFrame({'close': prices_high})
        
        vol_high = self.sizer.calculate_volatility(df_high, window_days=7)
        assert 0.5 < vol_high < 2.0  # Should be high (widened range for random data)


class TestPortfolioRiskManager:
    """Test suite for PortfolioRiskManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config = PositionSizingConfig(
            max_concurrent_positions=3,
            max_portfolio_exposure=0.5
        )
        sizer = AdaptivePositionSizer(config)
        self.manager = PortfolioRiskManager(sizer)
        self.manager.portfolio_value = 10000
        
    def test_open_position(self):
        """Test opening a position."""
        success = self.manager.open_position(
            symbol='BTC',
            entry_price=50000,
            size=1000,
            stop_loss=45000,
            take_profit=55000
        )
        
        assert success is True
        assert 'BTC' in self.manager.open_positions
        assert self.manager.open_positions['BTC']['size'] == 1000
        
    def test_max_positions_limit(self):
        """Test that max concurrent positions is enforced."""
        # Open max positions
        for i in range(3):
            self.manager.open_position(
                symbol=f'TEST{i}',
                entry_price=100,
                size=100,
                stop_loss=90,
                take_profit=110
            )
        
        # Try to open one more
        can_open = self.manager.can_open_position('TEST3', 100)
        assert can_open is False
        
    def test_max_exposure_limit(self):
        """Test that max portfolio exposure is enforced."""
        # Try to open position exceeding max exposure
        can_open = self.manager.can_open_position('BTC', 6000)  # 60% of portfolio
        assert can_open is False
        
        # Should allow up to 50%
        can_open = self.manager.can_open_position('BTC', 4000)  # 40% of portfolio
        assert can_open is True
        
    def test_close_position_with_profit(self):
        """Test closing a position with profit."""
        self.manager.open_position(
            symbol='BTC',
            entry_price=50000,
            size=1000,
            stop_loss=45000,
            take_profit=55000
        )
        
        pnl = self.manager.close_position('BTC', 55000)  # 10% profit
        assert pnl == 100.0  # 1000 * 0.1
        assert 'BTC' not in self.manager.open_positions
        
    def test_close_position_with_loss(self):
        """Test closing a position with loss."""
        self.manager.open_position(
            symbol='BTC',
            entry_price=50000,
            size=1000,
            stop_loss=45000,
            take_profit=55000
        )
        
        pnl = self.manager.close_position('BTC', 45000)  # 10% loss
        assert pnl == -100.0  # 1000 * -0.1
        
    def test_portfolio_summary(self):
        """Test portfolio summary calculation."""
        # Open two positions
        self.manager.open_position('BTC', 50000, 1000, 45000, 55000)
        self.manager.open_position('ETH', 3000, 500, 2700, 3300)
        
        summary = self.manager.get_portfolio_summary()
        
        assert summary['portfolio_value'] == 10000
        assert summary['open_positions'] == 2
        assert summary['current_exposure_usd'] == 1500
        assert summary['current_exposure_pct'] == 15.0
        assert summary['available_capital'] == 8500


def test_integration():
    """Integration test of the complete system."""
    # Set up configuration
    config = PositionSizingConfig(
        base_position_usd=100,
        bear_market_mult=2.0,
        bull_market_mult=0.5
    )
    
    # Create sizer and manager
    sizer = AdaptivePositionSizer(config)
    manager = PortfolioRiskManager(sizer)
    manager.portfolio_value = 10000
    
    # Simulate market conditions
    market_data = {
        'btc_regime': 'BEAR',
        'btc_volatility_7d': 0.6,
        'symbol_vs_btc_7d': -8,
        'market_cap_tier': 1
    }
    
    # Calculate position size
    size, multipliers = sizer.calculate_position_size(
        symbol='SOL',
        portfolio_value=manager.portfolio_value,
        market_data=market_data,
        ml_confidence=0.75,
        current_positions=len(manager.open_positions)
    )
    
    # Verify we got a reasonable size
    assert 200 < size < 500  # Should be enhanced from base 100
    
    # Open position if allowed
    if manager.can_open_position('SOL', size):
        success = manager.open_position(
            symbol='SOL',
            entry_price=100,
            size=size,
            stop_loss=92,
            take_profit=110
        )
        assert success is True
    
    # Get summary
    summary = manager.get_portfolio_summary()
    assert summary['open_positions'] == 1
    assert summary['current_exposure_usd'] == size


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, '-v'])
