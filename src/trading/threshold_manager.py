"""
Threshold Adjustment Manager
Manages parameter adjustments based on shadow testing recommendations
Implements safety controls and rollback mechanisms
"""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from decimal import Decimal
from loguru import logger
import json
from dataclasses import dataclass
from enum import Enum

from src.config.shadow_config import ShadowConfig
from src.analysis.shadow_analyzer import AdjustmentRecommendation


class AdjustmentStatus(Enum):
    """Status of an adjustment"""

    PENDING = "pending"
    APPROVED = "approved"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"
    REJECTED = "rejected"


@dataclass
class AdjustmentResult:
    """Result of an adjustment attempt"""

    success: bool
    adjustment_id: Optional[int]
    parameter_name: str
    old_value: float
    new_value: float
    reason: str
    rollback_triggered: bool = False


class ThresholdManager:
    """
    Manages threshold adjustments with safety controls
    """

    def __init__(self, supabase_client, regime_detector=None):
        """
        Initialize the threshold manager

        Args:
            supabase_client: Supabase client for database operations
            regime_detector: Market regime detector for stability checks
        """
        self.supabase = supabase_client
        self.regime_detector = regime_detector
        self.max_adjustments_per_day = 3
        self.regime_stability_hours = 12
        self.rollback_monitor_hours = 48

    async def process_recommendations(
        self, recommendations: List[AdjustmentRecommendation], force: bool = False
    ) -> List[AdjustmentResult]:
        """
        Process adjustment recommendations with safety checks

        Args:
            recommendations: List of recommendations from shadow analyzer
            force: Skip safety checks if True (manual override)

        Returns:
            List of adjustment results
        """
        results = []

        try:
            # Safety check 1: Market regime stability
            if not force and not await self._check_regime_stability():
                logger.warning("Market regime unstable - skipping adjustments")
                for rec in recommendations:
                    results.append(
                        AdjustmentResult(
                            success=False,
                            adjustment_id=None,
                            parameter_name=rec.parameter_name,
                            old_value=rec.current_value,
                            new_value=rec.recommended_value,
                            reason="Market regime unstable",
                        )
                    )
                return results

            # Safety check 2: Daily adjustment limit
            adjustments_today = 0
            if not force:
                adjustments_today = await self._count_adjustments_today()
                if adjustments_today >= self.max_adjustments_per_day:
                    logger.warning(
                        f"Daily adjustment limit reached ({adjustments_today}/{self.max_adjustments_per_day})"
                    )
                    for rec in recommendations:
                        results.append(
                            AdjustmentResult(
                                success=False,
                                adjustment_id=None,
                                parameter_name=rec.parameter_name,
                                old_value=rec.current_value,
                                new_value=rec.recommended_value,
                                reason="Daily adjustment limit reached",
                            )
                        )
                    return results

            # Process each recommendation
            for rec in recommendations[
                : self.max_adjustments_per_day - adjustments_today
            ]:
                result = await self._apply_adjustment(rec, force)
                results.append(result)

                if result.success:
                    logger.info(
                        f"✅ Applied adjustment: {rec.parameter_name} "
                        f"{rec.current_value:.2f} → {rec.recommended_value:.2f}"
                    )
                else:
                    logger.warning(
                        f"❌ Failed adjustment: {rec.parameter_name} - {result.reason}"
                    )

        except Exception as e:
            logger.error(f"Error processing recommendations: {e}")

        return results

    async def _apply_adjustment(
        self, recommendation: AdjustmentRecommendation, force: bool = False
    ) -> AdjustmentResult:
        """
        Apply a single adjustment with safety checks
        """
        try:
            # Get parameter limits
            limits = ShadowConfig.ADJUSTMENT_LIMITS.get(recommendation.parameter_name)
            if not limits and not force:
                return AdjustmentResult(
                    success=False,
                    adjustment_id=None,
                    parameter_name=recommendation.parameter_name,
                    old_value=recommendation.current_value,
                    new_value=recommendation.recommended_value,
                    reason="No limits defined for parameter",
                )

            # Calculate adjusted value with limits
            if not force and limits:
                adjusted_value = self._apply_limits(
                    current_value=recommendation.current_value,
                    recommended_value=recommendation.recommended_value,
                    limits=limits,
                    confidence_level=recommendation.confidence_level,
                )
            else:
                adjusted_value = recommendation.recommended_value

            # Check if adjustment is meaningful
            if abs(adjusted_value - recommendation.current_value) < 0.001:
                return AdjustmentResult(
                    success=False,
                    adjustment_id=None,
                    parameter_name=recommendation.parameter_name,
                    old_value=recommendation.current_value,
                    new_value=adjusted_value,
                    reason="Adjustment too small",
                )

            # Record adjustment in database
            adjustment_id = await self._record_adjustment(
                strategy_name=recommendation.strategy_name,
                parameter_name=recommendation.parameter_name,
                old_value=recommendation.current_value,
                new_value=adjusted_value,
                shadow_recommended=recommendation.recommended_value,
                confidence=recommendation.confidence_level,
                evidence_trades=recommendation.evidence_trades,
                outperformance=recommendation.outperformance,
                p_value=recommendation.p_value,
                reason=recommendation.reason,
                variation_source=recommendation.variation_source,
                manual_override=force,
            )

            # Apply to configuration
            success = await self._update_configuration(
                strategy_name=recommendation.strategy_name,
                parameter_name=recommendation.parameter_name,
                new_value=adjusted_value,
            )

            if success:
                # Start monitoring for rollback
                asyncio.create_task(self._monitor_for_rollback(adjustment_id))

            return AdjustmentResult(
                success=success,
                adjustment_id=adjustment_id,
                parameter_name=recommendation.parameter_name,
                old_value=recommendation.current_value,
                new_value=adjusted_value,
                reason="Applied successfully"
                if success
                else "Failed to update configuration",
            )

        except Exception as e:
            logger.error(f"Error applying adjustment: {e}")
            return AdjustmentResult(
                success=False,
                adjustment_id=None,
                parameter_name=recommendation.parameter_name,
                old_value=recommendation.current_value,
                new_value=recommendation.recommended_value,
                reason=f"Error: {str(e)}",
            )

    def _apply_limits(
        self,
        current_value: float,
        recommended_value: float,
        limits: Any,
        confidence_level: str,
    ) -> float:
        """
        Apply safety limits to recommended value
        """
        # Get adjustment multiplier based on confidence
        multiplier = ShadowConfig.CONFIDENCE_TIERS[confidence_level][
            "adjustment_multiplier"
        ]

        # Calculate maximum allowed change
        max_change = current_value * limits.max_relative_change

        # Calculate actual change with confidence multiplier
        desired_change = (recommended_value - current_value) * multiplier

        # Limit the change
        actual_change = max(min(desired_change, max_change), -max_change)

        # Calculate new value
        new_value = current_value + actual_change

        # Apply absolute limits
        new_value = max(min(new_value, limits.max_value), limits.min_value)

        return new_value

    async def _check_regime_stability(self) -> bool:
        """
        Check if market regime has been stable
        """
        if not self.regime_detector:
            return True  # No regime detector, assume stable

        try:
            # Get regime history
            cutoff_time = datetime.utcnow() - timedelta(
                hours=self.regime_stability_hours
            )

            result = (
                self.supabase.table("scan_history")
                .select("market_regime")
                .gte("timestamp", cutoff_time.isoformat())
                .order("timestamp", desc=True)
                .limit(100)
                .execute()
            )

            if not result.data:
                return True  # No data, assume stable

            # Check for regime changes
            regimes = [r["market_regime"] for r in result.data if r["market_regime"]]
            if not regimes:
                return True

            # If all regimes are the same, it's stable
            unique_regimes = set(regimes)
            is_stable = len(unique_regimes) == 1

            if not is_stable:
                logger.info(
                    f"Regime changed in last {self.regime_stability_hours}h: {unique_regimes}"
                )

            return is_stable

        except Exception as e:
            logger.error(f"Error checking regime stability: {e}")
            return False  # Err on side of caution

    async def _count_adjustments_today(self) -> int:
        """
        Count adjustments made today
        """
        try:
            today_start = datetime.utcnow().replace(
                hour=0, minute=0, second=0, microsecond=0
            )

            result = (
                self.supabase.table("threshold_adjustments")
                .select("adjustment_id")
                .gte("adjusted_at", today_start.isoformat())
                .eq("rollback_triggered", False)
                .execute()
            )

            return len(result.data) if result.data else 0

        except Exception as e:
            logger.error(f"Error counting adjustments: {e}")
            return self.max_adjustments_per_day  # Err on side of caution

    async def _record_adjustment(self, **kwargs) -> Optional[int]:
        """
        Record adjustment in database
        """
        try:
            record = {
                "strategy_name": kwargs["strategy_name"],
                "parameter_name": kwargs["parameter_name"],
                "old_value": kwargs["old_value"],
                "new_value": kwargs["new_value"],
                "shadow_recommended_value": kwargs["shadow_recommended"],
                "adjustment_percentage": (
                    (kwargs["new_value"] - kwargs["old_value"]) / kwargs["old_value"]
                )
                * 100,
                "adjustment_confidence": kwargs["confidence"],
                "evidence_trades": kwargs["evidence_trades"],
                "evidence_timeframe": "3d",  # Default to 3-day evidence
                "outperformance_percentage": kwargs["outperformance"] * 100,
                "statistical_p_value": kwargs["p_value"],
                "adjustment_reason": kwargs["reason"],
                "variation_source": kwargs["variation_source"],
                "within_safety_limits": True,
                "market_regime_stable": await self._check_regime_stability(),
                "manual_override": kwargs.get("manual_override", False),
                "adjusted_at": datetime.utcnow().isoformat(),
                "adjusted_by": "shadow_system",
            }

            result = (
                self.supabase.table("threshold_adjustments").insert(record).execute()
            )

            if result.data and len(result.data) > 0:
                return result.data[0]["adjustment_id"]

        except Exception as e:
            logger.error(f"Error recording adjustment: {e}")

        return None

    async def _update_configuration(
        self, strategy_name: str, parameter_name: str, new_value: float
    ) -> bool:
        """
        Update the actual configuration
        This would update your production parameters
        """
        try:
            # In a real implementation, this would update your actual config
            # For now, we'll update a configuration table

            # Check if config exists
            result = (
                self.supabase.table("strategy_configurations")
                .select("*")
                .eq("strategy_name", strategy_name)
                .single()
                .execute()
            )

            if result.data:
                # Update existing
                config = result.data
                config[parameter_name] = new_value
                config["updated_at"] = datetime.utcnow().isoformat()

                self.supabase.table("strategy_configurations").update(config).eq(
                    "strategy_name", strategy_name
                ).execute()
            else:
                # Create new
                config = {
                    "strategy_name": strategy_name,
                    parameter_name: new_value,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                }

                self.supabase.table("strategy_configurations").insert(config).execute()

            logger.info(f"Updated {strategy_name}.{parameter_name} = {new_value}")
            return True

        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
            return False

    async def _monitor_for_rollback(self, adjustment_id: int):
        """
        Monitor an adjustment for potential rollback
        """
        try:
            # Wait initial period
            await asyncio.sleep(3600)  # 1 hour

            # Check performance every hour for rollback_monitor_hours
            for hour in range(self.rollback_monitor_hours):
                should_rollback, reason = await self._check_rollback_conditions(
                    adjustment_id
                )

                if should_rollback:
                    await self.rollback_adjustment(adjustment_id, reason)
                    break

                await asyncio.sleep(3600)  # Check again in 1 hour

        except Exception as e:
            logger.error(f"Error monitoring adjustment {adjustment_id}: {e}")

    async def _check_rollback_conditions(self, adjustment_id: int) -> Tuple[bool, str]:
        """
        Check if an adjustment should be rolled back
        """
        try:
            # Get adjustment details
            result = (
                self.supabase.table("threshold_adjustments")
                .select("*")
                .eq("adjustment_id", adjustment_id)
                .single()
                .execute()
            )

            if not result.data:
                return False, ""

            adjustment = result.data

            # Get current performance
            current_performance = await self._get_current_performance(
                adjustment["strategy_name"]
            )

            if not current_performance:
                return False, ""

            # Check rollback triggers
            rollback_config = ShadowConfig.ROLLBACK_TRIGGERS

            # Immediate rollback: Win rate drop
            if "win_rate_before" in adjustment:
                win_rate_drop = (
                    adjustment["win_rate_before"] - current_performance["win_rate"]
                )
                if win_rate_drop > rollback_config["immediate"]["win_rate_drop"]:
                    return True, f"Win rate dropped by {win_rate_drop:.1%}"

            # Immediate rollback: Consecutive losses
            recent_trades = await self._get_recent_trades(
                adjustment["strategy_name"], hours=1
            )
            if recent_trades:
                consecutive_losses = self._count_consecutive_losses(recent_trades)
                if (
                    consecutive_losses
                    >= rollback_config["immediate"]["consecutive_losses"]
                ):
                    return True, f"{consecutive_losses} consecutive losses"

            # Gradual rollback: Underperformance
            hours_since = (
                datetime.utcnow() - datetime.fromisoformat(adjustment["adjusted_at"])
            ).total_seconds() / 3600
            if hours_since >= rollback_config["gradual"]["underperform_hours"]:
                if current_performance["win_rate"] < adjustment.get(
                    "win_rate_before", 0
                ):
                    return True, f"Underperforming for {hours_since:.0f} hours"

        except Exception as e:
            logger.error(f"Error checking rollback conditions: {e}")

        return False, ""

    async def rollback_adjustment(self, adjustment_id: int, reason: str):
        """
        Rollback a specific adjustment
        """
        try:
            # Get adjustment details
            result = (
                self.supabase.table("threshold_adjustments")
                .select("*")
                .eq("adjustment_id", adjustment_id)
                .single()
                .execute()
            )

            if not result.data:
                logger.error(f"Adjustment {adjustment_id} not found")
                return

            adjustment = result.data

            # Revert configuration
            success = await self._update_configuration(
                strategy_name=adjustment["strategy_name"],
                parameter_name=adjustment["parameter_name"],
                new_value=adjustment["old_value"],
            )

            if success:
                # Update adjustment record
                self.supabase.table("threshold_adjustments").update(
                    {"rollback_triggered": True, "rollback_reason": reason}
                ).eq("adjustment_id", adjustment_id).execute()

                logger.warning(f"🔄 Rolled back adjustment {adjustment_id}: {reason}")

                # Record the rollback as a new adjustment
                await self._record_adjustment(
                    strategy_name=adjustment["strategy_name"],
                    parameter_name=adjustment["parameter_name"],
                    old_value=adjustment["new_value"],
                    new_value=adjustment["old_value"],
                    shadow_recommended=adjustment["old_value"],
                    confidence="HIGH",
                    evidence_trades=0,
                    outperformance=0,
                    p_value=0,
                    reason=f"Rollback: {reason}",
                    variation_source="ROLLBACK",
                    manual_override=False,
                )

        except Exception as e:
            logger.error(f"Error rolling back adjustment: {e}")

    async def _get_current_performance(self, strategy_name: str) -> Optional[Dict]:
        """Get current performance metrics for a strategy"""
        try:
            result = (
                self.supabase.table("shadow_performance")
                .select("*")
                .eq("variation_name", "CHAMPION")
                .eq("strategy_name", strategy_name)
                .eq("timeframe", "24h")
                .single()
                .execute()
            )

            if result.data:
                return {
                    "win_rate": float(result.data["win_rate"]),
                    "avg_pnl": float(result.data["avg_pnl_percentage"]),
                }

        except Exception as e:
            logger.error(f"Error getting current performance: {e}")

        return None

    async def _get_recent_trades(self, strategy_name: str, hours: int) -> List[Dict]:
        """Get recent trades for a strategy"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)

            result = (
                self.supabase.table("trade_logs")
                .select("*")
                .eq("strategy_name", strategy_name)
                .gte("closed_at", cutoff_time.isoformat())
                .order("closed_at", desc=True)
                .execute()
            )

            return result.data if result.data else []

        except Exception as e:
            logger.error(f"Error getting recent trades: {e}")
            return []

    def _count_consecutive_losses(self, trades: List[Dict]) -> int:
        """Count consecutive losses from most recent trades"""
        consecutive = 0
        for trade in trades:
            if trade["status"] == "CLOSED_LOSS":
                consecutive += 1
            else:
                break
        return consecutive

    async def emergency_stop(self, reason: str = "Manual emergency stop"):
        """
        Emergency stop - rollback all recent adjustments
        """
        try:
            logger.critical(f"🚨 EMERGENCY STOP: {reason}")

            # Get all adjustments from last 24 hours
            cutoff_time = datetime.utcnow() - timedelta(hours=24)

            result = (
                self.supabase.table("threshold_adjustments")
                .select("*")
                .gte("adjusted_at", cutoff_time.isoformat())
                .eq("rollback_triggered", False)
                .execute()
            )

            if result.data:
                for adjustment in result.data:
                    await self.rollback_adjustment(
                        adjustment["adjustment_id"], f"Emergency stop: {reason}"
                    )

                logger.info(f"Rolled back {len(result.data)} adjustments")
            else:
                logger.info("No recent adjustments to rollback")

        except Exception as e:
            logger.error(f"Error in emergency stop: {e}")


# Import asyncio at the top of the file
import asyncio
