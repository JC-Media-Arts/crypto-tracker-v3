"""
Channel Trading Strategy Detector
Identifies price channels (parallel support and resistance lines)
Works best in sideways markets but can work in trending markets too
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from loguru import logger
from scipy import stats
from dataclasses import dataclass


@dataclass
class Channel:
    """Represents a price channel"""
    symbol: str
    upper_line: float  # Resistance level
    lower_line: float  # Support level
    slope: float  # Channel slope (0 = horizontal, positive = uptrend, negative = downtrend)
    width: float  # Channel width in percentage
    touches_upper: int  # Number of times price touched upper line
    touches_lower: int  # Number of times price touched lower line
    strength: float  # Channel strength score (0-1)
    start_time: datetime
    end_time: datetime
    current_position: float  # Where price is in channel (0 = bottom, 1 = top)
    
    @property
    def is_valid(self) -> bool:
        """Check if channel is valid for trading"""
        return (
            self.touches_upper >= 2 and 
            self.touches_lower >= 2 and
            self.strength > 0.6 and
            self.width > 1.0  # At least 1% wide
        )
    
    @property
    def channel_type(self) -> str:
        """Classify channel type"""
        if abs(self.slope) < 0.001:
            return "HORIZONTAL"
        elif self.slope > 0:
            return "ASCENDING"
        else:
            return "DESCENDING"


class ChannelDetector:
    """
    Detects price channels for channel trading strategy
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        
        # Channel detection parameters
        self.min_touches = self.config.get('min_touches', 2)  # Min touches per line
        self.lookback_periods = self.config.get('lookback_periods', 100)  # Bars to analyze
        self.touch_tolerance = self.config.get('touch_tolerance', 0.002)  # 0.2% tolerance
        self.min_channel_width = self.config.get('min_channel_width', 0.01)  # 1% minimum
        self.max_channel_width = self.config.get('max_channel_width', 0.10)  # 10% maximum
        self.parallel_tolerance = self.config.get('parallel_tolerance', 0.15)  # 15% slope difference
        
        # Trading zones
        self.buy_zone = self.config.get('buy_zone', 0.25)  # Bottom 25% of channel
        self.sell_zone = self.config.get('sell_zone', 0.75)  # Top 25% of channel
        
        logger.info("Channel Detector initialized")
    
    def detect_channel(self, symbol: str, ohlc_data: List[Dict]) -> Optional[Channel]:
        """
        Detect price channel from OHLC data
        
        Args:
            symbol: Trading symbol
            ohlc_data: List of OHLC bars (most recent first)
        
        Returns:
            Channel object if found, None otherwise
        """
        if len(ohlc_data) < self.lookback_periods:
            return None
        
        # Convert to DataFrame for easier analysis
        df = pd.DataFrame(ohlc_data[:self.lookback_periods])
        df = df.sort_values('timestamp')  # Ensure chronological order
        
        # Find local highs and lows
        highs = self._find_local_extremes(df['high'].values, is_high=True)
        lows = self._find_local_extremes(df['low'].values, is_high=False)
        
        if len(highs) < self.min_touches or len(lows) < self.min_touches:
            return None
        
        # Fit lines to highs and lows
        upper_line = self._fit_line(highs, df['high'].values)
        lower_line = self._fit_line(lows, df['low'].values)
        
        if upper_line is None or lower_line is None:
            return None
        
        # Check if lines are parallel
        if not self._are_parallel(upper_line, lower_line):
            return None
        
        # Calculate channel properties
        channel = self._create_channel(symbol, df, upper_line, lower_line, highs, lows)
        
        if channel and channel.is_valid:
            logger.info(f"Valid {channel.channel_type} channel detected for {symbol}: "
                       f"Width={channel.width:.2%}, Strength={channel.strength:.2f}, "
                       f"Position={channel.current_position:.2f}")
            return channel
        
        return None
    
    def _find_local_extremes(self, prices: np.ndarray, is_high: bool, window: int = 3) -> List[int]:
        """
        Find local highs or lows in price data
        """
        extremes = []
        
        for i in range(window, len(prices) - window):
            window_prices = prices[i-window:i+window+1]
            
            if is_high:
                # More lenient: price is at or near max
                if prices[i] >= np.max(window_prices) * 0.999:
                    extremes.append(i)
            else:
                # More lenient: price is at or near min
                if prices[i] <= np.min(window_prices) * 1.001:
                    extremes.append(i)
        
        # Ensure we have enough points
        if len(extremes) < 2:
            # Try to find more by being even more lenient
            for i in range(2, len(prices) - 2):
                if is_high and prices[i] > prices[i-1] and prices[i] > prices[i+1]:
                    if i not in extremes:
                        extremes.append(i)
                elif not is_high and prices[i] < prices[i-1] and prices[i] < prices[i+1]:
                    if i not in extremes:
                        extremes.append(i)
        
        return extremes
    
    def _fit_line(self, indices: List[int], prices: np.ndarray) -> Optional[Tuple[float, float]]:
        """
        Fit a line to price points using linear regression
        Returns (slope, intercept)
        """
        if len(indices) < 2:
            return None
        
        x = np.array(indices)
        y = np.array([prices[i] for i in indices])
        
        try:
            slope, intercept, r_value, _, _ = stats.linregress(x, y)
            
            # Check if fit is good enough (lowered threshold for synthetic data)
            if abs(r_value) < 0.5:  # R-squared threshold
                return None
            
            return (slope, intercept)
        except:
            return None
    
    def _are_parallel(self, line1: Tuple[float, float], line2: Tuple[float, float]) -> bool:
        """
        Check if two lines are approximately parallel
        """
        slope1, _ = line1
        slope2, _ = line2
        
        # Handle horizontal lines
        if abs(slope1) < 0.0001 and abs(slope2) < 0.0001:
            return True
        
        # Check if slopes are similar
        if slope1 == 0 or slope2 == 0:
            return False
        
        slope_ratio = abs(slope1 / slope2)
        return (1 - self.parallel_tolerance) <= slope_ratio <= (1 + self.parallel_tolerance)
    
    def _create_channel(self, symbol: str, df: pd.DataFrame, 
                       upper_line: Tuple[float, float], lower_line: Tuple[float, float],
                       highs: List[int], lows: List[int]) -> Optional[Channel]:
        """
        Create Channel object from detected lines
        """
        slope_upper, intercept_upper = upper_line
        slope_lower, intercept_lower = lower_line
        
        # Calculate current channel boundaries
        current_idx = len(df) - 1
        upper_current = slope_upper * current_idx + intercept_upper
        lower_current = slope_lower * current_idx + intercept_lower
        
        # Channel width
        avg_price = df['close'].mean()
        width = (upper_current - lower_current) / avg_price
        
        # Check width constraints
        if width < self.min_channel_width or width > self.max_channel_width:
            return None
        
        # Count touches
        touches_upper = self._count_touches(df['high'].values, upper_line)
        touches_lower = self._count_touches(df['low'].values, lower_line)
        
        # Calculate channel strength (based on touches and consistency)
        strength = self._calculate_strength(df, upper_line, lower_line, touches_upper, touches_lower)
        
        # Current position in channel
        current_price = df['close'].iloc[-1]
        position = (current_price - lower_current) / (upper_current - lower_current)
        position = max(0, min(1, position))  # Clamp to [0, 1]
        
        # Average slope for channel direction
        avg_slope = (slope_upper + slope_lower) / 2
        
        return Channel(
            symbol=symbol,
            upper_line=upper_current,
            lower_line=lower_current,
            slope=avg_slope,
            width=width,
            touches_upper=touches_upper,
            touches_lower=touches_lower,
            strength=strength,
            start_time=pd.to_datetime(df['timestamp'].iloc[0]),
            end_time=pd.to_datetime(df['timestamp'].iloc[-1]),
            current_position=position
        )
    
    def _count_touches(self, prices: np.ndarray, line: Tuple[float, float]) -> int:
        """
        Count how many times price touches a line
        """
        slope, intercept = line
        touches = 0
        
        for i, price in enumerate(prices):
            line_value = slope * i + intercept
            distance = abs(price - line_value) / line_value
            
            if distance <= self.touch_tolerance:
                touches += 1
        
        return touches
    
    def _calculate_strength(self, df: pd.DataFrame, upper_line: Tuple[float, float],
                           lower_line: Tuple[float, float], touches_upper: int, 
                           touches_lower: int) -> float:
        """
        Calculate channel strength score (0-1)
        """
        # Factor 1: Number of touches
        touch_score = min(1.0, (touches_upper + touches_lower) / 10)
        
        # Factor 2: Price containment (how well price stays within channel)
        contained = 0
        total = len(df)
        
        slope_upper, intercept_upper = upper_line
        slope_lower, intercept_lower = lower_line
        
        for i, row in df.iterrows():
            idx = i if isinstance(i, int) else list(df.index).index(i)
            upper_value = slope_upper * idx + intercept_upper
            lower_value = slope_lower * idx + intercept_lower
            
            if lower_value <= row['low'] and row['high'] <= upper_value:
                contained += 1
        
        containment_score = contained / total
        
        # Factor 3: Channel consistency (low variance in width)
        widths = []
        for i in range(0, len(df), 10):  # Sample every 10 bars
            upper_value = slope_upper * i + intercept_upper
            lower_value = slope_lower * i + intercept_lower
            widths.append(upper_value - lower_value)
        
        width_variance = np.std(widths) / np.mean(widths) if widths else 1
        consistency_score = max(0, 1 - width_variance)
        
        # Weighted average
        strength = (
            touch_score * 0.3 +
            containment_score * 0.5 +
            consistency_score * 0.2
        )
        
        return min(1.0, strength)
    
    def get_trading_signal(self, channel: Channel) -> Optional[str]:
        """
        Generate trading signal based on channel position
        
        Returns:
            'BUY', 'SELL', or None
        """
        if not channel.is_valid:
            return None
        
        # Buy near bottom of channel
        if channel.current_position <= self.buy_zone:
            return 'BUY'
        
        # Sell near top of channel
        elif channel.current_position >= self.sell_zone:
            return 'SELL'
        
        return None
    
    def calculate_targets(self, channel: Channel, entry_price: float, 
                         signal: str) -> Dict[str, float]:
        """
        Calculate take profit and stop loss for channel trade
        """
        if signal == 'BUY':
            # Target is top of channel
            take_profit = channel.upper_line
            # Stop is below channel
            stop_loss = channel.lower_line * 0.99  # 1% below channel
            
        elif signal == 'SELL':
            # Target is bottom of channel (for short)
            take_profit = channel.lower_line
            # Stop is above channel
            stop_loss = channel.upper_line * 1.01  # 1% above channel
            
        else:
            return {}
        
        # Calculate percentages
        tp_pct = abs(take_profit - entry_price) / entry_price * 100
        sl_pct = abs(stop_loss - entry_price) / entry_price * 100
        
        return {
            'take_profit': take_profit,
            'stop_loss': stop_loss,
            'take_profit_pct': tp_pct,
            'stop_loss_pct': sl_pct,
            'risk_reward': tp_pct / sl_pct if sl_pct > 0 else 0
        }
