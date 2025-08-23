"""
Shadow Evaluator Module
Evaluates shadow trade outcomes using dynamic evaluation with full grid simulation
Runs every 5 minutes to check for completed trades
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from loguru import logger
import asyncio
from dataclasses import dataclass


@dataclass
class ShadowOutcome:
    """Represents the evaluated outcome of a shadow trade"""

    shadow_id: int
    outcome_status: str  # 'WIN', 'LOSS', 'TIMEOUT', 'PENDING'
    exit_trigger: str  # 'take_profit', 'stop_loss', 'timeout'
    exit_price: float
    pnl_percentage: float
    pnl_amount: float
    actual_hold_hours: float
    grid_fills: Optional[int] = None  # For DCA
    average_entry_price: Optional[float] = None  # For DCA
    total_position_size: Optional[float] = None  # For DCA


class ShadowEvaluator:
    """
    Evaluates shadow trade outcomes using actual price data
    Implements dynamic evaluation with full grid simulation for DCA
    """

    def __init__(self, supabase_client):
        """
        Initialize the shadow evaluator

        Args:
            supabase_client: Supabase client for database operations
        """
        self.supabase = supabase_client
        self.evaluation_interval = 300  # 5 minutes
        self.max_lookback_hours = 168  # 7 days max

    async def evaluate_pending_shadows(self) -> List[ShadowOutcome]:
        """
        Main evaluation loop - checks all pending shadow trades

        Returns:
            List of evaluated shadow outcomes
        """
        outcomes = []

        try:
            # Get shadows ready for evaluation
            shadows = await self._get_pending_shadows()
            logger.info(f"Found {len(shadows)} shadow trades to evaluate")

            if not shadows:
                logger.debug("No shadows ready for evaluation yet (need 5+ minute delay)")

            for shadow in shadows:
                outcome = await self._evaluate_shadow(shadow)
                if outcome and outcome.outcome_status != "PENDING":
                    outcomes.append(outcome)
                    await self._save_outcome(outcome)

            logger.info(f"Evaluated {len(outcomes)} shadow trades")

        except Exception as e:
            logger.error(f"Error evaluating shadows: {e}")

        return outcomes

    async def _get_pending_shadows(self) -> List[Dict]:
        """Get shadow trades that need evaluation"""
        try:
            # Direct query (RPC not available through wrapper)
            cutoff_time = (datetime.utcnow() - timedelta(minutes=5)).isoformat()

            # Get shadow variations that need evaluation
            # First get all variations that would take trades
            result = (
                self.supabase.table("shadow_variations")
                .select("*, scan_history!inner(*)")
                .eq("would_take_trade", True)
                .lt("created_at", cutoff_time)
                .limit(100)
                .execute()
            )

            if not result.data:
                return []

            # Now filter out ones that already have outcomes
            shadow_ids = [s["shadow_id"] for s in result.data]
            if shadow_ids:
                # Check which ones already have outcomes
                outcomes_result = (
                    self.supabase.table("shadow_outcomes").select("shadow_id").in_("shadow_id", shadow_ids).execute()
                )

                evaluated_ids = {o["shadow_id"] for o in outcomes_result.data} if outcomes_result.data else set()

                # Filter to only unevaluated shadows
                result.data = [s for s in result.data if s["shadow_id"] not in evaluated_ids]

            return result.data if result.data else []

        except Exception as e:
            logger.error(f"Error getting pending shadows: {e}")
            return []

    async def _evaluate_shadow(self, shadow: Dict) -> Optional[ShadowOutcome]:
        """
        Evaluate a single shadow trade
        """
        try:
            # Get scan details
            scan_data = (
                shadow.get("scan_history", {})
                if "scan_history" in shadow
                else await self._get_scan_data(shadow["scan_id"])
            )
            if not scan_data:
                logger.warning(f"No scan data for shadow {shadow['shadow_id']}")
                return None

            symbol = scan_data["symbol"]
            strategy = scan_data["strategy_name"]
            entry_time = datetime.fromisoformat(shadow["created_at"].replace("Z", "+00:00"))

            # Get price data since entry
            price_data = await self._get_price_data(symbol=symbol, start_time=entry_time, end_time=datetime.utcnow())

            if not price_data:
                logger.debug(f"No price data yet for {symbol} shadow {shadow['shadow_id']}")
                return ShadowOutcome(
                    shadow_id=shadow["shadow_id"],
                    outcome_status="PENDING",
                    exit_trigger="pending",
                    exit_price=0,
                    pnl_percentage=0,
                    pnl_amount=0,
                    actual_hold_hours=0,
                )

            # Evaluate based on strategy type
            if strategy == "DCA":
                return await self._evaluate_dca_shadow(shadow, price_data, entry_time)
            else:
                return await self._evaluate_single_entry_shadow(shadow, price_data, entry_time)

        except Exception as e:
            logger.error(f"Error evaluating shadow {shadow.get('shadow_id')}: {e}")
            return None

    async def _evaluate_single_entry_shadow(
        self, shadow: Dict, price_data: List[Dict], entry_time: datetime
    ) -> ShadowOutcome:
        """
        Evaluate shadow with single entry (Swing, Channel)
        Uses dynamic evaluation to find exact exit point
        """
        entry_price = float(shadow["shadow_entry_price"])
        take_profit_pct = float(shadow["shadow_take_profit"]) / 100
        stop_loss_pct = float(shadow["shadow_stop_loss"]) / 100
        max_hold_hours = float(shadow.get("shadow_hold_hours", 72))

        # Calculate target prices
        tp_price = entry_price * (1 + take_profit_pct)
        sl_price = entry_price * (1 - stop_loss_pct)

        # Scan through price data to find exit
        for price_point in price_data:
            point_time = datetime.fromisoformat(price_point["timestamp"].replace("Z", "+00:00"))
            hours_held = (point_time - entry_time).total_seconds() / 3600

            # Check timeout first
            if hours_held >= max_hold_hours:
                exit_price = float(price_point["close"])
                pnl_pct = (exit_price - entry_price) / entry_price

                return ShadowOutcome(
                    shadow_id=shadow["shadow_id"],
                    outcome_status="TIMEOUT",
                    exit_trigger="timeout",
                    exit_price=exit_price,
                    pnl_percentage=pnl_pct * 100,
                    pnl_amount=pnl_pct * float(shadow.get("shadow_position_size", 100)),
                    actual_hold_hours=hours_held,
                )

            # Check if price hit take profit
            high_price = float(price_point.get("high", price_point["close"]))
            if high_price >= tp_price:
                pnl_pct = take_profit_pct

                return ShadowOutcome(
                    shadow_id=shadow["shadow_id"],
                    outcome_status="WIN",
                    exit_trigger="take_profit",
                    exit_price=tp_price,
                    pnl_percentage=pnl_pct * 100,
                    pnl_amount=pnl_pct * float(shadow.get("shadow_position_size", 100)),
                    actual_hold_hours=hours_held,
                )

            # Check if price hit stop loss
            low_price = float(price_point.get("low", price_point["close"]))
            if low_price <= sl_price:
                pnl_pct = -stop_loss_pct

                return ShadowOutcome(
                    shadow_id=shadow["shadow_id"],
                    outcome_status="LOSS",
                    exit_trigger="stop_loss",
                    exit_price=sl_price,
                    pnl_percentage=pnl_pct * 100,
                    pnl_amount=pnl_pct * float(shadow.get("shadow_position_size", 100)),
                    actual_hold_hours=hours_held,
                )

        # Still pending if we get here
        return ShadowOutcome(
            shadow_id=shadow["shadow_id"],
            outcome_status="PENDING",
            exit_trigger="pending",
            exit_price=0,
            pnl_percentage=0,
            pnl_amount=0,
            actual_hold_hours=0,
        )

    async def _evaluate_dca_shadow(self, shadow: Dict, price_data: List[Dict], entry_time: datetime) -> ShadowOutcome:
        """
        Evaluate DCA shadow with full grid simulation
        This is more complex as we need to simulate grid fills
        """
        initial_price = float(shadow["shadow_entry_price"])
        grid_levels = int(shadow.get("dca_grid_levels", 5))
        grid_spacing = float(shadow.get("dca_grid_spacing", 1.0)) / 100  # Convert to decimal
        position_size_per_level = float(shadow.get("shadow_position_size", 100)) / grid_levels

        take_profit_pct = float(shadow["shadow_take_profit"]) / 100
        stop_loss_pct = float(shadow["shadow_stop_loss"]) / 100
        max_hold_hours = float(shadow.get("shadow_hold_hours", 72))

        # Calculate grid entry prices
        grid_prices = []
        for i in range(grid_levels):
            grid_price = initial_price * (1 - grid_spacing * i)
            grid_prices.append(grid_price)

        # Track grid fills
        filled_levels = []
        filled_prices = []
        total_position = 0
        total_cost = 0

        # Scan through price data
        for price_point in price_data:
            point_time = datetime.fromisoformat(price_point["timestamp"].replace("Z", "+00:00"))
            hours_held = (point_time - entry_time).total_seconds() / 3600

            low_price = float(price_point.get("low", price_point["close"]))
            high_price = float(price_point.get("high", price_point["close"]))
            close_price = float(price_point["close"])

            # Check which grid levels would fill
            for i, grid_price in enumerate(grid_prices):
                if i not in filled_levels and low_price <= grid_price:
                    filled_levels.append(i)
                    filled_prices.append(grid_price)
                    total_position += position_size_per_level
                    total_cost += position_size_per_level * grid_price

            # If we have any fills, check for exit
            if filled_levels:
                average_entry = total_cost / total_position if total_position > 0 else initial_price

                # Calculate exit targets based on average entry
                tp_price = average_entry * (1 + take_profit_pct)
                sl_price = average_entry * (1 - stop_loss_pct)

                # Check timeout
                if hours_held >= max_hold_hours:
                    pnl_pct = (close_price - average_entry) / average_entry
                    pnl_amount = total_position * close_price - total_cost

                    return ShadowOutcome(
                        shadow_id=shadow["shadow_id"],
                        outcome_status="TIMEOUT",
                        exit_trigger="timeout",
                        exit_price=close_price,
                        pnl_percentage=pnl_pct * 100,
                        pnl_amount=pnl_amount,
                        actual_hold_hours=hours_held,
                        grid_fills=len(filled_levels),
                        average_entry_price=average_entry,
                        total_position_size=total_position,
                    )

                # Check take profit
                if high_price >= tp_price:
                    pnl_pct = take_profit_pct
                    pnl_amount = total_position * tp_price - total_cost

                    return ShadowOutcome(
                        shadow_id=shadow["shadow_id"],
                        outcome_status="WIN",
                        exit_trigger="take_profit",
                        exit_price=tp_price,
                        pnl_percentage=pnl_pct * 100,
                        pnl_amount=pnl_amount,
                        actual_hold_hours=hours_held,
                        grid_fills=len(filled_levels),
                        average_entry_price=average_entry,
                        total_position_size=total_position,
                    )

                # Check stop loss
                if low_price <= sl_price:
                    pnl_pct = -stop_loss_pct
                    pnl_amount = total_position * sl_price - total_cost

                    return ShadowOutcome(
                        shadow_id=shadow["shadow_id"],
                        outcome_status="LOSS",
                        exit_trigger="stop_loss",
                        exit_price=sl_price,
                        pnl_percentage=pnl_pct * 100,
                        pnl_amount=pnl_amount,
                        actual_hold_hours=hours_held,
                        grid_fills=len(filled_levels),
                        average_entry_price=average_entry,
                        total_position_size=total_position,
                    )

        # Still pending or no fills
        if filled_levels:
            average_entry = total_cost / total_position if total_position > 0 else initial_price
        else:
            average_entry = initial_price

        return ShadowOutcome(
            shadow_id=shadow["shadow_id"],
            outcome_status="PENDING",
            exit_trigger="pending",
            exit_price=0,
            pnl_percentage=0,
            pnl_amount=0,
            actual_hold_hours=0,
            grid_fills=len(filled_levels),
            average_entry_price=average_entry,
            total_position_size=total_position,
        )

    async def _get_scan_data(self, scan_id: int) -> Optional[Dict]:
        """Get scan data from scan_history table"""
        try:
            result = self.supabase.table("scan_history").select("*").eq("scan_id", scan_id).single().execute()
            return result.data
        except Exception as e:
            logger.error(f"Error getting scan data: {e}")
            return None

    async def _get_price_data(self, symbol: str, start_time: datetime, end_time: datetime) -> List[Dict]:
        """
        Get price data for evaluation period
        Uses 1-minute OHLC data for precise evaluation
        """
        try:
            # Query OHLC data
            result = (
                self.supabase.table("ohlc_data")
                .select("timestamp, open, high, low, close, volume")
                .eq("symbol", symbol)
                .eq("timeframe", "1m")  # Fixed: was "1min", should be "1m"
                .gte("timestamp", start_time.isoformat())
                .lte("timestamp", end_time.isoformat())
                .order("timestamp")
                .execute()
            )

            if result.data:
                logger.debug(f"Found {len(result.data)} 1m price points for {symbol}")
                return result.data

            logger.warning(f"No 1m data for {symbol}, trying 5m fallback")
            # Fallback to 5-minute data if 1-minute not available
            result = (
                self.supabase.table("ohlc_data")
                .select("timestamp, open, high, low, close, volume")
                .eq("symbol", symbol)
                .eq("timeframe", "5m")  # Fixed: was "5min", should be "5m"
                .gte("timestamp", start_time.isoformat())
                .lte("timestamp", end_time.isoformat())
                .order("timestamp")
                .execute()
            )

            return result.data if result.data else []

        except Exception as e:
            logger.error(f"Error getting price data for {symbol}: {e}")
            logger.error(f"Start time: {start_time}, End time: {end_time}")
            logger.error("This is likely causing shadow evaluation failures!")
            return []

    async def _save_outcome(self, outcome: ShadowOutcome) -> bool:
        """Save evaluated outcome to database"""
        try:
            # Check if this matches a real trade
            matched_real = await self._check_real_trade_match(outcome)

            record = {
                "shadow_id": outcome.shadow_id,
                "evaluated_at": datetime.utcnow().isoformat(),
                "evaluation_delay_hours": outcome.actual_hold_hours,
                "outcome_status": outcome.outcome_status,
                "exit_trigger": outcome.exit_trigger,
                "exit_price": outcome.exit_price,
                "pnl_percentage": outcome.pnl_percentage,
                "pnl_amount": outcome.pnl_amount,
                "actual_hold_hours": outcome.actual_hold_hours,
                "grid_fills": outcome.grid_fills,
                "average_entry_price": outcome.average_entry_price,
                "total_position_size": outcome.total_position_size,
                "matched_real_trade": matched_real,
                "prediction_accuracy": self._calculate_accuracy(outcome),
                "created_at": datetime.utcnow().isoformat(),
            }

            result = self.supabase.table("shadow_outcomes").insert(record).execute()

            if result.data:
                logger.debug(f"Saved outcome for shadow {outcome.shadow_id}: {outcome.outcome_status}")
                return True

        except Exception as e:
            logger.error(f"Error saving outcome: {e}")

        return False

    async def _check_real_trade_match(self, outcome: ShadowOutcome) -> bool:
        """
        Check if this shadow outcome matches what really happened
        """
        try:
            # Get the shadow variation record
            shadow_result = (
                self.supabase.table("shadow_variations")
                .select("scan_id, variation_name")
                .eq("shadow_id", outcome.shadow_id)
                .single()
                .execute()
            )

            if not shadow_result.data:
                return False

            # Check if this is the CHAMPION variation
            if shadow_result.data["variation_name"] != "CHAMPION":
                # For non-champion, check if a real trade exists
                trade_result = (
                    self.supabase.table("trade_logs")
                    .select("status, pnl_percentage")
                    .eq("scan_id", shadow_result.data["scan_id"])
                    .execute()
                )

                if trade_result.data:
                    real_trade = trade_result.data[0]
                    # Check if outcomes match (within tolerance)
                    if real_trade["status"].startswith("CLOSED_"):
                        real_win = "WIN" in real_trade["status"]
                        shadow_win = outcome.outcome_status == "WIN"
                        return real_win == shadow_win
            else:
                # Champion should always match real trades by definition
                return True

        except Exception as e:
            logger.error(f"Error checking real trade match: {e}")

        return False

    def _calculate_accuracy(self, outcome: ShadowOutcome) -> Dict:
        """Calculate prediction accuracy metrics"""
        return {
            "outcome_status": outcome.outcome_status,
            "pnl_percentage": outcome.pnl_percentage,
            "hold_hours": outcome.actual_hold_hours,
            "exit_trigger": outcome.exit_trigger,
            "grid_fills": outcome.grid_fills if outcome.grid_fills else None,
        }

    async def run_evaluation_loop(self):
        """
        Main loop that runs continuously
        Evaluates pending shadows every 5 minutes
        """
        logger.info("Starting shadow evaluation loop")

        while True:
            try:
                await self.evaluate_pending_shadows()
                await asyncio.sleep(self.evaluation_interval)

            except Exception as e:
                logger.error(f"Error in evaluation loop: {e}")
                await asyncio.sleep(60)  # Wait a minute before retrying
