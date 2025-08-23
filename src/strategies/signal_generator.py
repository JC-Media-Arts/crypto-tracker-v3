"""
Real-time Signal Generator

Monitors live OHLC data and generates trading signals:
- Continuously scans for DCA setups
- Triggers ML predictions for detected setups
- Manages signal lifecycle and deduplication
- Integrates with executor for automatic trading
"""

import asyncio
import json
import pickle
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
from pathlib import Path
from loguru import logger
import pandas as pd
import numpy as np

from src.data.supabase_client import SupabaseClient
from src.data.hybrid_fetcher import HybridDataFetcher
from src.strategies.dca.detector import DCADetector
from src.strategies.dca.grid import GridCalculator
from src.strategies.dca.executor import DCAExecutor
from src.trading.position_sizer import AdaptivePositionSizer
from src.ml.predictor import MLPredictor


class SignalStatus(Enum):
    """Signal status enumeration."""

    DETECTED = "DETECTED"
    ANALYZING = "ANALYZING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    EXPIRED = "EXPIRED"


class SignalGenerator:
    """Generates real-time trading signals from market data."""

    def __init__(
        self,
        supabase_client: SupabaseClient,
        config: Optional[Dict] = None,
        auto_execute: bool = False,
    ):
        """
        Initialize Signal Generator.

        Args:
            supabase_client: Database client
            config: Generator configuration
            auto_execute: Whether to automatically execute approved signals
        """
        self.supabase = supabase_client
        self.fetcher = HybridDataFetcher()
        self.config = config or self._default_config()
        self.auto_execute = auto_execute

        # Initialize components
        self.dca_detector = DCADetector(supabase_client)
        self.position_sizer = AdaptivePositionSizer()
        self.grid_calculator = GridCalculator(self.dca_detector.config)

        # ML components (will be loaded lazily)
        self.ml_predictor = None
        self.ml_model = None
        self.scaler = None

        # Executor (optional, for auto-execution)
        self.executor = None
        if auto_execute:
            self.executor = DCAExecutor(
                supabase_client=supabase_client, position_sizer=self.position_sizer
            )

        # Signal tracking
        self.active_signals = {}
        self.processed_symbols = set()  # Prevent duplicate signals
        self.signal_history = []

        # Monitoring control
        self.monitoring_active = False
        self.monitor_task = None

    def _default_config(self) -> Dict:
        """Default generator configuration."""
        return {
            "scan_interval": 60,  # Seconds between scans
            "signal_ttl": 300,  # Signal time-to-live in seconds
            "min_confidence": 0.60,  # Minimum ML confidence
            "max_signals_per_symbol": 1,  # Max concurrent signals per symbol
            "cooldown_period": 3600,  # Cooldown after signal (seconds)
            "symbols_to_monitor": None,  # None = all active symbols
            "max_concurrent_positions": 5,
            "capital_per_position": 100,  # Base capital allocation
            "enable_ml_filtering": True,
            "enable_notifications": True,
        }

    def _load_ml_components(self):
        """Load ML model and scaler."""
        if self.ml_model is not None:
            return  # Already loaded

        try:
            model_dir = Path("models/dca")

            # Load XGBoost model
            model_path = model_dir / "xgboost_multi_output.pkl"
            if model_path.exists():
                with open(model_path, "rb") as f:
                    self.ml_model = pickle.load(f)
                logger.info("Loaded XGBoost multi-output model")
            else:
                logger.warning(f"ML model not found at {model_path}")
                self.config["enable_ml_filtering"] = False
                return

            # Load scaler
            scaler_path = model_dir / "scaler.pkl"
            if scaler_path.exists():
                with open(scaler_path, "rb") as f:
                    self.scaler = pickle.load(f)
                logger.info("Loaded feature scaler")
            else:
                logger.warning(f"Scaler not found at {scaler_path}")
                self.config["enable_ml_filtering"] = False
                return

            # Initialize predictor
            from src.ml.predictor import MLPredictor

            self.ml_predictor = MLPredictor(
                model=self.ml_model, scaler=self.scaler, supabase_client=self.supabase
            )

        except Exception as e:
            logger.error(f"Error loading ML components: {e}")
            self.config["enable_ml_filtering"] = False

    async def start_monitoring(self):
        """Start real-time signal monitoring."""
        logger.info("Starting real-time signal monitoring")
        self.monitoring_active = True

        # Load ML components if enabled
        if self.config["enable_ml_filtering"]:
            self._load_ml_components()

        # Start executor monitoring if auto-execute is enabled
        if self.executor:
            await self.executor.start_monitoring()

        # Start main monitoring loop
        self.monitor_task = asyncio.create_task(self._monitoring_loop())

    async def stop_monitoring(self):
        """Stop signal monitoring."""
        logger.info("Stopping signal monitoring")
        self.monitoring_active = False

        if self.monitor_task:
            await self.monitor_task

        if self.executor:
            await self.executor.stop_monitoring()

    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.monitoring_active:
            try:
                # Scan for new signals
                await self.scan_for_signals()

                # Process pending signals
                await self.process_pending_signals()

                # Clean up expired signals
                self.cleanup_expired_signals()

                # Wait before next scan
                await asyncio.sleep(self.config["scan_interval"])

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.config["scan_interval"])

    async def scan_for_signals(self) -> List[Dict]:
        """
        Scan market for new trading signals.

        Returns:
            List of detected signals
        """
        logger.debug("Scanning for new signals...")
        new_signals = []

        try:
            # Get symbols to monitor
            symbols = self._get_symbols_to_monitor()

            # Filter out symbols with active signals or in cooldown
            available_symbols = [s for s in symbols if not self._is_symbol_blocked(s)]

            if not available_symbols:
                logger.debug("No symbols available for scanning")
                return new_signals

            # Detect DCA setups
            dca_setups = self.dca_detector.detect_setups(available_symbols)

            for setup in dca_setups:
                # Create signal entry
                signal = await self._create_signal(setup)
                if signal:
                    new_signals.append(signal)
                    self.active_signals[signal["signal_id"]] = signal
                    self.processed_symbols.add(setup["symbol"])

                    logger.info(
                        f"New signal detected: {setup['symbol']} "
                        f"({setup['setup_data']['drop_pct']:.1f}% drop)"
                    )

            # TODO: Add swing trading detection here
            # swing_setups = self.swing_detector.detect_setups(available_symbols)

        except Exception as e:
            logger.error(f"Error scanning for signals: {e}")

        return new_signals

    async def _create_signal(self, setup: Dict) -> Optional[Dict]:
        """
        Create a signal entry from a setup.

        Args:
            setup: Setup detection data

        Returns:
            Signal dictionary or None if rejected
        """
        try:
            signal_id = f"{setup['strategy_name']}_{setup['symbol']}_{datetime.now().timestamp():.0f}"

            signal = {
                "signal_id": signal_id,
                "strategy": setup["strategy_name"],
                "symbol": setup["symbol"],
                "status": SignalStatus.DETECTED,
                "detected_at": datetime.now(),
                "expires_at": datetime.now()
                + timedelta(seconds=self.config["signal_ttl"]),
                "setup_data": setup["setup_data"],
                "setup_price": setup["setup_price"],
                "ml_predictions": None,
                "confidence_score": 0.0,
                "grid_config": None,
                "position_size": None,
                "execution_result": None,
            }

            # Apply ML filtering if enabled
            if self.config["enable_ml_filtering"] and self.ml_predictor:
                signal["status"] = SignalStatus.ANALYZING
                ml_result = await self._apply_ml_filtering(signal)

                if not ml_result["approved"]:
                    signal["status"] = SignalStatus.REJECTED
                    signal["rejection_reason"] = ml_result["reason"]
                    logger.debug(f"Signal rejected by ML: {ml_result['reason']}")
                    return None

                signal["ml_predictions"] = ml_result["predictions"]
                signal["confidence_score"] = ml_result["confidence"]
                signal["status"] = SignalStatus.APPROVED
            else:
                # No ML filtering, auto-approve
                signal["status"] = SignalStatus.APPROVED
                signal["confidence_score"] = 0.65  # Default confidence

            return signal

        except Exception as e:
            logger.error(f"Error creating signal: {e}")
            return None

    async def _apply_ml_filtering(self, signal: Dict) -> Dict:
        """
        Apply ML model to filter and enhance signal.

        Args:
            signal: Signal data

        Returns:
            ML filtering result
        """
        try:
            # Get features for ML model
            features = await self._prepare_ml_features(signal)

            if features is None:
                return {
                    "approved": False,
                    "reason": "Could not prepare ML features",
                    "predictions": None,
                    "confidence": 0.0,
                }

            # Make predictions
            predictions = self.ml_predictor.predict(features)

            # Extract confidence (win probability)
            confidence = predictions.get("win_probability", 0.5)

            # Check confidence threshold
            if confidence < self.config["min_confidence"]:
                return {
                    "approved": False,
                    "reason": f"Low confidence: {confidence:.1%}",
                    "predictions": predictions,
                    "confidence": confidence,
                }

            # Check expected value
            expected_value = predictions["take_profit_percent"] * confidence - abs(
                predictions["stop_loss_percent"]
            ) * (1 - confidence)

            if expected_value < 1.0:  # Minimum 1% expected value
                return {
                    "approved": False,
                    "reason": f"Low expected value: {expected_value:.1f}%",
                    "predictions": predictions,
                    "confidence": confidence,
                }

            return {
                "approved": True,
                "reason": "ML approved",
                "predictions": predictions,
                "confidence": confidence,
            }

        except Exception as e:
            logger.error(f"Error in ML filtering: {e}")
            return {
                "approved": False,
                "reason": f"ML error: {str(e)}",
                "predictions": None,
                "confidence": 0.0,
            }

    async def _prepare_ml_features(self, signal: Dict) -> Optional[pd.DataFrame]:
        """
        Prepare features for ML model.

        Args:
            signal: Signal data

        Returns:
            Feature dataframe or None
        """
        try:
            # Get recent OHLC data using HybridDataFetcher
            result_data = await self.fetcher.get_recent_data(
                signal["symbol"], hours=24, timeframe="15m"
            )

            if not result_data or len(result_data) < 20:
                logger.warning(f"Insufficient data for {signal['symbol']}")
                return None

            df = pd.DataFrame(result_data)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.set_index("timestamp").sort_index()

            # Calculate technical indicators
            features = {}

            # Price features
            features["price_change_24h"] = (
                df["close"].iloc[-1] / df["close"].iloc[0] - 1
            ) * 100
            features["high_low_ratio"] = df["high"].iloc[-1] / df["low"].iloc[-1]

            # Volume features
            features["volume_ratio"] = (
                df["volume"].iloc[-4:].mean() / df["volume"].mean()
                if df["volume"].mean() > 0
                else 1.0
            )

            # Volatility
            features["volatility"] = df["close"].pct_change().std() * 100

            # RSI
            features["rsi"] = signal["setup_data"].get("rsi", 50)

            # Market regime (encoded)
            btc_regime = signal["setup_data"].get("btc_regime", "NEUTRAL")
            features["regime_bull"] = 1 if btc_regime == "BULL" else 0
            features["regime_bear"] = 1 if btc_regime == "BEAR" else 0
            features["regime_neutral"] = 1 if btc_regime == "NEUTRAL" else 0

            # Drop magnitude
            features["drop_magnitude"] = abs(signal["setup_data"].get("drop_pct", 0))

            # Support distance
            support_levels = signal["setup_data"].get("support_levels", [])
            if support_levels:
                features["support_distance"] = (
                    (signal["setup_price"] - min(support_levels))
                    / signal["setup_price"]
                    * 100
                )
            else:
                features["support_distance"] = 5.0

            # Time features
            features["hour_of_day"] = datetime.now().hour
            features["day_of_week"] = datetime.now().weekday()

            # Convert to DataFrame
            feature_df = pd.DataFrame([features])

            # Ensure all expected features are present
            expected_features = [
                "price_change_24h",
                "high_low_ratio",
                "volume_ratio",
                "volatility",
                "rsi",
                "regime_bull",
                "regime_bear",
                "regime_neutral",
                "drop_magnitude",
                "support_distance",
                "hour_of_day",
                "day_of_week",
            ]

            for feat in expected_features:
                if feat not in feature_df.columns:
                    feature_df[feat] = 0

            return feature_df[expected_features]

        except Exception as e:
            logger.error(f"Error preparing ML features: {e}")
            return None

    async def process_pending_signals(self):
        """Process approved signals for execution."""
        for signal_id, signal in list(self.active_signals.items()):
            try:
                if signal["status"] != SignalStatus.APPROVED:
                    continue

                # Check if signal has expired
                if datetime.now() > signal["expires_at"]:
                    signal["status"] = SignalStatus.EXPIRED
                    continue

                # Generate grid configuration
                if not signal["grid_config"]:
                    signal["grid_config"] = await self._generate_grid(signal)

                # Calculate position size
                if not signal["position_size"]:
                    signal["position_size"] = await self._calculate_position_size(
                        signal
                    )

                # Execute if auto-execute is enabled
                if self.auto_execute and self.executor:
                    execution_result = await self.executor.execute_grid(
                        symbol=signal["symbol"],
                        grid=signal["grid_config"],
                        ml_predictions=signal["ml_predictions"],
                        setup_data=signal["setup_data"],
                    )

                    signal["execution_result"] = execution_result
                    signal["status"] = SignalStatus.EXECUTED

                    if execution_result["success"]:
                        logger.info(
                            f"Signal executed: {signal['symbol']} "
                            f"position {execution_result['position_id']}"
                        )
                    else:
                        logger.warning(
                            f"Signal execution failed: {execution_result['error']}"
                        )
                else:
                    # Just log the signal for manual execution
                    logger.info(
                        f"Signal ready for execution: {signal['symbol']} "
                        f"${signal['position_size']:.2f} position"
                    )

            except Exception as e:
                logger.error(f"Error processing signal {signal_id}: {e}")

    async def _generate_grid(self, signal: Dict) -> Dict:
        """Generate grid configuration for signal."""
        try:
            # Use ML predictions if available
            if signal["ml_predictions"]:
                # Update config with ML predictions
                grid_config = self.dca_detector.config.copy()
                grid_config["take_profit"] = signal["ml_predictions"][
                    "take_profit_percent"
                ]
                grid_config["stop_loss"] = signal["ml_predictions"]["stop_loss_percent"]

                # Create temporary calculator with ML config
                calculator = GridCalculator(grid_config)
            else:
                calculator = self.grid_calculator

            # Generate grid
            grid = calculator.calculate_grid(
                current_price=signal["setup_price"],
                ml_confidence=signal["confidence_score"],
                support_levels=signal["setup_data"].get("support_levels", []),
                total_capital=signal["position_size"]
                or self.config["capital_per_position"],
            )

            return grid

        except Exception as e:
            logger.error(f"Error generating grid: {e}")
            return {}

    async def _calculate_position_size(self, signal: Dict) -> float:
        """Calculate position size for signal."""
        try:
            # Get market data for position sizing
            market_data = {
                "btc_regime": signal["setup_data"].get("btc_regime", "NEUTRAL"),
                "volatility": signal["setup_data"].get("volatility", 0.03),
                "market_cap_tier": "mid",  # Would need to fetch this
            }

            # Get ML confidence
            ml_confidence = signal["confidence_score"]

            # Calculate adaptive position size
            position_size = self.position_sizer.calculate_position_size(
                symbol=signal["symbol"],
                portfolio_value=self.config["capital_per_position"],
                market_data=market_data,
                ml_confidence=ml_confidence,
                ml_multiplier=(
                    signal.get("ml_predictions", {}).get(
                        "position_size_multiplier", 1.0
                    )
                    if signal.get("ml_predictions")
                    and isinstance(signal.get("ml_predictions"), dict)
                    else 1.0
                ),
            )

            return position_size

        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return self.config["capital_per_position"]

    def _get_symbols_to_monitor(self) -> List[str]:
        """Get list of symbols to monitor."""
        if self.config["symbols_to_monitor"]:
            return self.config["symbols_to_monitor"]

        # Get all active symbols (simplified for now)
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
            "MATIC",
            "ARB",
            "OP",
            "INJ",
            "TIA",
            "SEI",
            "SUI",
            "APT",
            "FTM",
            "ALGO",
        ]

    def _is_symbol_blocked(self, symbol: str) -> bool:
        """Check if symbol is blocked from new signals."""
        # Check if symbol has active signal
        for signal in self.active_signals.values():
            if signal["symbol"] == symbol and signal["status"] in [
                SignalStatus.APPROVED,
                SignalStatus.EXECUTED,
            ]:
                return True

        # Check if symbol is in cooldown
        if symbol in self.processed_symbols:
            # Simple cooldown check (would need timestamp tracking for proper implementation)
            return True

        # Check max concurrent positions
        active_count = sum(
            1
            for s in self.active_signals.values()
            if s["status"] == SignalStatus.EXECUTED
        )
        if active_count >= self.config["max_concurrent_positions"]:
            return True

        return False

    def cleanup_expired_signals(self):
        """Remove expired signals from tracking."""
        expired = []

        for signal_id, signal in self.active_signals.items():
            if signal["status"] == SignalStatus.EXPIRED:
                expired.append(signal_id)
            elif (
                datetime.now() > signal["expires_at"]
                and signal["status"] != SignalStatus.EXECUTED
            ):
                signal["status"] = SignalStatus.EXPIRED
                expired.append(signal_id)

        for signal_id in expired:
            signal = self.active_signals.pop(signal_id)
            self.signal_history.append(signal)

            # Remove from processed symbols after cooldown
            # (simplified - would need proper timestamp tracking)
            if signal["symbol"] in self.processed_symbols:
                self.processed_symbols.remove(signal["symbol"])

        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired signals")

    def get_active_signals(self) -> List[Dict]:
        """Get list of active signals."""
        return [
            {
                "signal_id": s["signal_id"],
                "symbol": s["symbol"],
                "strategy": s["strategy"],
                "status": (
                    s["status"].value
                    if isinstance(s["status"], SignalStatus)
                    else s["status"]
                ),
                "confidence": s["confidence_score"],
                "detected_at": (
                    s["detected_at"].isoformat()
                    if isinstance(s["detected_at"], datetime)
                    else s["detected_at"]
                ),
                "expires_at": (
                    s["expires_at"].isoformat()
                    if isinstance(s["expires_at"], datetime)
                    else s["expires_at"]
                ),
            }
            for s in self.active_signals.values()
        ]

    def get_signal_details(self, signal_id: str) -> Optional[Dict]:
        """Get detailed information about a specific signal."""
        return self.active_signals.get(signal_id)

    async def force_scan(self, symbols: Optional[List[str]] = None) -> List[Dict]:
        """
        Force an immediate scan for signals.

        Args:
            symbols: Specific symbols to scan (None = all)

        Returns:
            List of detected signals
        """
        if symbols:
            # Temporarily override symbols to monitor
            original_symbols = self.config["symbols_to_monitor"]
            self.config["symbols_to_monitor"] = symbols

            signals = await self.scan_for_signals()

            # Restore original config
            self.config["symbols_to_monitor"] = original_symbols
        else:
            signals = await self.scan_for_signals()

        return signals
