"""
Swing Trading Strategy Detector
Identifies momentum and breakout opportunities for multi-day trades
Optimized for bull market conditions
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
from src.data.hybrid_fetcher import HybridDataFetcher
import asyncio

logger = logging.getLogger(__name__)


class SwingDetector:
    """
    Detects swing trading opportunities based on:
    - Breakout patterns
    - Momentum indicators
    - Volume analysis
    - Trend strength
    """

    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.fetcher = HybridDataFetcher()

        # Swing detection parameters
        self.config = {
            # Breakout detection
            "breakout_lookback": 20,  # periods to look back for resistance
            "breakout_threshold": 1.02,  # 2% above resistance
            "volume_spike_threshold": 2.0,  # 2x average volume
            # Momentum indicators
            "momentum_period": 14,
            "rsi_overbought": 70,
            "rsi_bullish_min": 50,  # RSI should be above 50 for bullish momentum
            "macd_signal_cross": True,
            # Trend filters
            "sma_fast": 20,
            "sma_slow": 50,
            "min_trend_strength": 0.02,  # 2% difference between SMAs
            # Price action
            "min_price_change_24h": 3.0,  # 3% minimum move
            "max_price_change_24h": 15.0,  # 15% max to avoid FOMO
            "min_candle_body": 0.5,  # 50% of candle should be body (not wick)
            # Volume requirements
            "min_volume_usd": 1000000,  # $1M daily volume
            "volume_trend_periods": 5,  # periods for volume trend
            # Risk filters
            "max_volatility": 0.10,  # 10% daily volatility max
            "min_liquidity_ratio": 0.1,  # position size vs daily volume
        }

        # Track detected setups to avoid duplicates
        self.active_setups = {}

    def detect_setup(self, symbol: str, data: List[Dict]) -> Optional[Dict]:
        """
        Detect swing setup for a single symbol.

        Args:
            symbol: Symbol to check
            data: OHLC data for the symbol

        Returns:
            Setup dictionary if detected, None otherwise
        """
        if not data or len(data) < 20:
            return None

        # Convert list to DataFrame if needed
        if isinstance(data, list):
            df = pd.DataFrame(data)
        else:
            df = data

        # Calculate indicators first
        df = self._calculate_indicators(df)

        # Check for breakout
        breakout = self._detect_breakout(df)
        if not breakout.get("detected", False):
            return None

        # Check momentum
        momentum = self._check_momentum(df)
        if not momentum.get("strong", False):
            return None

        # Create setup
        latest = df.iloc[-1] if isinstance(df, pd.DataFrame) else df[-1]

        # Calculate composite score from breakout and momentum
        breakout_strength = breakout.get("strength", 0)
        momentum_score = momentum.get("score", 0)
        volume_ratio = breakout.get("volume_ratio", 1)

        # Composite score: combination of breakout strength, momentum, and volume
        # This represents the overall quality of the setup
        composite_score = (
            breakout_strength * 0.4
            + momentum_score * 0.4  # 40% weight on breakout strength
            + min(volume_ratio / 2, 1) * 0.2  # 40% weight on momentum  # 20% weight on volume (capped at 2x)
        ) * 100  # Scale to 0-100

        setup = {
            "symbol": symbol,
            "detected_at": latest.get("timestamp"),
            "price": latest.get("close", 0),
            "breakout_strength": breakout_strength,
            "volume_surge": volume_ratio,
            "momentum_score": momentum_score,
            "score": composite_score,  # Overall setup quality score
            "pattern": breakout.get("pattern", "breakout"),
            "confidence": 0.5,  # Base confidence
        }

        # Calculate confidence without ML if needed
        setup["confidence"] = self.calculate_confidence_without_ml(setup, df)

        return setup

    def calculate_confidence_without_ml(self, setup: Dict, df: pd.DataFrame) -> float:
        """
        Calculate confidence score without ML based on technical indicators.
        This replaces ML predictions when ML is disabled.

        Args:
            setup: The detected setup dictionary
            df: DataFrame with calculated indicators

        Returns:
            Confidence score between 0.0 and 1.0
        """
        confidence = 0.3  # Base confidence for any valid setup
        latest = df.iloc[-1]

        # Volume confirmation (0-0.2 points)
        volume_ratio = setup.get("volume_surge", 1.0)
        if volume_ratio > 3.0:
            confidence += 0.2  # Very strong volume
        elif volume_ratio > 2.0:
            confidence += 0.15  # Strong volume
        elif volume_ratio > 1.5:
            confidence += 0.1  # Moderate volume
        elif volume_ratio > 1.2:
            confidence += 0.05  # Slight volume increase

        # Breakout strength (0-0.2 points)
        breakout_strength = setup.get("breakout_strength", 0) * 100  # Convert to percentage
        if breakout_strength > 3.0:
            confidence += 0.2  # Strong breakout
        elif breakout_strength > 2.0:
            confidence += 0.15
        elif breakout_strength > 1.0:
            confidence += 0.1
        elif breakout_strength > 0.5:
            confidence += 0.05

        # Momentum alignment (0-0.15 points)
        rsi = latest.get("rsi", 50)
        if 50 < rsi < 70:
            confidence += 0.1  # Good RSI range
        elif 45 < rsi <= 50 or 70 <= rsi < 75:
            confidence += 0.05  # Acceptable RSI

        if latest.get("macd", 0) > latest.get("macd_signal", 0):
            confidence += 0.05  # MACD bullish

        # Trend alignment (0-0.15 points)
        if latest.get("close", 0) > latest.get("sma_20", 0) > latest.get("sma_50", 0):
            confidence += 0.15  # Perfect trend alignment
        elif latest.get("close", 0) > latest.get("sma_20", 0):
            confidence += 0.1  # Above short-term MA
        elif latest.get("close", 0) > latest.get("sma_50", 0):
            confidence += 0.05  # Above long-term MA

        # Cap confidence at 0.95 (never 100% certain without ML)
        return min(confidence, 0.95)

    async def detect_setups(self, symbols: List[str]) -> List[Dict]:
        """
        Scan multiple symbols for swing trading setups

        Args:
            symbols: List of symbols to scan

        Returns:
            List of detected swing setups with scores
        """
        setups = []

        for symbol in symbols:
            try:
                # Get OHLC data
                ohlc_data = await self._fetch_ohlc_data(symbol)

                if ohlc_data is None or len(ohlc_data) < 100:
                    continue

                # Convert to DataFrame
                df = pd.DataFrame(ohlc_data)

                # Calculate indicators
                df = self._calculate_indicators(df)

                # Check for swing setup
                setup = self._check_swing_conditions(df, symbol)

                if setup:
                    setups.append(setup)
                    logger.info(f"🎯 Swing setup detected for {symbol}: {setup['pattern']}")

            except Exception as e:
                logger.error(f"Error detecting swing setup for {symbol}: {e}")

        # Sort by score
        setups.sort(key=lambda x: x["score"], reverse=True)

        return setups

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators for swing detection"""

        # Price SMAs
        df["sma_20"] = df["close"].rolling(window=self.config["sma_fast"]).mean()
        df["sma_50"] = df["close"].rolling(window=self.config["sma_slow"]).mean()

        # Volume SMA
        df["volume_sma"] = df["volume"].rolling(window=20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_sma"]

        # RSI
        df["rsi"] = self._calculate_rsi(df["close"])

        # MACD
        df["macd"], df["macd_signal"], df["macd_hist"] = self._calculate_macd(df["close"])

        # Bollinger Bands
        (
            df["bb_upper"],
            df["bb_middle"],
            df["bb_lower"],
        ) = self._calculate_bollinger_bands(df["close"])

        # ATR for volatility
        df["atr"] = self._calculate_atr(df)
        df["volatility"] = df["atr"] / df["close"]

        # Price momentum
        df["momentum"] = df["close"].pct_change(periods=self.config["momentum_period"])

        # Resistance levels
        df["resistance"] = df["high"].rolling(window=self.config["breakout_lookback"]).max()
        df["support"] = df["low"].rolling(window=self.config["breakout_lookback"]).min()

        # Candle patterns
        df["candle_body"] = abs(df["close"] - df["open"])
        df["candle_range"] = df["high"] - df["low"]
        df["body_ratio"] = df["candle_body"] / (df["candle_range"] + 0.0001)

        # Trend strength
        df["trend_strength"] = (df["sma_20"] - df["sma_50"]) / df["sma_50"]

        return df

    def _check_swing_conditions(self, df: pd.DataFrame, symbol: str) -> Optional[Dict]:
        """Check if current conditions meet swing trading criteria"""

        if len(df) < 50:
            return None

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # Skip if already in active setup
        if symbol in self.active_setups:
            if (datetime.now() - self.active_setups[symbol]["timestamp"]).seconds < 3600:
                return None

        score = 0
        signals = []
        pattern = "None"

        # 1. Breakout Detection (30 points)
        if self._detect_breakout(df):
            score += 30
            signals.append("Breakout")
            pattern = "Resistance Breakout"

        # 2. Volume Confirmation (20 points)
        if latest["volume_ratio"] > self.config["volume_spike_threshold"]:
            score += 20
            signals.append("Volume Spike")

        # 3. Trend Alignment (20 points)
        if self._check_trend_alignment(df):
            score += 20
            signals.append("Trend Aligned")

        # 4. Momentum Indicators (15 points)
        momentum_result = self._check_momentum(df)
        momentum_score = momentum_result["score"] if isinstance(momentum_result, dict) else momentum_result
        score += momentum_score
        if momentum_score > 10:
            signals.append("Strong Momentum")

        # 5. Price Action (15 points)
        price_change_24h = ((latest["close"] - df.iloc[-24]["close"]) / df.iloc[-24]["close"]) * 100

        if self.config["min_price_change_24h"] <= price_change_24h <= self.config["max_price_change_24h"]:
            score += 15
            signals.append(f"Price +{price_change_24h:.1f}%")

        # Check for specific patterns
        if pattern == "None":
            pattern = self._identify_pattern(df)

        # Minimum score threshold
        if score < 50:
            return None

        # Risk checks
        if not self._check_risk_criteria(df):
            return None

        # Create setup
        setup = {
            "symbol": symbol,
            "pattern": pattern,
            "score": score,
            "signals": signals,
            "price": latest["close"],  # Standardized field name
            "entry_price": latest["close"],  # Keep for backward compatibility
            "stop_loss": self._calculate_stop_loss(df),
            "take_profit": self._calculate_take_profit(df),
            "position_size_multiplier": self._calculate_size_multiplier(score),
            "rsi": latest["rsi"],
            "volume_ratio": latest["volume_ratio"],
            "trend_strength": latest["trend_strength"],
            "volatility": latest["volatility"],
            "timestamp": datetime.now(),
        }

        # Track setup
        self.active_setups[symbol] = setup

        return setup

    def _detect_breakout(self, df: pd.DataFrame) -> dict:
        """Detect if price is breaking out above resistance"""

        latest = df.iloc[-1]
        prev_high = df.iloc[-2]["resistance"]

        breakout_info = {
            "detected": False,
            "strength": 0,
            "volume_ratio": latest.get("volume_ratio", 1),
            "pattern": None,
        }

        # Check if current price is breaking above recent resistance
        if latest["close"] > prev_high * self.config["breakout_threshold"]:
            # Confirm with volume (must be 2x for strong breakout per MASTER_PLAN)
            if latest["volume_ratio"] > self.config["volume_spike_threshold"]:
                # Also check RSI is bullish (>50)
                if latest.get("rsi", 50) > self.config["rsi_bullish_min"]:
                    breakout_info["detected"] = True
                    breakout_info["pattern"] = "resistance_breakout"
                    # Calculate strength based on how much above resistance
                    breakout_info["strength"] = (latest["close"] - prev_high) / prev_high

        # Check for bollinger band breakout with strict conditions
        if not breakout_info["detected"] and latest["close"] > latest["bb_upper"]:
            # Must have volume confirmation AND good RSI
            if latest["volume_ratio"] > self.config["volume_spike_threshold"]:
                if self.config["rsi_bullish_min"] < latest.get("rsi", 50) < self.config["rsi_overbought"]:
                    breakout_info["detected"] = True
                    breakout_info["pattern"] = "bollinger_breakout"
                    # Calculate strength based on distance from upper band
                    breakout_info["strength"] = (latest["close"] - latest["bb_upper"]) / latest["bb_upper"]

        return breakout_info

    def _check_trend_alignment(self, df: pd.DataFrame) -> bool:
        """Check if trend indicators are aligned bullishly"""

        latest = df.iloc[-1]

        # Price above both SMAs
        if latest["close"] > latest["sma_20"] > latest["sma_50"]:
            # SMAs in bullish alignment
            if latest["trend_strength"] > self.config["min_trend_strength"]:
                return True

        return False

    def _check_momentum(self, df: pd.DataFrame) -> dict:
        """Score momentum indicators"""

        score = 0
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # RSI in bullish zone
        if self.config["rsi_bullish_min"] < latest["rsi"] < self.config["rsi_overbought"]:
            score += 5

        # MACD bullish cross
        if latest["macd"] > latest["macd_signal"] and prev["macd"] <= prev["macd_signal"]:
            score += 5

        # Positive momentum
        if latest["momentum"] > 0.05:  # 5% momentum
            score += 5

        # Return as dict for compatibility
        return {"score": score, "strong": score >= 10}  # Consider strong if score >= 10

    def _identify_pattern(self, df: pd.DataFrame) -> str:
        """Identify specific chart patterns"""

        latest = df.iloc[-1]

        # Bull flag
        if self._detect_bull_flag(df):
            return "Bull Flag"

        # Cup and handle
        if self._detect_cup_handle(df):
            return "Cup & Handle"

        # Ascending triangle
        if self._detect_ascending_triangle(df):
            return "Ascending Triangle"

        # Momentum surge
        if latest["momentum"] > 0.10:
            return "Momentum Surge"

        # Volume breakout
        if latest["volume_ratio"] > 3.0:
            return "Volume Breakout"

        return "Bullish Continuation"

    def _detect_bull_flag(self, df: pd.DataFrame) -> bool:
        """Detect bull flag pattern"""

        if len(df) < 20:
            return False

        # Look for strong upward move followed by consolidation
        recent = df.iloc[-20:]

        # Find the peak
        peak_idx = recent["high"].idxmax()
        peak_pos = recent.index.get_loc(peak_idx)

        if peak_pos < 5:  # Peak too recent
            return False

        # Check for consolidation after peak
        post_peak = recent.iloc[peak_pos:]
        consolidation_range = (post_peak["high"].max() - post_peak["low"].min()) / post_peak["close"].mean()

        if consolidation_range < 0.03:  # Less than 3% range
            # Check if breaking out of consolidation
            if recent.iloc[-1]["close"] > post_peak["high"].max() * 0.99:
                return True

        return False

    def _detect_cup_handle(self, df: pd.DataFrame) -> bool:
        """Detect cup and handle pattern"""
        # Simplified detection - would need more sophisticated logic in production
        return False

    def _detect_ascending_triangle(self, df: pd.DataFrame) -> bool:
        """Detect ascending triangle pattern"""

        if len(df) < 30:
            return False

        recent = df.iloc[-30:]

        # Check for flat resistance
        highs = recent["high"].values
        resistance_level = np.mean(highs[-5:])
        resistance_flat = np.std(highs[-5:]) / resistance_level < 0.01

        # Check for rising support
        lows = recent["low"].values
        support_trend = np.polyfit(range(len(lows)), lows, 1)[0]

        if resistance_flat and support_trend > 0:
            # Check for breakout
            if recent.iloc[-1]["close"] > resistance_level * 1.01:
                return True

        return False

    def _check_risk_criteria(self, df: pd.DataFrame) -> bool:
        """Check if setup meets risk management criteria"""

        latest = df.iloc[-1]

        # Volatility check
        if latest["volatility"] > self.config["max_volatility"]:
            logger.debug(f"Volatility too high: {latest['volatility']:.2%}")
            return False

        # Volume check
        volume_usd = latest["volume"] * latest["close"]
        if volume_usd < self.config["min_volume_usd"]:
            logger.debug(f"Volume too low: ${volume_usd:,.0f}")
            return False

        # Not extremely overbought
        if latest["rsi"] > 80:
            logger.debug(f"RSI too high: {latest['rsi']:.1f}")
            return False

        return True

    def _calculate_stop_loss(self, df: pd.DataFrame) -> float:
        """Calculate stop loss for swing trade"""

        latest = df.iloc[-1]

        # Use ATR-based stop
        atr_stop = latest["close"] - (2 * latest["atr"])

        # Use recent support
        support_stop = latest["support"]

        # Use SMA as stop
        sma_stop = latest["sma_20"]

        # Take the highest (closest to entry) for tighter risk
        stop_loss = max(atr_stop, support_stop, sma_stop)

        # Ensure minimum 3% stop
        min_stop = latest["close"] * 0.97

        return max(stop_loss, min_stop)

    def _calculate_take_profit(self, df: pd.DataFrame) -> float:
        """Calculate take profit target for swing trade"""

        latest = df.iloc[-1]

        # Base target on ATR
        atr_target = latest["close"] + (3 * latest["atr"])

        # Use measured move
        recent_range = df.iloc[-20:]["high"].max() - df.iloc[-20:]["low"].min()
        measured_target = latest["close"] + recent_range

        # Average the targets
        take_profit = (atr_target + measured_target) / 2

        # Ensure minimum 5% target
        min_target = latest["close"] * 1.05

        return max(take_profit, min_target)

    def _calculate_size_multiplier(self, score: int) -> float:
        """Calculate position size multiplier based on setup score"""

        if score >= 80:
            return 1.5
        elif score >= 70:
            return 1.3
        elif score >= 60:
            return 1.1
        else:
            return 1.0

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_macd(self, prices: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate MACD"""
        exp1 = prices.ewm(span=12, adjust=False).mean()
        exp2 = prices.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        hist = macd - signal
        return macd, signal, hist

    def _calculate_bollinger_bands(
        self, prices: pd.Series, period: int = 20, std: int = 2
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate Bollinger Bands"""
        middle = prices.rolling(window=period).mean()
        std_dev = prices.rolling(window=period).std()
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)
        return upper, middle, lower

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        high_low = df["high"] - df["low"]
        high_close = abs(df["high"] - df["close"].shift())
        low_close = abs(df["low"] - df["close"].shift())

        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        atr = true_range.rolling(window=period).mean()

        return atr

    async def _fetch_ohlc_data(self, symbol: str) -> Optional[List[Dict]]:
        """Fetch OHLC data from database using HybridDataFetcher"""
        try:
            # Get last 100 hours of 1-hour data using the fast views
            data = await self.fetcher.get_recent_data(symbol, hours=100, timeframe="1h")

            if data:
                # Data is already in chronological order from HybridDataFetcher
                return data
            else:
                return None

        except Exception as e:
            logger.error(f"Error fetching OHLC data for {symbol}: {e}")
            return None
