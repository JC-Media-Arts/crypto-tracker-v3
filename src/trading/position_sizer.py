"""
Adaptive Position Sizing System for Crypto Trading.

This module implements intelligent position sizing based on:
- Market regime (BULL/BEAR/NEUTRAL)
- Volatility levels
- Symbol performance relative to BTC
- Risk management constraints
- ML confidence scores (when available)
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from loguru import logger
from dateutil import tz


@dataclass
class PositionSizingConfig:
    """Configuration for adaptive position sizing."""
    
    # Base position settings
    base_position_usd: float = 100.0  # Base position size in USD
    max_position_pct: float = 0.10    # Max 10% of portfolio per position
    min_position_usd: float = 10.0    # Minimum position size
    
    # Market regime multipliers
    bear_market_mult: float = 2.0     # Double size in bear markets
    neutral_market_mult: float = 1.0  # Normal size in neutral
    bull_market_mult: float = 0.5     # Half size in bull markets
    
    # Volatility multipliers
    high_volatility_mult: float = 1.2
    normal_volatility_mult: float = 1.0
    low_volatility_mult: float = 0.8
    volatility_threshold_high: float = 0.6  # 60% annualized
    volatility_threshold_low: float = 0.3   # 30% annualized
    
    # Relative performance multipliers
    underperform_mult: float = 1.3    # When symbol underperforms BTC
    normal_perf_mult: float = 1.0
    outperform_mult: float = 0.7      # When symbol outperforms BTC
    underperform_threshold: float = -5.0  # -5% vs BTC
    outperform_threshold: float = 10.0    # +10% vs BTC
    
    # ML confidence adjustments
    use_ml_confidence: bool = True
    ml_confidence_min_mult: float = 0.5   # At 0% confidence
    ml_confidence_max_mult: float = 1.5   # At 100% confidence
    
    # Risk management
    max_concurrent_positions: int = 20
    max_portfolio_exposure: float = 0.5   # Max 50% of portfolio in positions
    kelly_fraction: float = 0.25          # Use 25% of Kelly criterion
    
    # Market cap tier adjustments
    large_cap_mult: float = 0.8
    mid_cap_mult: float = 1.0
    small_cap_mult: float = 1.2


class AdaptivePositionSizer:
    """
    Calculates optimal position sizes based on market conditions and risk parameters.
    """
    
    def __init__(self, config: PositionSizingConfig = None):
        """Initialize the position sizer with configuration."""
        self.config = config or PositionSizingConfig()
        self._btc_data_cache = {}
        self._last_regime_check = None
        self._current_regime = "NEUTRAL"
        
    def calculate_position_size(
        self,
        symbol: str,
        portfolio_value: float,
        market_data: Dict,
        ml_confidence: Optional[float] = None,
        current_positions: int = 0
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculate the optimal position size for a trade.
        
        Args:
            symbol: Trading symbol (e.g., "BTC", "ETH")
            portfolio_value: Total portfolio value in USD
            market_data: Dictionary containing:
                - btc_regime: Current BTC market regime
                - btc_volatility_7d: 7-day BTC volatility
                - symbol_vs_btc_7d: Symbol's 7-day performance vs BTC
                - market_cap_tier: Symbol's market cap tier (0=large, 1=mid, 2=small)
            ml_confidence: ML model confidence score (0-1)
            current_positions: Number of currently open positions
            
        Returns:
            Tuple of (position_size_usd, multipliers_dict)
        """
        # Start with base position size
        position_size = self.config.base_position_usd
        multipliers = {}
        
        # 1. Apply market regime multiplier
        regime_mult = self._get_regime_multiplier(market_data.get('btc_regime', 'NEUTRAL'))
        position_size *= regime_mult
        multipliers['regime'] = regime_mult
        
        # 2. Apply volatility multiplier
        vol_mult = self._get_volatility_multiplier(market_data.get('btc_volatility_7d', 0.4))
        position_size *= vol_mult
        multipliers['volatility'] = vol_mult
        
        # 3. Apply relative performance multiplier
        perf_mult = self._get_performance_multiplier(market_data.get('symbol_vs_btc_7d', 0))
        position_size *= perf_mult
        multipliers['performance'] = perf_mult
        
        # 4. Apply market cap tier multiplier
        tier_mult = self._get_tier_multiplier(market_data.get('market_cap_tier', 1))
        position_size *= tier_mult
        multipliers['tier'] = tier_mult
        
        # 5. Apply ML confidence multiplier (if available)
        if self.config.use_ml_confidence and ml_confidence is not None:
            conf_mult = self._get_confidence_multiplier(ml_confidence)
            position_size *= conf_mult
            multipliers['ml_confidence'] = conf_mult
        
        # 6. Apply risk management constraints
        position_size = self._apply_risk_constraints(
            position_size, 
            portfolio_value, 
            current_positions
        )
        
        # Log the calculation
        logger.debug(
            f"Position size for {symbol}: ${position_size:.2f} "
            f"(multipliers: {multipliers})"
        )
        
        return position_size, multipliers
    
    def _get_regime_multiplier(self, regime: str) -> float:
        """Get position size multiplier based on market regime."""
        regime_map = {
            'BEAR': self.config.bear_market_mult,
            'NEUTRAL': self.config.neutral_market_mult,
            'BULL': self.config.bull_market_mult
        }
        return regime_map.get(regime, self.config.neutral_market_mult)
    
    def _get_volatility_multiplier(self, volatility: float) -> float:
        """Get position size multiplier based on volatility."""
        if volatility > self.config.volatility_threshold_high:
            return self.config.high_volatility_mult
        elif volatility < self.config.volatility_threshold_low:
            return self.config.low_volatility_mult
        else:
            return self.config.normal_volatility_mult
    
    def _get_performance_multiplier(self, symbol_vs_btc: float) -> float:
        """Get position size multiplier based on relative performance."""
        if symbol_vs_btc < self.config.underperform_threshold:
            return self.config.underperform_mult
        elif symbol_vs_btc > self.config.outperform_threshold:
            return self.config.outperform_mult
        else:
            return self.config.normal_perf_mult
    
    def _get_tier_multiplier(self, tier: int) -> float:
        """Get position size multiplier based on market cap tier."""
        tier_map = {
            0: self.config.large_cap_mult,
            1: self.config.mid_cap_mult,
            2: self.config.small_cap_mult
        }
        return tier_map.get(tier, self.config.mid_cap_mult)
    
    def _get_confidence_multiplier(self, confidence: float) -> float:
        """Get position size multiplier based on ML confidence."""
        # Linear interpolation between min and max multipliers
        confidence = max(0, min(1, confidence))  # Clamp to [0, 1]
        return (
            self.config.ml_confidence_min_mult + 
            (self.config.ml_confidence_max_mult - self.config.ml_confidence_min_mult) * confidence
        )
    
    def _apply_risk_constraints(
        self, 
        position_size: float, 
        portfolio_value: float,
        current_positions: int
    ) -> float:
        """Apply risk management constraints to position size."""
        # Constraint 1: Check if we have room for more positions
        if current_positions >= self.config.max_concurrent_positions:
            logger.warning(
                f"Max concurrent positions ({self.config.max_concurrent_positions}) reached"
            )
            return 0
        
        # Constraint 2: Max position as percentage of portfolio
        max_position = portfolio_value * self.config.max_position_pct
        position_size = min(position_size, max_position)
        
        # Constraint 3: Check total portfolio exposure
        # This is simplified - in production, you'd calculate actual exposure
        avg_position = portfolio_value * self.config.max_portfolio_exposure / self.config.max_concurrent_positions
        position_size = min(position_size, avg_position)
        
        # Constraint 4: Minimum position size (but only if position is non-zero)
        if position_size > 0:
            position_size = max(position_size, self.config.min_position_usd)
        
        return position_size
    
    def calculate_kelly_size(
        self,
        win_probability: float,
        avg_win: float,
        avg_loss: float,
        portfolio_value: float
    ) -> float:
        """
        Calculate position size using Kelly Criterion.
        
        Args:
            win_probability: Probability of winning (0-1)
            avg_win: Average win amount (positive)
            avg_loss: Average loss amount (positive)
            portfolio_value: Total portfolio value
            
        Returns:
            Optimal position size in USD
        """
        if avg_loss == 0:
            return self.config.base_position_usd
        
        # Kelly formula: f = (p*b - q) / b
        # where p = win prob, q = loss prob, b = win/loss ratio
        q = 1 - win_probability
        b = avg_win / avg_loss
        
        kelly_fraction = (win_probability * b - q) / b
        
        # Apply safety factor (use only 25% of Kelly)
        kelly_fraction *= self.config.kelly_fraction
        
        # Ensure non-negative and cap at 25% of portfolio
        kelly_fraction = max(0, min(kelly_fraction, 0.25))
        
        # Calculate position size
        if kelly_fraction > 0:
            position_size = portfolio_value * kelly_fraction
        else:
            position_size = self.config.min_position_usd
        
        return position_size
    
    def get_market_regime(self, btc_price_data: pd.DataFrame) -> str:
        """
        Determine current market regime based on BTC price action.
        
        Args:
            btc_price_data: DataFrame with BTC price data (needs 'close' column)
            
        Returns:
            Market regime: "BULL", "BEAR", or "NEUTRAL"
        """
        if len(btc_price_data) < 200:
            return "NEUTRAL"
        
        # Calculate SMAs
        sma50 = btc_price_data['close'].rolling(window=50).mean().iloc[-1]
        sma200 = btc_price_data['close'].rolling(window=200).mean().iloc[-1]
        current_price = btc_price_data['close'].iloc[-1]
        
        # Determine regime
        if sma50 > sma200 and current_price > sma50:
            return "BULL"
        elif sma50 < sma200 and current_price < sma50:
            return "BEAR"
        else:
            return "NEUTRAL"
    
    def calculate_volatility(self, price_data: pd.DataFrame, window_days: int = 7) -> float:
        """
        Calculate annualized volatility.
        
        Args:
            price_data: DataFrame with price data (needs 'close' column)
            window_days: Number of days for volatility calculation
            
        Returns:
            Annualized volatility (0-1 scale)
        """
        if len(price_data) < 2:
            return 0.4  # Default to moderate volatility
        
        # Calculate returns
        returns = price_data['close'].pct_change().dropna()
        
        # Use recent window
        if len(returns) > window_days:
            returns = returns.tail(window_days)
        
        # Calculate annualized volatility
        daily_vol = returns.std()
        annual_vol = daily_vol * np.sqrt(252)
        
        return annual_vol
    
    def get_position_sizing_summary(
        self,
        portfolio_value: float,
        current_positions: int = 0
    ) -> Dict:
        """
        Get a summary of current position sizing parameters.
        
        Args:
            portfolio_value: Total portfolio value
            current_positions: Number of open positions
            
        Returns:
            Dictionary with sizing parameters and limits
        """
        return {
            'base_position_usd': self.config.base_position_usd,
            'max_position_usd': portfolio_value * self.config.max_position_pct,
            'min_position_usd': self.config.min_position_usd,
            'positions_available': self.config.max_concurrent_positions - current_positions,
            'max_portfolio_exposure_usd': portfolio_value * self.config.max_portfolio_exposure,
            'current_regime_multiplier': self._get_regime_multiplier(self._current_regime),
            'config': {
                'bear_mult': self.config.bear_market_mult,
                'bull_mult': self.config.bull_market_mult,
                'high_vol_mult': self.config.high_volatility_mult,
                'underperform_mult': self.config.underperform_mult
            }
        }


class PortfolioRiskManager:
    """
    Manages overall portfolio risk and position allocation.
    """
    
    def __init__(self, position_sizer: AdaptivePositionSizer):
        """Initialize with a position sizer."""
        self.position_sizer = position_sizer
        self.open_positions = {}
        self.portfolio_value = 10000.0  # Default starting value
        
    def can_open_position(self, symbol: str, proposed_size: float) -> bool:
        """
        Check if a new position can be opened within risk limits.
        
        Args:
            symbol: Trading symbol
            proposed_size: Proposed position size in USD
            
        Returns:
            True if position can be opened
        """
        # Check if symbol already has position
        if symbol in self.open_positions:
            logger.warning(f"Position already exists for {symbol}")
            return False
        
        # Check concurrent positions limit
        if len(self.open_positions) >= self.position_sizer.config.max_concurrent_positions:
            logger.warning("Maximum concurrent positions reached")
            return False
        
        # Check total exposure
        current_exposure = sum(pos['size'] for pos in self.open_positions.values())
        max_exposure = self.portfolio_value * self.position_sizer.config.max_portfolio_exposure
        
        if current_exposure + proposed_size > max_exposure:
            logger.warning(
                f"Position would exceed max exposure "
                f"(current: ${current_exposure:.2f}, max: ${max_exposure:.2f})"
            )
            return False
        
        return True
    
    def open_position(
        self,
        symbol: str,
        entry_price: float,
        size: float,
        stop_loss: float,
        take_profit: float
    ) -> bool:
        """
        Open a new position if risk limits allow.
        
        Args:
            symbol: Trading symbol
            entry_price: Entry price
            size: Position size in USD
            stop_loss: Stop loss price
            take_profit: Take profit price
            
        Returns:
            True if position was opened
        """
        if not self.can_open_position(symbol, size):
            return False
        
        self.open_positions[symbol] = {
            'entry_price': entry_price,
            'size': size,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'entry_time': datetime.now(tz.UTC)
        }
        
        logger.info(
            f"Opened position: {symbol} @ ${entry_price:.2f}, "
            f"size: ${size:.2f}, SL: ${stop_loss:.2f}, TP: ${take_profit:.2f}"
        )
        
        return True
    
    def close_position(self, symbol: str, exit_price: float) -> Optional[float]:
        """
        Close a position and return P&L.
        
        Args:
            symbol: Trading symbol
            exit_price: Exit price
            
        Returns:
            P&L in USD or None if position doesn't exist
        """
        if symbol not in self.open_positions:
            logger.warning(f"No position exists for {symbol}")
            return None
        
        position = self.open_positions[symbol]
        pnl = position['size'] * ((exit_price - position['entry_price']) / position['entry_price'])
        
        del self.open_positions[symbol]
        
        logger.info(f"Closed position: {symbol} @ ${exit_price:.2f}, P&L: ${pnl:+.2f}")
        
        return pnl
    
    def get_portfolio_summary(self) -> Dict:
        """Get current portfolio status and metrics."""
        current_exposure = sum(pos['size'] for pos in self.open_positions.values())
        
        return {
            'portfolio_value': self.portfolio_value,
            'open_positions': len(self.open_positions),
            'current_exposure_usd': current_exposure,
            'current_exposure_pct': (current_exposure / self.portfolio_value) * 100,
            'available_capital': self.portfolio_value - current_exposure,
            'positions': self.open_positions
        }
