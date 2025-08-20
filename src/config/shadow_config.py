"""
Shadow Testing Configuration
Defines all shadow variations, adjustment rules, and safety parameters
"""

from typing import Dict, Any, List
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class ShadowVariation:
    """Defines a single shadow variation to test"""

    name: str
    type: str  # 'scenario', 'isolated', 'champion'
    description: str
    parameters: Dict[str, Any]
    is_active: bool = True
    priority: int = 1


@dataclass
class AdjustmentLimits:
    """Safety limits for parameter adjustments"""

    parameter: str
    max_relative_change: float  # Maximum relative change per adjustment
    min_value: float  # Absolute minimum value
    max_value: float  # Absolute maximum value


class ShadowConfig:
    """Complete shadow testing configuration"""

    # ============================================
    # SHADOW VARIATIONS
    # ============================================

    VARIATIONS = {
        "CHAMPION": ShadowVariation(
            name="CHAMPION",
            type="champion",
            description="Current production settings - baseline for comparison",
            parameters={},  # Uses current production values
            priority=1,
        ),
        "BEAR_MARKET": ShadowVariation(
            name="BEAR_MARKET",
            type="scenario",
            description="Aggressive settings optimized for bear markets",
            parameters={
                "confidence_threshold": 0.55,  # Lower threshold
                "position_size_multiplier": 1.5,  # Larger positions
                "stop_loss_percent": 0.06,  # Wider stops
                "take_profit_multiplier": 1.2,  # Higher targets
                "dca_drop_threshold": 0.03,  # Smaller drops
            },
            priority=2,
        ),
        "BULL_MARKET": ShadowVariation(
            name="BULL_MARKET",
            type="scenario",
            description="Conservative settings for bull markets",
            parameters={
                "confidence_threshold": 0.65,  # Higher threshold
                "position_size_multiplier": 0.5,  # Smaller positions
                "stop_loss_percent": 0.04,  # Tighter stops
                "take_profit_multiplier": 0.8,  # Quick profits
                "swing_breakout_threshold": 0.05,  # Stronger breakouts
            },
            priority=3,
        ),
        "ML_TRUST": ShadowVariation(
            name="ML_TRUST",
            type="scenario",
            description="Follow ML predictions exactly without modification",
            parameters={
                "use_ml_predictions_raw": True,
                "confidence_threshold": 0.50,  # Trust ML confidence
                "take_profit_multiplier": 1.0,  # Use ML TP exactly
                "stop_loss_from_ml": True,  # Use ML SL exactly
            },
            priority=4,
        ),
        "QUICK_EXITS": ShadowVariation(
            name="QUICK_EXITS",
            type="scenario",
            description="Take profits earlier to increase win rate",
            parameters={
                "take_profit_multiplier": 0.8,  # 80% of ML prediction
                "max_hold_hours": 24,  # Exit within a day
                "trailing_stop_activation": 0.05,  # Trail after 5%
            },
            priority=5,
        ),
        "DCA_DROPS": ShadowVariation(
            name="DCA_DROPS",
            type="isolated",
            description="Test optimal DCA entry drop thresholds",
            parameters={
                "test_parameter": "dca_drop_threshold",
                "test_values": [0.03, 0.04, 0.05],  # 3%, 4%, 5%
            },
            priority=6,
        ),
        "CONFIDENCE_TEST": ShadowVariation(
            name="CONFIDENCE_TEST",
            type="isolated",
            description="Test optimal confidence thresholds",
            parameters={
                "test_parameter": "confidence_threshold",
                "test_values": [0.55, 0.58, 0.60, 0.62],
            },
            priority=7,
        ),
        "VOLATILITY_SIZED": ShadowVariation(
            name="VOLATILITY_SIZED",
            type="scenario",
            description="Dynamic position sizing based on volatility",
            parameters={
                "use_volatility_sizing": True,
                "low_vol_multiplier": 1.5,  # Increase size in low vol
                "high_vol_multiplier": 0.5,  # Decrease size in high vol
                "vol_threshold_low": 0.02,  # <2% daily vol
                "vol_threshold_high": 0.05,  # >5% daily vol
            },
            priority=8,
        ),
    }

    # ============================================
    # ADJUSTMENT RULES
    # ============================================

    ADJUSTMENT_FREQUENCY = "daily_2am_pst"  # When to check for adjustments
    MIN_SHADOW_TRADES = 30  # Minimum trades before any adjustment

    # Parameter-specific adjustment limits
    ADJUSTMENT_LIMITS = {
        "confidence_threshold": AdjustmentLimits(
            parameter="confidence_threshold",
            max_relative_change=0.05,  # 5% relative
            min_value=0.50,
            max_value=0.70,
        ),
        "stop_loss_percent": AdjustmentLimits(
            parameter="stop_loss_percent",
            max_relative_change=0.20,  # 20% relative
            min_value=0.03,
            max_value=0.10,
        ),
        "position_size_multiplier": AdjustmentLimits(
            parameter="position_size_multiplier",
            max_relative_change=0.30,  # 30% relative
            min_value=0.3,
            max_value=2.0,
        ),
        "dca_drop_threshold": AdjustmentLimits(
            parameter="dca_drop_threshold",
            max_relative_change=0.20,  # 20% relative
            min_value=0.02,
            max_value=0.10,
        ),
        "take_profit_multiplier": AdjustmentLimits(
            parameter="take_profit_multiplier",
            max_relative_change=0.15,  # 15% relative
            min_value=0.5,
            max_value=1.5,
        ),
        "swing_breakout_threshold": AdjustmentLimits(
            parameter="swing_breakout_threshold",
            max_relative_change=0.25,  # 25% relative
            min_value=0.02,
            max_value=0.08,
        ),
    }

    # ============================================
    # CONFIDENCE TIERS
    # ============================================

    CONFIDENCE_TIERS = {
        "HIGH": {
            "min_trades": 100,
            "min_outperformance": 0.10,  # 10% better
            "max_p_value": 0.01,  # 99% confidence
            "adjustment_multiplier": 1.0,  # Full adjustment
            "min_days": 3,  # Consistent for 3 days
        },
        "MEDIUM": {
            "min_trades": 50,
            "min_outperformance": 0.05,  # 5% better
            "max_p_value": 0.05,  # 95% confidence
            "adjustment_multiplier": 0.5,  # Half adjustment
            "min_days": 2,  # Consistent for 2 days
        },
        "LOW": {
            "min_trades": 30,
            "min_outperformance": 0.03,  # 3% better
            "max_p_value": 0.10,  # 90% confidence
            "adjustment_multiplier": 0.25,  # Quarter adjustment
            "min_days": 1,  # At least 1 day
        },
    }

    # ============================================
    # ROLLBACK TRIGGERS
    # ============================================

    ROLLBACK_TRIGGERS = {
        "immediate": {
            "win_rate_drop": 0.15,  # 15% drop in win rate
            "consecutive_losses": 3,  # 3 losses in a row
            "pnl_drop": 0.20,  # 20% drop in P&L
        },
        "gradual": {
            "underperform_hours": 48,  # Underperform for 48 hours
            "revert_percentage": 0.50,  # Move 50% back
        },
        "emergency": {
            "market_panic": True,  # Circuit breaker
            "manual_override": True,  # Always available
        },
    }

    # ============================================
    # ML INTEGRATION
    # ============================================

    ML_INTEGRATION = {
        "shadow_weight_range": (0.1, 0.5),  # Min and max weight for shadows
        "weight_factors": [
            "accuracy",  # Did shadow match reality?
            "variation_performance",  # How well does this variation perform?
            "age",  # How long have we tracked this?
            "regime_match",  # Does regime match current?
        ],
        "min_real_trades": 5,  # Always need some real trades
        "max_shadow_ratio": 20,  # Maximum 20:1 shadow to real
        "shadow_features": [
            "shadow_consensus_score",  # % of shadows agreeing
            "shadow_performance_delta",  # Shadow vs real performance
            "regime_shadow_alignment",  # How well shadows work in regime
        ],
    }

    # ============================================
    # EVALUATION SETTINGS
    # ============================================

    EVALUATION = {
        "check_interval_minutes": 5,  # Check for completed trades
        "min_price_data_minutes": 1,  # Need 1-minute data
        "use_dynamic_evaluation": True,  # Simulate exact exits
        "simulate_full_grids": True,  # For DCA, simulate all levels
        "track_metrics": [
            "time_to_tp",
            "time_to_sl",
            "max_adverse_excursion",
            "max_favorable_excursion",
            "grid_fill_rate",
            "average_entry_improvement",
        ],
    }

    # ============================================
    # SAFETY SETTINGS
    # ============================================

    SAFETY = {
        "require_stable_regime": True,  # No adjustments during regime changes
        "regime_stability_hours": 12,  # Regime must be stable for 12 hours
        "max_adjustments_per_day": 3,  # Maximum 3 parameter adjustments
        "require_consensus": False,  # Don't require all shadows to agree
        "preserve_champion": True,  # Always keep champion for comparison
        "max_active_variations": 10,  # Limit concurrent variations
    }

    # ============================================
    # REPORTING SETTINGS
    # ============================================

    REPORTING = {
        "daily_summary_time": "02:00",  # 2 AM PST
        "slack_notifications": True,
        "include_recommendations": True,
        "show_top_performers": 3,  # Show top 3 variations
        "timeframes": ["24h", "3d", "7d"],  # Report these timeframes
        "min_trades_for_report": 10,  # Need 10 trades to include
    }

    @classmethod
    def get_variation_parameters(cls, variation_name: str, base_params: Dict) -> Dict:
        """
        Get complete parameters for a variation, merging with base parameters
        """
        if variation_name not in cls.VARIATIONS:
            return base_params

        variation = cls.VARIATIONS[variation_name]

        # Champion uses base params as-is
        if variation.type == "champion":
            return base_params

        # Scenario variations override specific parameters
        if variation.type == "scenario":
            result = base_params.copy()
            result.update(variation.parameters)
            return result

        # Isolated variations test specific values
        if variation.type == "isolated":
            # This will be handled by the shadow logger
            # It will create multiple sub-variations
            return base_params

        return base_params

    @classmethod
    def should_adjust_parameter(
        cls, param_name: str, evidence: Dict
    ) -> tuple[bool, float, str]:
        """
        Determine if a parameter should be adjusted based on evidence
        Returns: (should_adjust, recommended_value, confidence_level)
        """
        # Check if we have enough evidence
        if evidence["trade_count"] < cls.MIN_SHADOW_TRADES:
            return False, None, "INSUFFICIENT"

        # Determine confidence tier
        confidence_level = None
        adjustment_multiplier = 0

        for tier_name, tier_config in cls.CONFIDENCE_TIERS.items():
            if (
                evidence["trade_count"] >= tier_config["min_trades"]
                and evidence["outperformance"] >= tier_config["min_outperformance"]
                and evidence["p_value"] <= tier_config["max_p_value"]
                and evidence["consistent_days"] >= tier_config["min_days"]
            ):
                confidence_level = tier_name
                adjustment_multiplier = tier_config["adjustment_multiplier"]
                break

        if not confidence_level:
            return False, None, "LOW_CONFIDENCE"

        # Calculate recommended adjustment
        if param_name not in cls.ADJUSTMENT_LIMITS:
            return False, None, "NO_LIMITS"

        limits = cls.ADJUSTMENT_LIMITS[param_name]
        current_value = evidence["current_value"]
        suggested_value = evidence["suggested_value"]

        # Calculate adjustment with limits
        max_change = current_value * limits.max_relative_change
        actual_change = (suggested_value - current_value) * adjustment_multiplier
        actual_change = max(min(actual_change, max_change), -max_change)

        new_value = current_value + actual_change
        new_value = max(min(new_value, limits.max_value), limits.min_value)

        # Check if adjustment is meaningful
        if abs(new_value - current_value) / current_value < 0.01:  # <1% change
            return False, None, "CHANGE_TOO_SMALL"

        return True, new_value, confidence_level

    @classmethod
    def get_active_variations(cls) -> List[str]:
        """Get list of currently active variation names"""
        return [name for name, var in cls.VARIATIONS.items() if var.is_active]

    @classmethod
    def get_ml_shadow_weight(cls, shadow_outcome: Dict) -> float:
        """Calculate weight for a shadow outcome in ML training"""
        base_weight = cls.ML_INTEGRATION["shadow_weight_range"][0]

        # Add weight based on factors
        if shadow_outcome.get("matched_reality", False):
            base_weight += 0.2

        if shadow_outcome.get("variation_win_rate", 0) > 0.60:
            base_weight += 0.1

        if shadow_outcome.get("variation_age_days", 0) > 7:
            base_weight += 0.1

        if shadow_outcome.get("regime_matches", False):
            base_weight += 0.1

        # Cap at maximum
        max_weight = cls.ML_INTEGRATION["shadow_weight_range"][1]
        return min(base_weight, max_weight)
