"""
Strategy Manager for orchestrating multiple trading strategies
Handles DCA and Swing strategies with conflict resolution and capital allocation
Based on MASTER_PLAN.md specifications
"""

import asyncio
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from loguru import logger
import json

from src.strategies.dca.detector import DCADetector
from src.strategies.dca.grid import GridCalculator
from src.strategies.dca.executor import DCAExecutor
from src.strategies.swing.detector import SwingDetector
from src.strategies.swing.analyzer import SwingAnalyzer
from src.strategies.channel.detector import ChannelDetector
from src.strategies.channel.executor import ChannelExecutor
from src.strategies.regime_detector import RegimeDetector, MarketRegime
from src.strategies.scan_logger import ScanLogger
from src.analysis.shadow_logger import ShadowLogger
from src.ml.predictor import MLPredictor
from src.strategies.simple_rules import SimpleRules
from src.trading.position_sizer import AdaptivePositionSizer
from src.trading.simple_position_sizer import SimplePositionSizer
from src.config.settings import Settings
import os


class StrategyType(Enum):
    DCA = "DCA"
    SWING = "SWING"
    CHANNEL = "CHANNEL"


class ConflictResolution(Enum):
    HIGHER_CONFIDENCE = "higher_confidence_wins"
    PAUSE_LOWER_PRIORITY = "pause_lower_priority"
    SKIP_BOTH = "skip_both"


@dataclass
class StrategySignal:
    """Represents a trading signal from any strategy"""

    strategy_type: StrategyType
    symbol: str
    confidence: float
    expected_value: float
    required_capital: float
    setup_data: Dict
    timestamp: datetime
    expires_at: datetime
    priority_score: float = 0.0

    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at


@dataclass
class StrategyAllocation:
    """Tracks capital allocation across strategies"""

    total_capital: float
    dca_allocation: float  # Percentage
    swing_allocation: float  # Percentage
    channel_allocation: float  # Percentage
    reserve: float  # Percentage
    dca_used: float = 0.0
    swing_used: float = 0.0
    channel_used: float = 0.0

    @property
    def dca_available(self) -> float:
        return (self.total_capital * self.dca_allocation) - self.dca_used

    @property
    def swing_available(self) -> float:
        return (self.total_capital * self.swing_allocation) - self.swing_used

    @property
    def channel_available(self) -> float:
        return (self.total_capital * self.channel_allocation) - self.channel_used

    @property
    def total_available(self) -> float:
        return self.dca_available + self.swing_available + self.channel_available


class StrategyManager:
    """
    Orchestrates multiple trading strategies based on MASTER_PLAN.md
    """

    def __init__(self, config: Dict, supabase_client=None):
        self.config = config
        self.settings = Settings()
        self.supabase = supabase_client
        
        # Check if ML is enabled (from env or config)
        self.ml_enabled = os.getenv("ML_ENABLED", "true").lower() == "true"
        self.ml_enabled = config.get("ml_enabled", self.ml_enabled)
        
        # Check if shadow testing is enabled
        self.shadow_enabled = os.getenv("SHADOW_TESTING_ENABLED", "true").lower() == "true"
        self.shadow_enabled = config.get("shadow_testing_enabled", self.shadow_enabled)

        # Initialize scan logger for ML learning (only if ML enabled)
        self.scan_logger = ScanLogger(supabase_client) if (supabase_client and self.ml_enabled) else None

        # Initialize shadow logger for parallel testing (only if shadow enabled)
        self.shadow_logger = ShadowLogger(supabase_client) if (supabase_client and self.shadow_enabled) else None

        # Initialize strategy components
        self.dca_detector = DCADetector(config.get("dca_config", {}))
        self.swing_detector = SwingDetector(config.get("swing_config", {}))
        self.swing_analyzer = SwingAnalyzer()  # No config needed
        self.channel_detector = ChannelDetector(config.get("channel_config", {}))
        self.channel_executor = ChannelExecutor(config.get("channel_config", {}))
        self.regime_detector = RegimeDetector(
            enabled=config.get("regime_detection_enabled", True)
        )
        
        # Initialize either ML predictor or simple rules
        if self.ml_enabled:
            self.ml_predictor = MLPredictor(self.settings)
            self.simple_rules = None
            self.position_sizer = AdaptivePositionSizer(config)
            logger.info("✅ ML predictions ENABLED")
        else:
            self.ml_predictor = None
            self.simple_rules = SimpleRules(config)
            self.position_sizer = SimplePositionSizer(config)  # Use simple sizer
            logger.info("❌ ML predictions DISABLED - Using simple rules")
            
        self.grid_calculator = GridCalculator(config.get("dca_config", {}))

        # Capital allocation (from MASTER_PLAN.md - updated for 3 strategies)
        self.allocation = StrategyAllocation(
            total_capital=config.get("total_capital", 1000),
            dca_allocation=config.get("dca_allocation", 0.4),  # 40% for DCA
            swing_allocation=config.get("swing_allocation", 0.3),  # 30% for Swing
            channel_allocation=config.get("channel_allocation", 0.3),  # 30% for Channel
            reserve=config.get("reserve", 0.2),  # Keep 20% in reserve
        )

        # Conflict resolution settings
        self.conflict_resolution = config.get(
            "conflict_resolution",
            {
                "same_coin": ConflictResolution.HIGHER_CONFIDENCE,
                "capital_limit": ConflictResolution.PAUSE_LOWER_PRIORITY,
                "opposing_signals": ConflictResolution.SKIP_BOTH,
            },
        )

        # Active positions and signals
        self.active_positions: Dict[str, StrategySignal] = {}
        self.pending_signals: List[StrategySignal] = []
        self.blocked_symbols: set = set()

        # Performance tracking
        self.strategy_performance = {
            StrategyType.DCA: {"wins": 0, "losses": 0, "total_pnl": 0.0},
            StrategyType.SWING: {"wins": 0, "losses": 0, "total_pnl": 0.0},
            StrategyType.CHANNEL: {"wins": 0, "losses": 0, "total_pnl": 0.0},
        }

        logger.info(
            f"Strategy Manager initialized with ${self.allocation.total_capital} capital"
        )
        logger.info(
            f"Allocation: DCA {self.allocation.dca_allocation:.0%}, Swing {self.allocation.swing_allocation:.0%}, Channel {getattr(self.allocation, 'channel_allocation', 0.3):.0%}"
        )
        logger.info(
            f"Regime Detection: {'Enabled' if self.regime_detector.enabled else 'Disabled'}"
        )

    def update_btc_price(self, price: float, timestamp: Optional[datetime] = None):
        """
        Update BTC price for regime detection

        Args:
            price: Current BTC price
            timestamp: Price timestamp
        """
        self.regime_detector.update_btc_price(price, timestamp)

    async def scan_for_opportunities(self, market_data: Dict) -> List[StrategySignal]:
        """
        Scan market for DCA, Swing, and Channel opportunities
        """
        # Update BTC price if available
        if "BTC" in market_data and market_data["BTC"]:
            btc_data = market_data["BTC"]
            # Check if it's a list or dict
            if isinstance(btc_data, list) and len(btc_data) > 0:
                btc_price = btc_data[-1].get("close", 0)  # Get latest price
            elif isinstance(btc_data, dict):
                btc_price = btc_data.get("close", 0)
            else:
                btc_price = 0

            if btc_price > 0:
                self.update_btc_price(btc_price)

        # Check market regime first
        regime = self.regime_detector.get_market_regime()

        if regime == MarketRegime.PANIC:
            logger.warning("🚨 Market PANIC detected - Stopping all new trades")
            # Could send Slack alert here
            return []  # No new trades during panic

        signals = []

        # Check DCA opportunities
        dca_setups = await self._scan_dca_opportunities(market_data)
        signals.extend(dca_setups)

        # Check Swing opportunities
        swing_setups = await self._scan_swing_opportunities(market_data)
        signals.extend(swing_setups)

        # Check Channel opportunities
        channel_setups = await self._scan_channel_opportunities(market_data)
        signals.extend(channel_setups)

        # Apply regime-based position sizing adjustments
        if regime == MarketRegime.CAUTION:
            logger.warning("⚠️ Market CAUTION - Reducing all positions by 50%")
            for signal in signals:
                signal.required_capital *= 0.5
                if "position_size" in signal.setup_data:
                    signal.setup_data["position_size"] *= 0.5
        elif regime == MarketRegime.EUPHORIA:
            logger.warning(
                "🚀 Market EUPHORIA - Reducing positions by 30% (FOMO protection)"
            )
            for signal in signals:
                signal.required_capital *= 0.7
                if "position_size" in signal.setup_data:
                    signal.setup_data["position_size"] *= 0.7

        # Sort by priority score
        signals.sort(key=lambda x: x.priority_score, reverse=True)

        logger.info(
            f"Found {len(signals)} total opportunities: "
            f"{len(dca_setups)} DCA, {len(swing_setups)} Swing, "
            f"{len(channel_setups)} Channel | Regime: {regime.value}"
        )

        # Flush scan logs to database (only if ML enabled)
        if self.scan_logger:
            self.scan_logger.flush()
            
        # Flush shadow logs (only if shadow enabled)
        if self.shadow_logger:
            self.shadow_logger.flush()

        return signals

    async def _scan_dca_opportunities(self, market_data: Dict) -> List[StrategySignal]:
        """Scan for DCA setups"""
        signals = []
        regime = self.regime_detector.get_market_regime()
        btc_price = (
            self.regime_detector.btc_prices[-1]
            if self.regime_detector.btc_prices
            else 0
        )

        for symbol, data in market_data.items():
            if symbol in self.blocked_symbols:
                # Log blocked symbol
                if self.scan_logger:
                    self.scan_logger.log_scan_decision(
                        symbol=symbol,
                        strategy_name="DCA",
                        decision="SKIP",
                        reason="symbol_blocked",
                        features={},
                        market_regime=regime.value,
                        btc_price=btc_price,
                    )
                continue

            # Check if DCA setup exists
            setup = self.dca_detector.detect_setup(symbol, data)
            if not setup:
                # Log no setup
                if self.scan_logger:
                    features = self._extract_dca_features(data) if data else {}
                    self.scan_logger.log_scan_decision(
                        symbol=symbol,
                        strategy_name="DCA",
                        decision="SKIP",
                        reason="no_setup_detected",
                        features=features,
                        market_regime=regime.value,
                        btc_price=btc_price,
                        thresholds_used={
                            "drop_threshold": self.config.get("dca_config", {}).get(
                                "drop_threshold", -5.0
                            )
                        },
                    )
                continue

            # Get ML prediction or use simple rules
            features = {}
            if self.ml_enabled:
                features = self._extract_dca_features(data)
                ml_result = self.ml_predictor.predict_dca(features)
            else:
                # Use simple rules instead of ML
                simple_setup = self.simple_rules.check_dca_setup(symbol, data)
                if not simple_setup:
                    continue
                ml_result = self.simple_rules.predict_dca({})  # Fake ML format

            # Check confidence threshold (skip if using simple rules)
            min_confidence = self.config.get("min_confidence", 0.60) if self.ml_enabled else 0.0
            if ml_result["confidence"] < min_confidence:
                # Log low confidence near-miss (only if ML enabled and scan logger exists)
                if self.scan_logger and self.ml_enabled:
                    decision = (
                        "NEAR_MISS"
                        if ml_result["confidence"] > (min_confidence * 0.8)
                        else "SKIP"
                    )
                    self.scan_logger.log_scan_decision(
                        symbol=symbol,
                        strategy_name="DCA",
                        decision=decision,
                        reason=f'confidence_too_low ({ml_result["confidence"]:.3f} < {min_confidence})',
                        features=features,
                        setup_data=setup,
                        ml_confidence=ml_result["confidence"],
                        ml_predictions=ml_result,
                        market_regime=regime.value,
                        btc_price=btc_price,
                        thresholds_used={"min_confidence": min_confidence},
                    )
                continue

            # Calculate expected value
            expected_value = self._calculate_expected_value(
                win_prob=ml_result["win_probability"],
                expected_profit=ml_result["optimal_take_profit"],
                expected_loss=ml_result["optimal_stop_loss"],
                confidence=ml_result["confidence"],
            )

            # Determine position size
            base_size = self.config.get("dca_position_size", 100)
            position_size = self.position_sizer.calculate_position_size(
                symbol=symbol,
                portfolio_value=self.allocation.dca_available,
                market_data={"confidence": ml_result["confidence"]},
                ml_confidence=ml_result["confidence"],
            )

            # Log successful signal
            if self.scan_logger:
                self.scan_logger.log_scan_decision(
                    symbol=symbol,
                    strategy_name="DCA",
                    decision="TAKE",
                    reason="all_conditions_met",
                    features=features,
                    setup_data=setup,
                    ml_confidence=ml_result["confidence"],
                    ml_predictions=ml_result,
                    market_regime=regime.value,
                    btc_price=btc_price,
                    thresholds_used={
                        "min_confidence": self.config.get("min_confidence", 0.60)
                    },
                    proposed_position_size=position_size,
                    proposed_capital=position_size,
                )

            # Create signal
            signal = StrategySignal(
                strategy_type=StrategyType.DCA,
                symbol=symbol,
                confidence=ml_result["confidence"],
                expected_value=expected_value,
                required_capital=position_size * 5,  # For 5-level grid
                setup_data={
                    "setup": setup,
                    "ml_result": ml_result,
                    "position_size": position_size,
                },
                timestamp=datetime.now(),
                expires_at=datetime.now() + timedelta(minutes=15),
                priority_score=self._calculate_priority_score(
                    StrategyType.DCA, expected_value, ml_result["confidence"]
                ),
            )

            signals.append(signal)

        return signals

    async def _scan_swing_opportunities(
        self, market_data: Dict
    ) -> List[StrategySignal]:
        """Scan for Swing setups"""
        signals = []
        
        # Generate market conditions for swing analyzer
        market_conditions = self._generate_market_conditions(market_data)

        for symbol, data in market_data.items():
            if symbol in self.blocked_symbols:
                continue

            # Check if Swing setup exists (complex detector first)
            setup = self.swing_detector.detect_setup(symbol, data)
            
            # If complex detector didn't find anything, try SimpleRules as fallback
            if not setup and not self.ml_enabled:
                simple_setup = self.simple_rules.check_swing_setup(symbol, data)
                if simple_setup:
                    # Convert SimpleRules format to standard setup format
                    setup = {
                        "symbol": symbol,
                        "detected_at": datetime.now().isoformat(),
                        "price": simple_setup.get("entry_price", 0),
                        "breakout_strength": simple_setup.get("breakout_pct", 0) / 100,
                        "volume_surge": simple_setup.get("volume_surge", 1),
                        "momentum_score": 0.5,
                        "pattern": "simple_breakout",
                        "confidence": simple_setup.get("confidence", 0.5),
                        "position_size_multiplier": 1.0,  # Default multiplier
                        "score": 50,  # Default score for simple setups
                        "from_simple_rules": True
                    }
            
            if not setup:
                continue

            # Analyze the setup with market conditions
            analysis = self.swing_analyzer.analyze_setup(setup, market_conditions)

            # Get ML prediction or use confidence from detector
            if self.ml_enabled:
                features = self._extract_swing_features(data, setup)
                ml_result = self.ml_predictor.predict_swing(features)
                min_confidence = self.config.get("min_confidence", 0.65)
            else:
                # Use confidence from the detector (already calculated)
                ml_result = {
                    "confidence": setup.get("confidence", 0.5),
                    "breakout_success_probability": setup.get("confidence", 0.5),
                    "expected_hold_days": 3,
                    "expected_profit_pct": 5.0
                }
                min_confidence = self.config.get("min_confidence_no_ml", 0.45)  # Lower threshold without ML

            if ml_result["confidence"] < min_confidence:
                continue

            # Calculate expected value
            expected_value = self._calculate_expected_value(
                win_prob=ml_result["breakout_success_probability"],
                expected_profit=analysis["risk_reward"]["potential_profit"],
                expected_loss=analysis["risk_reward"]["potential_loss"],
                confidence=ml_result["confidence"],
            )

            # Determine position size
            base_size = self.config.get("swing_position_size", 200)
            position_size = self.position_sizer.calculate_position_size(
                symbol=symbol,
                portfolio_value=self.allocation.swing_available,
                market_data={"confidence": ml_result["confidence"]},
                ml_confidence=ml_result["confidence"],
            )

            # Create signal
            signal = StrategySignal(
                strategy_type=StrategyType.SWING,
                symbol=symbol,
                confidence=ml_result["confidence"],
                expected_value=expected_value,
                required_capital=position_size,
                setup_data={
                    "setup": setup,
                    "analysis": analysis,
                    "ml_result": ml_result,
                    "position_size": position_size,
                },
                timestamp=datetime.now(),
                expires_at=datetime.now()
                + timedelta(minutes=5),  # Shorter expiry for momentum
                priority_score=self._calculate_priority_score(
                    StrategyType.SWING, expected_value, ml_result["confidence"]
                ),
            )

            signals.append(signal)

        return signals

    async def _scan_channel_opportunities(
        self, market_data: Dict
    ) -> List[StrategySignal]:
        """Scan for Channel trading setups"""
        signals = []

        for symbol, data in market_data.items():
            if symbol in self.blocked_symbols:
                continue

            # Check if Channel exists (complex detector first)
            channel = self.channel_detector.detect_channel(symbol, data)
            signal_type = None
            targets = None
            current_price = data[0]["close"] if data else 0
            
            if channel and channel.is_valid:
                # Get trading signal from channel
                signal_type = self.channel_detector.get_trading_signal(channel)
                if signal_type:
                    # Calculate targets
                    targets = self.channel_detector.calculate_targets(
                        channel, current_price, signal_type
                    )
            
            # If complex detector didn't find anything, try SimpleRules as fallback
            if (not channel or not signal_type) and not self.ml_enabled:
                simple_setup = self.simple_rules.check_channel_setup(symbol, data)
                if simple_setup and simple_setup.get("signal_type") == "BUY":
                    # Create a simple channel object for compatibility
                    from src.strategies.channel.detector import Channel
                    channel = Channel(
                        symbol=symbol,
                        upper_line=simple_setup.get("channel_high", current_price * 1.05),
                        lower_line=simple_setup.get("channel_low", current_price * 0.95),
                        slope=0,  # Assume horizontal
                        width=(simple_setup.get("channel_high", 0) - simple_setup.get("channel_low", 0)) / simple_setup.get("channel_low", 1) if simple_setup.get("channel_low", 0) > 0 else 0.05,
                        touches_upper=2,  # Minimum viable
                        touches_lower=2,  # Minimum viable
                        strength=0.6,  # Moderate strength
                        start_time=datetime.now() - timedelta(days=5),
                        end_time=datetime.now(),
                        current_position=simple_setup.get("position", 0.5)
                    )
                    signal_type = "BUY"
                    # Simple targets
                    targets = {
                        "take_profit": simple_setup.get("channel_high", current_price * 1.05),
                        "stop_loss": simple_setup.get("channel_low", current_price * 0.95) * 0.99,
                        "take_profit_pct": 5.0,
                        "stop_loss_pct": 2.0,
                        "risk_reward": 2.5
                    }
            
            if not channel or not signal_type:
                continue

            # Check risk/reward
            if targets and targets.get("risk_reward", 0) < self.config.get("min_risk_reward", 1.5):
                continue

            # Calculate confidence
            if self.ml_enabled:
                # For now, use channel strength as confidence (ML for channels not yet implemented)
                confidence = channel.strength
                min_confidence = self.config.get("min_confidence", 0.60)
            else:
                # Use confidence scoring from detector
                confidence = self.channel_detector.calculate_confidence_without_ml(channel, signal_type)
                min_confidence = self.config.get("min_confidence_no_ml", 0.45)  # Lower threshold without ML

            if confidence < min_confidence:
                continue

            # Calculate expected value
            expected_value = self._calculate_expected_value(
                win_prob=confidence,  # Use channel strength as win probability
                expected_profit=targets["take_profit_pct"],
                expected_loss=targets["stop_loss_pct"],
                confidence=confidence,
            )

            # Determine position size
            position_size = self.position_sizer.calculate_position_size(
                symbol=symbol,
                portfolio_value=self.allocation.channel_available,
                market_data={"confidence": confidence},
                ml_confidence=confidence,
            )

            # Create signal
            signal = StrategySignal(
                strategy_type=StrategyType.CHANNEL,
                symbol=symbol,
                confidence=confidence,
                expected_value=expected_value,
                required_capital=position_size,
                setup_data={
                    "channel": channel,
                    "signal_type": signal_type,
                    "targets": targets,
                    "position_size": position_size,
                },
                timestamp=datetime.now(),
                expires_at=datetime.now()
                + timedelta(minutes=30),  # Channels are more stable
                priority_score=self._calculate_priority_score(
                    StrategyType.CHANNEL, expected_value, confidence
                ),
            )

            signals.append(signal)

        return signals

    def resolve_conflicts(self, signals: List[StrategySignal]) -> List[StrategySignal]:
        """
        Resolve conflicts between signals based on MASTER_PLAN.md rules
        """
        resolved_signals = []
        symbol_signals = {}

        # Group signals by symbol
        for signal in signals:
            if signal.symbol not in symbol_signals:
                symbol_signals[signal.symbol] = []
            symbol_signals[signal.symbol].append(signal)

        # Resolve conflicts for each symbol
        for symbol, symbol_signal_list in symbol_signals.items():
            if len(symbol_signal_list) == 1:
                resolved_signals.append(symbol_signal_list[0])
            else:
                # Multiple signals for same symbol - apply conflict resolution
                resolution = self._resolve_symbol_conflict(symbol_signal_list)
                if resolution:
                    resolved_signals.append(resolution)

        # Check capital constraints
        resolved_signals = self._apply_capital_constraints(resolved_signals)

        return resolved_signals

    def _resolve_symbol_conflict(
        self, signals: List[StrategySignal]
    ) -> Optional[StrategySignal]:
        """Resolve conflict between multiple signals for same symbol"""

        # Check if signals are opposing (one buy, one sell - not applicable here)
        # In our case, both DCA and Swing are buy strategies

        # Apply resolution strategy
        resolution_type = self.conflict_resolution.get(
            "same_coin", ConflictResolution.HIGHER_CONFIDENCE
        )

        if resolution_type == ConflictResolution.HIGHER_CONFIDENCE:
            # Return signal with highest confidence
            return max(signals, key=lambda x: x.confidence)

        elif resolution_type == ConflictResolution.SKIP_BOTH:
            # Skip both signals
            logger.warning(f"Skipping conflicting signals for {signals[0].symbol}")
            return None

        else:
            # Default to higher confidence
            return max(signals, key=lambda x: x.confidence)

    def _apply_capital_constraints(
        self, signals: List[StrategySignal]
    ) -> List[StrategySignal]:
        """Apply capital allocation constraints"""
        approved_signals = []
        temp_dca_used = self.allocation.dca_used
        temp_swing_used = self.allocation.swing_used
        temp_channel_used = self.allocation.channel_used

        for signal in signals:
            if signal.strategy_type == StrategyType.DCA:
                available = (
                    self.allocation.total_capital * self.allocation.dca_allocation
                ) - temp_dca_used
                if signal.required_capital <= available:
                    approved_signals.append(signal)
                    temp_dca_used += signal.required_capital
                else:
                    logger.warning(
                        f"Insufficient DCA capital for {signal.symbol}: "
                        f"needs ${signal.required_capital:.2f}, have ${available:.2f}"
                    )

            elif signal.strategy_type == StrategyType.SWING:
                available = (
                    self.allocation.total_capital * self.allocation.swing_allocation
                ) - temp_swing_used
                if signal.required_capital <= available:
                    approved_signals.append(signal)
                    temp_swing_used += signal.required_capital
                else:
                    logger.warning(
                        f"Insufficient Swing capital for {signal.symbol}: "
                        f"needs ${signal.required_capital:.2f}, have ${available:.2f}"
                    )

            elif signal.strategy_type == StrategyType.CHANNEL:
                available = (
                    self.allocation.total_capital * self.allocation.channel_allocation
                ) - temp_channel_used
                if signal.required_capital <= available:
                    approved_signals.append(signal)
                    temp_channel_used += signal.required_capital
                else:
                    logger.warning(
                        f"Insufficient Channel capital for {signal.symbol}: "
                        f"needs ${signal.required_capital:.2f}, have ${available:.2f}"
                    )

        return approved_signals

    def _calculate_expected_value(
        self,
        win_prob: float,
        expected_profit: float,
        expected_loss: float,
        confidence: float,
    ) -> float:
        """Calculate risk-adjusted expected value"""
        raw_ev = (win_prob * expected_profit) - ((1 - win_prob) * abs(expected_loss))

        # Adjust for confidence
        confidence_adjustment = confidence / 0.60  # Normalize to min confidence

        return raw_ev * confidence_adjustment

    def _calculate_priority_score(
        self, strategy: StrategyType, expected_value: float, confidence: float
    ) -> float:
        """
        Calculate priority score based on MASTER_PLAN.md priority rules:
        1. ML confidence
        2. Strategy performance
        3. Market conditions
        """
        score = 0.0

        # 1. ML confidence (weight: 40%)
        score += confidence * 0.4

        # 2. Strategy performance (weight: 30%)
        perf = self.strategy_performance[strategy]
        win_rate = perf["wins"] / max(perf["wins"] + perf["losses"], 1)
        score += win_rate * 0.3

        # 3. Expected value (weight: 30%)
        ev_normalized = min(max(expected_value / 10, -1), 1)  # Normalize to -1 to 1
        score += ev_normalized * 0.3

        return score

    def _generate_market_conditions(self, market_data: Dict) -> Dict:
        """Generate market conditions from raw market data"""
        
        # Get BTC data if available for market trend
        btc_data = market_data.get("BTC", [])
        btc_trend = 0
        if btc_data and len(btc_data) > 1:
            # Calculate BTC trend from last 24 hours
            btc_close_24h_ago = btc_data[-24]["close"] if len(btc_data) >= 24 else btc_data[0]["close"]
            btc_close_now = btc_data[-1]["close"]
            btc_trend = (btc_close_now - btc_close_24h_ago) / btc_close_24h_ago
        
        # Calculate market breadth (percentage of symbols up)
        up_count = 0
        total_count = 0
        for symbol, data in market_data.items():
            if data and len(data) > 1:
                total_count += 1
                if data[-1]["close"] > data[0]["close"]:
                    up_count += 1
        
        market_breadth = (up_count / total_count * 100) if total_count > 0 else 50
        
        # Mock fear/greed index (would normally come from external source)
        # For now, derive from BTC trend and market breadth
        fear_greed = 50  # Neutral default
        if btc_trend > 0.05 and market_breadth > 60:
            fear_greed = 70  # Greed
        elif btc_trend < -0.05 and market_breadth < 40:
            fear_greed = 30  # Fear
        
        return {
            "btc_trend": btc_trend,
            "market_breadth": market_breadth,
            "fear_greed_index": fear_greed
        }
    
    def _extract_dca_features(self, data: List[Dict]) -> Dict:
        """Extract features for DCA ML prediction"""
        # Calculate features from OHLC data
        if not data or len(data) == 0:
            return {}

        # Get the latest data point
        latest = data[-1] if isinstance(data, list) else data
        current_price = latest.get("close", 0)

        # Calculate recent high from available data
        lookback = min(20, len(data)) if isinstance(data, list) else 1
        if isinstance(data, list) and lookback > 0:
            recent_data = data[-lookback:]
            recent_high = max(d.get("high", 0) for d in recent_data)
        else:
            recent_high = current_price

        price_drop = (
            (current_price - recent_high) / recent_high * 100 if recent_high > 0 else 0
        )

        return {
            "price_drop": price_drop,
            "rsi": 50,  # Would calculate actual RSI
            "volume_ratio": 1,  # Would calculate actual volume ratio
            "distance_from_support": 0,
            "btc_correlation": 0,
            "market_regime": 0,
        }

    def _extract_swing_features(self, data: List[Dict], setup: Dict) -> Dict:
        """Extract features for Swing ML prediction"""
        # Extract features from OHLC data and setup
        return {
            "breakout_strength": setup.get("breakout_pct", 0),
            "volume_ratio": setup.get("volume_ratio", 1),
            "resistance_cleared": 1,  # Simplified
            "trend_alignment": 1,  # Simplified
            "momentum_score": 0.7,  # Simplified
            "market_regime": 1,  # Bull
        }

    async def execute_signals(self, signals: List[StrategySignal]) -> Dict:
        """Execute approved signals"""
        results = {"executed": [], "failed": [], "skipped": []}

        for signal in signals:
            try:
                if signal.is_expired():
                    results["skipped"].append(
                        {"symbol": signal.symbol, "reason": "expired"}
                    )
                    continue

                if signal.symbol in self.active_positions:
                    results["skipped"].append(
                        {"symbol": signal.symbol, "reason": "position_exists"}
                    )
                    continue

                # Execute based on strategy type
                if signal.strategy_type == StrategyType.DCA:
                    success = await self._execute_dca_signal(signal)
                elif signal.strategy_type == StrategyType.SWING:
                    success = await self._execute_swing_signal(signal)
                else:
                    success = False

                if success:
                    results["executed"].append(signal)
                    self.active_positions[signal.symbol] = signal

                    # Update capital allocation
                    if signal.strategy_type == StrategyType.DCA:
                        self.allocation.dca_used += signal.required_capital
                    else:
                        self.allocation.swing_used += signal.required_capital
                else:
                    results["failed"].append(signal)

            except Exception as e:
                logger.error(f"Error executing signal for {signal.symbol}: {e}")
                results["failed"].append(signal)

        logger.info(
            f"Execution complete: {len(results['executed'])} executed, "
            f"{len(results['failed'])} failed, {len(results['skipped'])} skipped"
        )

        return results

    async def _execute_dca_signal(self, signal: StrategySignal) -> bool:
        """Execute DCA signal"""
        try:
            # Generate grid
            grid = self.grid_calculator.calculate_grid(
                entry_price=signal.setup_data["setup"]["current_price"],
                confidence=signal.confidence,
                ml_predictions=signal.setup_data["ml_result"],
            )

            # Execute through DCA executor (would connect to actual trading)
            logger.info(
                f"Executing DCA grid for {signal.symbol}: "
                f"{len(grid['levels'])} levels, ${signal.required_capital:.2f} total"
            )

            # Here you would call the actual DCA executor
            # For now, return True to indicate success
            return True

        except Exception as e:
            logger.error(f"Failed to execute DCA signal: {e}")
            return False

    async def _execute_swing_signal(self, signal: StrategySignal) -> bool:
        """Execute Swing signal"""
        try:
            # Execute market order for swing trade
            position_size = signal.setup_data["position_size"]
            entry_price = signal.setup_data["setup"]["entry_price"]

            logger.info(
                f"Executing Swing trade for {signal.symbol}: "
                f"${position_size:.2f} at ${entry_price:.2f}"
            )

            # Here you would call the actual trading executor
            # For now, return True to indicate success
            return True

        except Exception as e:
            logger.error(f"Failed to execute Swing signal: {e}")
            return False

    def update_performance(self, symbol: str, pnl: float, is_win: bool):
        """Update strategy performance metrics"""
        if symbol in self.active_positions:
            signal = self.active_positions[symbol]
            strategy = signal.strategy_type

            if is_win:
                self.strategy_performance[strategy]["wins"] += 1
            else:
                self.strategy_performance[strategy]["losses"] += 1

            self.strategy_performance[strategy]["total_pnl"] += pnl

            # Free up capital
            if strategy == StrategyType.DCA:
                self.allocation.dca_used -= signal.required_capital
            elif strategy == StrategyType.SWING:
                self.allocation.swing_used -= signal.required_capital
            elif strategy == StrategyType.CHANNEL:
                self.allocation.channel_used -= signal.required_capital

            # Remove from active positions
            del self.active_positions[symbol]

            logger.info(
                f"Updated {strategy.value} performance: "
                f"Win rate: {self._get_win_rate(strategy):.1%}, "
                f"Total P&L: ${self.strategy_performance[strategy]['total_pnl']:.2f}"
            )

    def _get_win_rate(self, strategy: StrategyType) -> float:
        """Calculate win rate for a strategy"""
        perf = self.strategy_performance[strategy]
        total_trades = perf["wins"] + perf["losses"]
        return perf["wins"] / total_trades if total_trades > 0 else 0.0

    def get_status(self) -> Dict:
        """Get current manager status"""
        return {
            "active_positions": len(self.active_positions),
            "capital_allocation": {
                "dca_used": self.allocation.dca_used,
                "dca_available": self.allocation.dca_available,
                "swing_used": self.allocation.swing_used,
                "swing_available": self.allocation.swing_available,
                "channel_used": self.allocation.channel_used,
                "channel_available": self.allocation.channel_available,
                "total_available": self.allocation.total_available,
            },
            "performance": {
                "dca": {
                    "win_rate": self._get_win_rate(StrategyType.DCA),
                    "total_pnl": self.strategy_performance[StrategyType.DCA][
                        "total_pnl"
                    ],
                },
                "swing": {
                    "win_rate": self._get_win_rate(StrategyType.SWING),
                    "total_pnl": self.strategy_performance[StrategyType.SWING][
                        "total_pnl"
                    ],
                },
                "channel": {
                    "win_rate": self._get_win_rate(StrategyType.CHANNEL),
                    "total_pnl": self.strategy_performance[StrategyType.CHANNEL][
                        "total_pnl"
                    ],
                },
            },
            "blocked_symbols": list(self.blocked_symbols),
        }
