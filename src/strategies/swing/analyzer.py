"""
Swing Trading Strategy Analyzer
Analyzes and ranks swing trading opportunities
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class SwingAnalyzer:
    """
    Analyzes swing trading setups and provides:
    - Entry/exit recommendations
    - Position sizing suggestions
    - Risk/reward analysis
    - Market regime consideration
    """

    def __init__(self):
        self.market_regimes = {
            "STRONG_BULL": {"multiplier": 1.5, "min_score": 50},
            "BULL": {"multiplier": 1.2, "min_score": 60},
            "NEUTRAL": {"multiplier": 1.0, "min_score": 70},
            "BEAR": {"multiplier": 0.7, "min_score": 80},
            "STRONG_BEAR": {"multiplier": 0.5, "min_score": 90},
        }

    def analyze_setup(self, setup: Dict, market_data: Dict) -> Dict:
        """
        Analyze a swing trading setup in context of market conditions

        Args:
            setup: Detected swing setup from detector
            market_data: Current market conditions

        Returns:
            Enhanced setup with analysis
        """

        # Determine market regime
        market_regime = self._determine_market_regime(market_data)

        # Calculate risk/reward
        risk_reward = self._calculate_risk_reward(setup)

        # Adjust for market conditions
        adjusted_setup = self._adjust_for_market(setup, market_regime)

        # Calculate expected value
        expected_value = self._calculate_expected_value(adjusted_setup, risk_reward)

        # Generate trade plan
        trade_plan = self._generate_trade_plan(adjusted_setup)

        # Compile analysis
        analysis = {
            **setup,
            "market_regime": market_regime,
            "risk_reward_ratio": risk_reward["ratio"],
            "risk_amount": risk_reward["risk"],
            "reward_amount": risk_reward["reward"],
            "expected_value": expected_value,
            "adjusted_score": adjusted_setup["score"],
            "adjusted_size_multiplier": adjusted_setup["position_size_multiplier"],
            "trade_plan": trade_plan,
            "confidence": self._calculate_confidence(adjusted_setup, market_regime),
            "priority": self._calculate_priority(adjusted_setup, expected_value),
        }

        return analysis

    def rank_opportunities(
        self, setups: List[Dict], portfolio_state: Dict
    ) -> List[Dict]:
        """
        Rank multiple swing opportunities based on various factors

        Args:
            setups: List of analyzed setups
            portfolio_state: Current portfolio state

        Returns:
            Ranked list of opportunities
        """

        # Filter based on portfolio constraints
        filtered = self._filter_by_portfolio(setups, portfolio_state)

        # Score each opportunity
        for setup in filtered:
            setup["composite_score"] = self._calculate_composite_score(
                setup, portfolio_state
            )

        # Sort by composite score
        ranked = sorted(filtered, key=lambda x: x["composite_score"], reverse=True)

        # Add ranking
        for i, setup in enumerate(ranked, 1):
            setup["rank"] = i

        return ranked

    def _determine_market_regime(self, market_data: Dict) -> str:
        """Determine current market regime"""

        # Check Bitcoin as market leader
        btc_trend = market_data.get("btc_trend", 0)
        market_breadth = market_data.get("market_breadth", 0)
        fear_greed = market_data.get("fear_greed_index", 50)

        score = 0

        # BTC trend (40% weight)
        if btc_trend > 0.05:
            score += 40
        elif btc_trend > 0:
            score += 20
        elif btc_trend < -0.05:
            score -= 40
        elif btc_trend < 0:
            score -= 20

        # Market breadth (30% weight)
        if market_breadth > 0.7:
            score += 30
        elif market_breadth > 0.5:
            score += 15
        elif market_breadth < 0.3:
            score -= 30
        elif market_breadth < 0.5:
            score -= 15

        # Fear & Greed (30% weight)
        if fear_greed > 75:
            score += 30
        elif fear_greed > 60:
            score += 15
        elif fear_greed < 25:
            score -= 30
        elif fear_greed < 40:
            score -= 15

        # Map score to regime
        if score >= 60:
            return "STRONG_BULL"
        elif score >= 20:
            return "BULL"
        elif score >= -20:
            return "NEUTRAL"
        elif score >= -60:
            return "BEAR"
        else:
            return "STRONG_BEAR"

    def _calculate_risk_reward(self, setup: Dict) -> Dict:
        """Calculate risk/reward metrics"""

        entry = setup["entry_price"]
        stop = setup["stop_loss"]
        target = setup["take_profit"]

        risk = abs(entry - stop)
        reward = abs(target - entry)
        ratio = reward / risk if risk > 0 else 0

        risk_pct = (risk / entry) * 100
        reward_pct = (reward / entry) * 100

        return {
            "risk": risk,
            "reward": reward,
            "ratio": ratio,
            "risk_pct": risk_pct,
            "reward_pct": reward_pct,
        }

    def _adjust_for_market(self, setup: Dict, market_regime: str) -> Dict:
        """Adjust setup parameters based on market regime"""

        adjusted = setup.copy()
        regime_config = self.market_regimes[market_regime]

        # Adjust score threshold
        if setup["score"] < regime_config["min_score"]:
            adjusted["score"] *= 0.8  # Penalize if below threshold

        # Adjust position size
        adjusted["position_size_multiplier"] *= regime_config["multiplier"]

        # Adjust targets in bear market
        if "BEAR" in market_regime:
            # Tighter stops and smaller targets
            adjusted["stop_loss"] = setup["entry_price"] * 0.97  # Max 3% loss
            adjusted["take_profit"] = setup["entry_price"] * 1.05  # 5% target

        return adjusted

    def _calculate_expected_value(self, setup: Dict, risk_reward: Dict) -> float:
        """Calculate expected value of the trade"""

        # Estimate win probability based on setup score
        win_prob = min(0.35 + (setup["score"] / 200), 0.75)  # 35-75% win rate

        # Adjust for market conditions
        if setup.get("trend_strength", 0) > 0.05:
            win_prob += 0.05

        if setup.get("volume_ratio", 1) > 2:
            win_prob += 0.05

        win_prob = min(win_prob, 0.80)  # Cap at 80%

        # Calculate EV
        expected_value = (win_prob * risk_reward["reward_pct"]) - (
            (1 - win_prob) * risk_reward["risk_pct"]
        )

        return expected_value

    def _generate_trade_plan(self, setup: Dict) -> Dict:
        """Generate detailed trade plan"""

        entry = setup["entry_price"]

        # Scaling in strategy
        scale_in_levels = [
            {"price": entry, "size_pct": 50},
            {"price": entry * 1.005, "size_pct": 30},  # 0.5% higher
            {"price": entry * 1.01, "size_pct": 20},  # 1% higher
        ]

        # Scaling out strategy
        scale_out_levels = [
            {"price": entry * 1.03, "size_pct": 30},  # 3% profit
            {"price": entry * 1.05, "size_pct": 40},  # 5% profit
            {"price": setup["take_profit"], "size_pct": 30},  # Full target
        ]

        # Time limits
        max_hold_days = 5 if setup["pattern"] == "Momentum Surge" else 10

        return {
            "entry_strategy": "scale_in",
            "scale_in_levels": scale_in_levels,
            "exit_strategy": "scale_out",
            "scale_out_levels": scale_out_levels,
            "stop_loss": setup["stop_loss"],
            "trailing_stop_activation": entry * 1.05,  # Activate at 5% profit
            "trailing_stop_distance": 0.02,  # 2% trailing
            "max_hold_days": max_hold_days,
            "notes": self._generate_trade_notes(setup),
        }

    def _generate_trade_notes(self, setup: Dict) -> List[str]:
        """Generate helpful notes for the trade"""

        notes = []

        # Pattern-specific notes
        if setup["pattern"] == "Breakout":
            notes.append("Watch for false breakout - confirm with volume")
        elif setup["pattern"] == "Bull Flag":
            notes.append("Classic continuation pattern - expect strong move")
        elif setup["pattern"] == "Momentum Surge":
            notes.append("Fast mover - use tight stops and take profits quickly")

        # Volume notes
        if setup.get("volume_ratio", 1) > 3:
            notes.append("Exceptional volume - possible news catalyst")

        # RSI notes
        if setup.get("rsi", 50) > 65:
            notes.append("Approaching overbought - watch for reversal")
        elif setup.get("rsi", 50) < 40:
            notes.append("Oversold bounce play - may need patience")

        # Volatility notes
        if setup.get("volatility", 0) > 0.05:
            notes.append("High volatility - consider smaller position")

        return notes

    def _calculate_confidence(self, setup: Dict, market_regime: str) -> float:
        """Calculate confidence level for the trade"""

        confidence = 0.5  # Base confidence

        # Setup score contribution
        confidence += (setup["score"] - 50) / 200  # 0-25% from score

        # Market regime contribution
        if "BULL" in market_regime:
            confidence += 0.1
        elif "BEAR" in market_regime:
            confidence -= 0.1

        # Pattern strength
        strong_patterns = ["Breakout", "Bull Flag", "Cup & Handle"]
        if setup.get("pattern") in strong_patterns:
            confidence += 0.1

        # Volume confirmation
        if setup.get("volume_ratio", 1) > 2:
            confidence += 0.05

        return min(max(confidence, 0.2), 0.9)  # Clamp between 20-90%

    def _calculate_priority(self, setup: Dict, expected_value: float) -> int:
        """Calculate trade priority (1-10 scale)"""

        priority = 5  # Base priority

        # Expected value contribution
        if expected_value > 5:
            priority += 2
        elif expected_value > 3:
            priority += 1
        elif expected_value < 0:
            priority -= 2

        # Score contribution
        if setup["score"] > 80:
            priority += 2
        elif setup["score"] > 70:
            priority += 1
        elif setup["score"] < 60:
            priority -= 1

        # Risk/reward contribution
        rr_ratio = setup.get("risk_reward_ratio", 1)
        if rr_ratio > 3:
            priority += 1
        elif rr_ratio < 1.5:
            priority -= 1

        return min(max(priority, 1), 10)

    def _filter_by_portfolio(
        self, setups: List[Dict], portfolio_state: Dict
    ) -> List[Dict]:
        """Filter setups based on portfolio constraints"""

        filtered = []

        current_positions = portfolio_state.get("positions", [])
        current_exposure = portfolio_state.get("total_exposure_pct", 0)
        max_exposure = portfolio_state.get("max_exposure_pct", 30)

        # Get current symbols
        current_symbols = [p["symbol"] for p in current_positions]

        for setup in setups:
            # Skip if already in position
            if setup["symbol"] in current_symbols:
                continue

            # Skip if would exceed exposure limit
            position_size_pct = 3.0  # Base 3% position
            if current_exposure + position_size_pct > max_exposure:
                continue

            # Skip if too many positions
            if len(current_positions) >= 10:
                continue

            filtered.append(setup)

        return filtered

    def _calculate_composite_score(self, setup: Dict, portfolio_state: Dict) -> float:
        """Calculate composite score for ranking"""

        # Weighted factors
        weights = {
            "setup_score": 0.25,
            "expected_value": 0.25,
            "risk_reward": 0.15,
            "confidence": 0.15,
            "priority": 0.10,
            "diversification": 0.10,
        }

        # Normalize scores to 0-100 scale
        scores = {
            "setup_score": setup["score"],
            "expected_value": min(max(setup["expected_value"] * 10, 0), 100),
            "risk_reward": min(setup["risk_reward_ratio"] * 20, 100),
            "confidence": setup["confidence"] * 100,
            "priority": setup["priority"] * 10,
            "diversification": self._calculate_diversification_score(
                setup, portfolio_state
            ),
        }

        # Calculate weighted score
        composite = sum(scores[factor] * weight for factor, weight in weights.items())

        return composite

    def _calculate_diversification_score(
        self, setup: Dict, portfolio_state: Dict
    ) -> float:
        """Calculate how much this trade adds to diversification"""

        current_positions = portfolio_state.get("positions", [])

        if not current_positions:
            return 100  # First position gets max score

        # Check sector/correlation
        # Simplified - in production would use actual correlation data
        current_symbols = [p["symbol"] for p in current_positions]

        # Prefer different assets
        if setup["symbol"][:3] not in [s[:3] for s in current_symbols]:
            return 80
        else:
            return 40
