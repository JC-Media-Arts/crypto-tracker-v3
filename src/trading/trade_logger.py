"""
Trade Logger for tracking trade outcomes and linking to predictions
"""

from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from loguru import logger
import json


class TradeLogger:
    """Logs trade execution and outcomes for ML feedback loop"""

    def __init__(self, supabase_client):
        """
        Initialize trade logger

        Args:
            supabase_client: Supabase client for database operations
        """
        self.supabase = supabase_client
        self.active_trades = {}  # trade_id -> trade_info

    def open_trade(
        self,
        scan_id: int,
        symbol: str,
        strategy_name: str,
        entry_price: float,
        position_size: float,
        capital_used: float,
        ml_predictions: Optional[Dict] = None,
        ml_confidence: Optional[float] = None,
    ) -> Optional[int]:
        """
        Log a new trade opening

        Args:
            scan_id: ID of the scan that triggered this trade
            symbol: Trading symbol
            strategy_name: Strategy that opened the trade
            entry_price: Entry price
            position_size: Size of position
            capital_used: Capital allocated
            ml_predictions: ML predictions (TP, SL, hold time, win prob)
            ml_confidence: ML confidence score

        Returns:
            trade_id if successful, None otherwise
        """
        try:
            trade_data = {
                "scan_id": scan_id,
                "symbol": symbol,
                "strategy_name": strategy_name,
                "entry_price": entry_price,
                "position_size": position_size,
                "capital_used": capital_used,
                "status": "OPEN",
                "opened_at": datetime.utcnow().isoformat(),
            }

            # Add ML predictions if available
            if ml_predictions:
                trade_data.update(
                    {
                        "predicted_take_profit": ml_predictions.get("take_profit"),
                        "predicted_stop_loss": ml_predictions.get("stop_loss"),
                        "predicted_hold_hours": ml_predictions.get("hold_hours"),
                        "predicted_win_probability": ml_predictions.get(
                            "win_probability"
                        ),
                    }
                )

            if ml_confidence:
                trade_data["ml_confidence"] = ml_confidence

            # Insert to database
            result = self.supabase.table("trade_logs").insert(trade_data).execute()

            if result.data:
                trade_id = result.data[0]["trade_id"]
                self.active_trades[trade_id] = trade_data
                logger.info(
                    f"Opened trade {trade_id}: {symbol} {strategy_name} @ ${entry_price:.2f}"
                )
                return trade_id

            return None

        except Exception as e:
            logger.error(f"Error logging trade open: {e}")
            return None

    def close_trade(
        self,
        trade_id: int,
        exit_price: float,
        exit_reason: str,
        market_regime: Optional[str] = None,
        btc_price: Optional[float] = None,
    ) -> bool:
        """
        Log trade closing and calculate outcomes

        Args:
            trade_id: ID of trade to close
            exit_price: Exit price
            exit_reason: Reason for exit (take_profit, stop_loss, timeout, etc)
            market_regime: Current market regime
            btc_price: Current BTC price

        Returns:
            True if successful
        """
        try:
            # Get trade info
            result = (
                self.supabase.table("trade_logs")
                .select("*")
                .eq("trade_id", trade_id)
                .execute()
            )

            if not result.data:
                logger.error(f"Trade {trade_id} not found")
                return False

            trade = result.data[0]

            # Calculate outcomes
            entry_price = float(trade["entry_price"])
            position_size = float(trade["position_size"])
            capital_used = float(trade["capital_used"])

            # Calculate P&L
            pnl_amount = (exit_price - entry_price) * position_size
            pnl_percentage = ((exit_price - entry_price) / entry_price) * 100

            # Calculate hold time
            # Handle timezone-aware datetime from database
            opened_at_str = trade["opened_at"]
            if isinstance(opened_at_str, str):
                # Remove timezone info for consistent comparison
                opened_at_str = opened_at_str.replace("Z", "").replace("+00:00", "")
                if "T" in opened_at_str:
                    opened_at = datetime.fromisoformat(opened_at_str)
                else:
                    opened_at = datetime.fromisoformat(opened_at_str)
            else:
                opened_at = opened_at_str

            closed_at = datetime.utcnow()
            hold_time_hours = (closed_at - opened_at).total_seconds() / 3600

            # Determine status
            if pnl_amount > 0:
                status = "CLOSED_WIN"
            elif pnl_amount < 0:
                status = "CLOSED_LOSS"
            else:
                status = "CLOSED_EVEN"

            # Calculate prediction accuracy
            prediction_accuracy = self._calculate_prediction_accuracy(
                trade, exit_price, hold_time_hours, status
            )

            # Update trade record
            update_data = {
                "exit_price": exit_price,
                "closed_at": closed_at.isoformat(),
                "hold_time_hours": hold_time_hours,
                "status": status,
                "exit_reason": exit_reason,
                "pnl_amount": pnl_amount,
                "pnl_percentage": pnl_percentage,
                "prediction_accuracy": json.dumps(prediction_accuracy),
                "market_regime_at_close": market_regime,
                "btc_price_at_close": btc_price,
                "updated_at": datetime.utcnow().isoformat(),
            }

            result = (
                self.supabase.table("trade_logs")
                .update(update_data)
                .eq("trade_id", trade_id)
                .execute()
            )

            if result.data:
                # Remove from active trades
                if trade_id in self.active_trades:
                    del self.active_trades[trade_id]

                logger.info(
                    f"Closed trade {trade_id}: {status} P&L: ${pnl_amount:.2f} ({pnl_percentage:+.2f}%)"
                )

                # Log feedback for ML learning
                self._log_ml_feedback(trade_id, trade, update_data)

                return True

            return False

        except Exception as e:
            logger.error(f"Error closing trade: {e}")
            return False

    def _calculate_prediction_accuracy(
        self, trade: Dict, exit_price: float, hold_time_hours: float, status: str
    ) -> Dict:
        """Calculate how accurate the ML predictions were"""
        accuracy = {}

        # Check if win prediction was correct
        if trade.get("predicted_win_probability"):
            predicted_win = float(trade["predicted_win_probability"]) > 0.5
            actual_win = status == "CLOSED_WIN"
            accuracy["win_prediction_correct"] = predicted_win == actual_win

        # Check take profit accuracy
        if trade.get("predicted_take_profit") and status == "CLOSED_WIN":
            entry_price = float(trade["entry_price"])
            predicted_tp = entry_price * (
                1 + float(trade["predicted_take_profit"]) / 100
            )
            tp_error = abs(exit_price - predicted_tp) / predicted_tp * 100
            accuracy["take_profit_error_pct"] = tp_error

        # Check stop loss accuracy
        if trade.get("predicted_stop_loss") and status == "CLOSED_LOSS":
            entry_price = float(trade["entry_price"])
            predicted_sl = entry_price * (1 + float(trade["predicted_stop_loss"]) / 100)
            sl_error = abs(exit_price - predicted_sl) / predicted_sl * 100
            accuracy["stop_loss_error_pct"] = sl_error

        # Check hold time accuracy
        if trade.get("predicted_hold_hours"):
            predicted_hours = float(trade["predicted_hold_hours"])
            hold_error = abs(hold_time_hours - predicted_hours) / predicted_hours * 100
            accuracy["hold_time_error_pct"] = hold_error

        return accuracy

    def _log_ml_feedback(self, trade_id: int, original_trade: Dict, outcome: Dict):
        """Log feedback for ML model retraining"""
        try:
            feedback = {
                "timestamp": datetime.utcnow().isoformat(),
                "trade_id": trade_id,
                "scan_id": original_trade.get("scan_id"),
                "symbol": original_trade["symbol"],
                "strategy": original_trade["strategy_name"],
                "ml_confidence": original_trade.get("ml_confidence"),
                "predicted_win_prob": original_trade.get("predicted_win_probability"),
                "actual_outcome": 1 if outcome["status"] == "CLOSED_WIN" else 0,
                "pnl_pct": outcome["pnl_percentage"],
                "hold_hours": outcome["hold_time_hours"],
                "prediction_accuracy": outcome.get("prediction_accuracy"),
            }

            logger.debug(f"ML Feedback: {feedback}")

            # This feedback can be used for model retraining
            # Could store in a separate feedback table or queue for processing

        except Exception as e:
            logger.error(f"Error logging ML feedback: {e}")

    def get_active_trades(self) -> Dict:
        """Get all currently active trades"""
        try:
            result = (
                self.supabase.table("trade_logs")
                .select("*")
                .eq("status", "OPEN")
                .execute()
            )

            if result.data:
                return {trade["trade_id"]: trade for trade in result.data}

            return {}

        except Exception as e:
            logger.error(f"Error fetching active trades: {e}")
            return {}

    def get_trade_performance(self, hours: int = 24) -> Dict:
        """Get trade performance statistics"""
        try:
            since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

            result = (
                self.supabase.table("trade_logs")
                .select("*")
                .gte("opened_at", since)
                .execute()
            )

            if not result.data:
                return {
                    "total_trades": 0,
                    "open_trades": 0,
                    "closed_trades": 0,
                    "win_rate": 0,
                    "avg_pnl_pct": 0,
                    "total_pnl": 0,
                }

            trades = result.data
            closed_trades = [t for t in trades if t["status"].startswith("CLOSED_")]
            wins = [t for t in closed_trades if t["status"] == "CLOSED_WIN"]

            stats = {
                "total_trades": len(trades),
                "open_trades": len([t for t in trades if t["status"] == "OPEN"]),
                "closed_trades": len(closed_trades),
                "win_rate": len(wins) / len(closed_trades) if closed_trades else 0,
                "avg_pnl_pct": (
                    sum(float(t["pnl_percentage"] or 0) for t in closed_trades)
                    / len(closed_trades)
                    if closed_trades
                    else 0
                ),
                "total_pnl": sum(float(t["pnl_amount"] or 0) for t in closed_trades),
            }

            return stats

        except Exception as e:
            logger.error(f"Error getting trade performance: {e}")
            return {}
