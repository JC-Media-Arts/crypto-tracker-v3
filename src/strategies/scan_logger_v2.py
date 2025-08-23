"""
Enhanced Scan History Logger for ML Learning with Trade Linking
Logs every scan decision to enable continuous learning and threshold optimization
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from loguru import logger
import json


class ScanLoggerV2:
    """Enhanced scan logger that returns scan_id for trade linking"""

    def __init__(self, supabase_client):
        """
        Initialize the scan logger

        Args:
            supabase_client: Supabase client for database operations
        """
        self.supabase = supabase_client
        self.batch = []  # For batch inserts
        self.batch_size = 100  # Insert in batches for efficiency

    def log_scan_decision(
        self,
        symbol: str,
        strategy_name: str,
        decision: str,
        reason: str,
        features: Dict,
        ml_confidence: Optional[float] = None,
        ml_predictions: Optional[Dict] = None,
        setup_data: Optional[Dict] = None,
        market_regime: Optional[str] = None,
        btc_price: Optional[float] = None,
        thresholds_used: Optional[Dict] = None,
        proposed_position_size: Optional[float] = None,
        proposed_capital: Optional[float] = None,
        immediate_insert: bool = False,
    ) -> Optional[int]:
        """
        Log a single scan decision

        Args:
            symbol: Trading symbol (e.g., 'BTC', 'ETH')
            strategy_name: Strategy type ('DCA', 'SWING', 'CHANNEL')
            decision: Decision made ('TAKE', 'SKIP', 'NEAR_MISS')
            reason: Reason for decision
            features: All calculated features at scan time
            ml_confidence: ML model confidence score
            ml_predictions: Full ML predictions (TP, SL, etc.)
            setup_data: Setup-specific data if detected
            market_regime: Current market regime
            btc_price: Current BTC price
            thresholds_used: Active thresholds at decision time
            proposed_position_size: Proposed position size if calculated
            proposed_capital: Proposed capital allocation if calculated
            immediate_insert: If True, insert immediately and return scan_id

        Returns:
            scan_id if immediate_insert=True and decision='TAKE', None otherwise
        """
        try:
            # Prepare the record
            record = {
                "timestamp": datetime.utcnow().isoformat(),
                "symbol": symbol,
                "strategy_name": strategy_name.upper(),
                "decision": decision,
                "reason": reason,
                "features": json.dumps(features) if features else None,
                "ml_confidence": ml_confidence,
                "ml_predictions": (
                    json.dumps(ml_predictions) if ml_predictions else None
                ),
                "setup_data": json.dumps(setup_data) if setup_data else None,
                "market_regime": market_regime,
                "btc_price": btc_price,
                "thresholds_used": (
                    json.dumps(thresholds_used) if thresholds_used else None
                ),
                "proposed_position_size": proposed_position_size,
                "proposed_capital": proposed_capital,
            }

            # If this is a TAKE decision and we need immediate insert for trade linking
            if immediate_insert and decision == "TAKE":
                result = self.supabase.table("scan_history").insert(record).execute()
                if result.data and len(result.data) > 0:
                    scan_id = result.data[0].get("scan_id")
                    logger.debug(f"Logged TAKE decision with scan_id: {scan_id}")
                    return scan_id
                return None

            # Otherwise add to batch for later insert
            self.batch.append(record)

            # Insert if batch is full
            if len(self.batch) >= self.batch_size:
                self.flush()

            return None

        except Exception as e:
            logger.error(f"Error logging scan decision: {e}")
            return None

    def flush(self) -> bool:
        """
        Flush all pending scan records to database

        Returns:
            True if successful
        """
        if not self.batch:
            return True

        try:
            # Insert batch to database
            result = self.supabase.table("scan_history").insert(self.batch).execute()

            if result.data:
                logger.debug(f"Flushed {len(self.batch)} scan records to database")
                self.batch = []  # Clear batch
                return True
            else:
                logger.error("Failed to flush scan records - no data returned")
                return False

        except Exception as e:
            logger.error(f"Error flushing scan records: {e}")
            return False

    def get_decision_stats(self, hours: int = 24) -> Dict:
        """
        Get statistics about scan decisions

        Args:
            hours: Number of hours to look back

        Returns:
            Dictionary with decision statistics
        """
        try:
            since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

            query = self.supabase.table("scan_history").select("*")
            query = query.gte("timestamp", since)
            result = query.execute()

            if not result.data:
                return {
                    "total_scans": 0,
                    "decisions": {},
                    "strategies": {},
                    "avg_confidence": 0,
                }

            # Analyze the data
            total = len(result.data)
            decisions = {}
            strategies = {}
            confidences = []

            for record in result.data:
                # Count decisions
                decision = record.get("decision", "UNKNOWN")
                decisions[decision] = decisions.get(decision, 0) + 1

                # Count strategies
                strategy = record.get("strategy_name", "UNKNOWN")
                strategies[strategy] = strategies.get(strategy, 0) + 1

                # Collect confidences
                if record.get("ml_confidence"):
                    confidences.append(float(record["ml_confidence"]))

            return {
                "total_scans": total,
                "decisions": decisions,
                "strategies": strategies,
                "avg_confidence": (
                    sum(confidences) / len(confidences) if confidences else 0
                ),
                "symbols_scanned": len(set(r.get("symbol") for r in result.data)),
            }

        except Exception as e:
            logger.error(f"Error getting decision stats: {e}")
            return {}

    def get_near_misses(self, hours: int = 24, limit: int = 20) -> List[Dict]:
        """
        Get recent near-miss opportunities

        Args:
            hours: Hours to look back
            limit: Maximum number of results

        Returns:
            List of near-miss records
        """
        try:
            since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

            query = (
                self.supabase.table("scan_history")
                .select("*")
                .eq("decision", "NEAR_MISS")
                .gte("timestamp", since)
                .order("ml_confidence", desc=True)
                .limit(limit)
            )

            result = query.execute()

            if result.data:
                return result.data

            return []

        except Exception as e:
            logger.error(f"Error getting near misses: {e}")
            return []
