"""
DCA Strategy Setup Detector

Identifies opportunities for Dollar Cost Averaging (DCA) entries:
- Detects 5%+ drops from recent highs
- Filters for adequate volume/liquidity
- Checks BTC market regime
- Prepares data for ML filtering
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger
from src.data.hybrid_fetcher import HybridDataFetcher


class DCADetector:
    """Detects DCA setup opportunities in crypto markets."""

    def __init__(self, config_or_client):
        """
        Initialize DCA Detector.

        Args:
            config_or_client: Either a config dict or Supabase client for database operations
        """
        # Check if it's a dict (config) or a client object
        if isinstance(config_or_client, dict):
            # It's a config dict, use it directly
            self.config = config_or_client
            self.supabase = None
        else:
            # It's a supabase client
            self.supabase = config_or_client
            self.config = self._load_strategy_config()

        # Initialize the hybrid fetcher for fast OHLC data access
        self.fetcher = HybridDataFetcher()

    def _load_strategy_config(self) -> Dict:
        """Load DCA strategy configuration from database."""
        # Default configuration (Custom balanced approach - moderate settings)
        default_config = {
            "price_drop_threshold": -4.0,  # Changed from -5.0 (moderate adjustment)
            "timeframe": "4h",
            "volume_filter": "above_average",
            "btc_regime_filter": ["BULL", "NEUTRAL"],
            "grid_levels": 5,
            "grid_spacing": 1.0,
            "base_size": 100,
            "take_profit": 10.0,
            "stop_loss": -8.0,
            "time_exit_hours": 72,
            "ml_confidence_threshold": 0.60,
            "volume_requirement_multiplier": 0.85,  # Added: 0.85x average volume (was 1.0x)
        }

        if not self.supabase:
            # Return default configuration if no database client
            return default_config

        try:
            # Try to load from database
            if hasattr(self.supabase, "table"):
                # It's a supabase client
                result = (
                    self.supabase.table("strategy_configs")
                    .select("*")
                    .eq("strategy_name", "DCA")
                    .eq("is_active", True)
                    .execute()
                )
                if result.data:
                    return result.data[0]["parameters"]
            return default_config
        except Exception as e:
            # Don't log error if it's just a missing table method
            if "'dict' object has no attribute 'table'" not in str(e):
                logger.error(f"Error loading DCA config: {e}")
            return default_config

    def detect_setups(self, symbols: Optional[List[str]] = None) -> List[Dict]:
        """
        Detect DCA setup opportunities across symbols.

        Args:
            symbols: List of symbols to check (None = all active symbols)

        Returns:
            List of detected setups with details
        """
        setups = []

        if symbols is None:
            symbols = self._get_active_symbols()

        # Get current BTC regime
        btc_regime = self._get_btc_regime()

        # Check if market conditions allow DCA
        if btc_regime not in self.config.get("btc_regime_filter", ["BULL", "NEUTRAL"]):
            logger.info(f"Skipping DCA detection - BTC regime is {btc_regime}")
            return setups

        for symbol in symbols:
            setup = self._check_symbol_for_setup(symbol, btc_regime)
            if setup:
                setups.append(setup)

        logger.info(f"Detected {len(setups)} DCA setups out of {len(symbols)} symbols")
        return setups

    def _check_symbol_for_setup(self, symbol: str, btc_regime: str) -> Optional[Dict]:
        """
        Check if a symbol has a valid DCA setup.

        Args:
            symbol: Cryptocurrency symbol
            btc_regime: Current BTC market regime

        Returns:
            Setup details if valid, None otherwise
        """
        try:
            # Get recent price data (last 24 hours)
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=24)

            price_data = self._get_price_data(symbol, start_time, end_time)

            if price_data is None or len(price_data) < 100:
                return None

            # Calculate metrics
            current_price = price_data["price"].iloc[-1]
            high_4h = (
                price_data["price"].rolling(window=240).max().iloc[-1]
            )  # 4 hours of minutes
            drop_pct = ((current_price - high_4h) / high_4h) * 100

            # Check if drop meets threshold
            if drop_pct > self.config["price_drop_threshold"]:
                # Check volume filter
                if not self._check_volume_filter(price_data):
                    return None

                # Calculate support levels
                support_levels = self._calculate_support_levels(price_data)

                # Prepare setup data
                setup = {
                    "strategy_name": "DCA",
                    "symbol": symbol,
                    "detected_at": datetime.now(),
                    "setup_price": current_price,
                    "setup_data": {
                        "drop_pct": drop_pct,
                        "high_4h": high_4h,
                        "support_levels": support_levels,
                        "btc_regime": btc_regime,
                        "volume_avg_ratio": self._calculate_volume_ratio(price_data),
                        "rsi": self._calculate_rsi_series(price_data["price"]),
                    },
                }

                logger.info(
                    f"DCA setup detected for {symbol}: {drop_pct:.2f}% drop from {high_4h:.2f}"
                )
                return setup

        except Exception as e:
            logger.error(f"Error checking {symbol} for DCA setup: {e}")

        return None

    async def _get_price_data(
        self, symbol: str, start_time: datetime, end_time: datetime
    ) -> Optional[pd.DataFrame]:
        """Get price data for a symbol using HybridDataFetcher."""
        try:
            # Calculate hours for the fetcher
            hours = int((end_time - start_time).total_seconds() / 3600)

            # Use HybridDataFetcher for fast access
            result_data = await self.fetcher.get_recent_data(symbol, hours, "15m")

            if result_data:
                # Convert OHLC to price format
                price_data = []
                for record in result_data:
                    if (
                        record["timestamp"] >= start_time.isoformat()
                        and record["timestamp"] <= end_time.isoformat()
                    ):
                        price_data.append(
                            {
                                "timestamp": record["timestamp"],
                                "price": record["close"],
                                "volume": record.get("volume", 0),
                            }
                        )

                if price_data:
                    df = pd.DataFrame(price_data)
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
                    df = df.set_index("timestamp")
                    return df

        except Exception as e:
            logger.error(f"Error fetching price data for {symbol}: {e}")

        return None

    def _check_volume_filter(self, price_data: pd.DataFrame) -> bool:
        """Check if volume meets requirements."""
        if self.config["volume_filter"] == "above_average":
            recent_volume = price_data["volume"].iloc[-60:].mean()  # Last hour
            avg_volume = price_data["volume"].mean()
            # Use configurable volume requirement multiplier (default 0.85)
            volume_multiplier = self.config.get("volume_requirement_multiplier", 0.85)
            return (
                recent_volume > avg_volume * volume_multiplier
            )  # Now 85% of average (was 80%)
        return True

    def _calculate_support_levels(self, price_data: pd.DataFrame) -> List[float]:
        """Calculate support levels for grid placement."""
        prices = price_data["price"].values

        # Simple support: recent lows
        support_levels = []

        # 1-hour low
        support_levels.append(prices[-60:].min())

        # 4-hour low
        if len(prices) >= 240:
            support_levels.append(prices[-240:].min())

        # 24-hour low
        support_levels.append(prices.min())

        # Remove duplicates and sort
        support_levels = sorted(list(set(support_levels)))

        return support_levels

    def _calculate_volume_ratio(self, price_data: pd.DataFrame) -> float:
        """Calculate current volume vs average."""
        recent_volume = price_data["volume"].iloc[-60:].mean()
        avg_volume = price_data["volume"].mean()
        return recent_volume / avg_volume if avg_volume > 0 else 1.0

    def _calculate_rsi_series(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate RSI indicator from pandas Series."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return rsi.iloc[-1] if not rsi.empty else 50.0

    def _get_btc_regime(self) -> str:
        """Get current BTC market regime."""
        try:
            # Get latest regime from database
            result = (
                self.supabase.client.table("market_regimes")
                .select("btc_regime")
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )

            if result.data:
                return result.data[0]["btc_regime"]

            # If no regime data, calculate it
            return self._calculate_btc_regime()

        except Exception as e:
            logger.error(f"Error getting BTC regime: {e}")
            return "NEUTRAL"

    def _calculate_btc_regime(self) -> str:
        """Calculate current BTC regime based on price action."""
        try:
            # Get BTC price data for last 7 days
            end_time = datetime.now()
            start_time = end_time - timedelta(days=7)

            btc_data = self._get_price_data("BTC", start_time, end_time)

            if btc_data is None or len(btc_data) < 1000:
                return "NEUTRAL"

            current_price = btc_data["price"].iloc[-1]

            # Calculate SMAs only if we have enough data
            if len(btc_data) >= 1200:
                sma_20h = (
                    btc_data["price"].rolling(window=1200).mean().iloc[-1]
                )  # 20 hours
            else:
                sma_20h = btc_data["price"].mean()

            if len(btc_data) >= 3000:
                sma_50h = (
                    btc_data["price"].rolling(window=3000).mean().iloc[-1]
                )  # 50 hours
            else:
                sma_50h = btc_data["price"].mean()

            # Simple regime detection
            if current_price > sma_20h > sma_50h:
                regime = "BULL"
            elif current_price < sma_20h < sma_50h:
                regime = "BEAR"
            elif (
                current_price / btc_data["price"].iloc[-1440]
            ) < 0.9:  # 10% drop in 24h
                regime = "CRASH"
            else:
                regime = "NEUTRAL"

            # Store regime in database
            self._store_btc_regime(regime, current_price)

            return regime

        except Exception as e:
            logger.error(f"Error calculating BTC regime: {e}")
            return "NEUTRAL"

    def _store_btc_regime(self, regime: str, btc_price: float):
        """Store BTC regime in database."""
        try:
            data = {
                "timestamp": datetime.now().isoformat(),
                "btc_regime": regime,
                "btc_price": btc_price,
                "btc_trend_strength": 0.5,  # Placeholder
                "market_fear_greed": 50,  # Placeholder - would integrate Fear & Greed API
                "total_market_cap": 2000000000000,  # Placeholder
            }

            self.supabase.client.table("market_regimes").insert(data).execute()

        except Exception as e:
            logger.error(f"Error storing BTC regime: {e}")

    def _get_active_symbols(self) -> List[str]:
        """Get list of symbols with sufficient data."""
        try:
            # Get distinct symbols that have data in the last hour
            one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()

            # Query for symbols with recent data
            result = (
                self.supabase.client.table("price_data")
                .select("symbol")
                .gte("timestamp", one_hour_ago)
                .execute()
            )

            if result.data:
                # Get unique symbols
                symbols = list(set(row["symbol"] for row in result.data))
                return symbols[:20]  # Limit to 20 symbols for testing

            # Fallback to default list
            return [
                "BTC",
                "ETH",
                "SOL",
                "ADA",
                "DOT",
                "AVAX",
                "LINK",
                "UNI",
                "ATOM",
                "NEAR",
            ]

        except Exception as e:
            logger.warning(f"Error getting active symbols, using defaults: {e}")
            return ["BTC", "ETH", "SOL", "ADA", "DOT"]

    def detect_setup(self, symbol: str, data: List[Dict]) -> Optional[Dict]:
        """
        Detect DCA setup for a single symbol.

        Args:
            symbol: Symbol to check
            data: OHLC data for the symbol

        Returns:
            Setup dictionary if detected, None otherwise
        """
        if not data or len(data) < 20:
            return None

        # Get latest price and calculate metrics
        latest = data[-1]
        current_price = latest.get("close", 0)

        # Calculate 4-hour high
        lookback_bars = min(16, len(data))  # 16 bars of 15min = 4 hours
        recent_data = data[-lookback_bars:]
        high_4h = max(bar.get("high", 0) for bar in recent_data)

        # Calculate drop percentage
        if high_4h > 0:
            drop_pct = ((current_price - high_4h) / high_4h) * 100
        else:
            return None

        # Check if this meets DCA criteria (using updated threshold)
        drop_threshold = self.config.get(
            "price_drop_threshold", -4.0
        )  # Use correct config key
        if drop_pct > drop_threshold:
            return None

        # Calculate RSI
        prices = [bar.get("close", 0) for bar in data[-14:]]
        rsi = self._calculate_rsi(prices) if len(prices) >= 14 else 50

        # Volume check
        recent_volume = sum(bar.get("volume", 0) for bar in recent_data) / len(
            recent_data
        )
        avg_volume = sum(bar.get("volume", 0) for bar in data) / len(data)
        volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1

        # Create setup
        setup = {
            "symbol": symbol,
            "detected_at": latest.get("timestamp"),
            "price": current_price,
            "drop_pct": drop_pct,
            "high_4h": high_4h,
            "rsi": rsi,
            "volume_ratio": volume_ratio,
            "confidence": 0.5,  # Base confidence, ML will adjust
            "position_size_multiplier": 1.0,  # Default multiplier, can be adjusted by ML/market conditions
            "score": 50,  # Default score for consistency with swing detector
        }

        return setup

    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI from price list"""
        if len(prices) < period:
            return 50.0

        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def save_setup(self, setup: Dict) -> Optional[int]:
        """
        Save detected setup to database.

        Args:
            setup: Setup details dictionary

        Returns:
            Setup ID if saved successfully
        """
        try:
            result = (
                self.supabase.client.table("strategy_setups").insert(setup).execute()
            )

            if result.data:
                setup_id = result.data[0]["setup_id"]
                logger.info(f"Saved DCA setup {setup_id} for {setup['symbol']}")
                return setup_id

        except Exception as e:
            logger.error(f"Error saving setup: {e}")

        return None
