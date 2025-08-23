"""
Scan History Logger for ML Learning
Logs every scan decision to enable continuous learning and threshold optimization
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from loguru import logger
import json


class ScanLogger:
    """Logs all scan decisions for ML learning"""

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
    ) -> bool:
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

        Returns:
            True if logged successfully
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
                "ml_predictions": (json.dumps(ml_predictions) if ml_predictions else None),
                "setup_data": json.dumps(setup_data) if setup_data else None,
                "market_regime": market_regime,
                "btc_price": btc_price,
                "thresholds_used": (json.dumps(thresholds_used) if thresholds_used else None),
                "proposed_position_size": proposed_position_size,
                "proposed_capital": proposed_capital,
            }

            # Add to batch
            self.batch.append(record)

            # Insert if batch is full
            if len(self.batch) >= self.batch_size:
                self.flush()

            return True

        except Exception as e:
            logger.error(f"Error logging scan decision: {e}")
            return False

    def log_batch(self, decisions: List[Dict]) -> bool:
        """
        Log multiple scan decisions at once

        Args:
            decisions: List of decision dictionaries

        Returns:
            True if all logged successfully
        """
        try:
            for decision in decisions:
                self.log_scan_decision(**decision)
            return True
        except Exception as e:
            logger.error(f"Error logging batch: {e}")
            return False

    def flush(self) -> bool:
        """
        Flush pending records to database

        Returns:
            True if flushed successfully
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
                logger.error(f"Failed to flush scan records")
                return False

        except Exception as e:
            logger.error(f"Error flushing scan records: {e}")
            return False

    def get_recent_scans(
        self,
        symbol: Optional[str] = None,
        strategy: Optional[str] = None,
        hours: int = 24,
    ) -> List[Dict]:
        """
        Get recent scan history for analysis

        Args:
            symbol: Filter by symbol
            strategy: Filter by strategy
            hours: Hours to look back

        Returns:
            List of scan records
        """
        try:
            query = self.supabase.table("scan_history").select("*")

            if symbol:
                query = query.eq("symbol", symbol)
            if strategy:
                query = query.eq("strategy_name", strategy.upper())

            # Time filter
            from datetime import timedelta

            cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            query = query.gte("timestamp", cutoff)

            # Order and limit
            query = query.order("timestamp", desc=True).limit(1000)

            result = query.execute()
            return result.data if result.data else []

        except Exception as e:
            logger.error(f"Error fetching recent scans: {e}")
            return []

    def get_near_misses(self, confidence_threshold: float = 0.50, limit: int = 100) -> List[Dict]:
        """
        Get near-miss opportunities for threshold analysis

        Args:
            confidence_threshold: Minimum confidence to consider
            limit: Maximum records to return

        Returns:
            List of near-miss records
        """
        try:
            query = (
                self.supabase.table("scan_history")
                .select("*")
                .in_("decision", ["NEAR_MISS", "SKIP"])
                .gte("ml_confidence", confidence_threshold)
                .order("ml_confidence", desc=True)
                .limit(limit)
            )

            result = query.execute()
            return result.data if result.data else []

        except Exception as e:
            logger.error(f"Error fetching near misses: {e}")
            return []

    def get_decision_stats(self, hours: int = 24) -> Dict:
        """
        Get statistics about recent decisions

        Args:
            hours: Hours to look back

        Returns:
            Dictionary with statistics
        """
        try:
            # Get recent scans
            scans = self.get_recent_scans(hours=hours)

            if not scans:
                return {
                    "total_scans": 0,
                    "decisions": {},
                    "strategies": {},
                    "avg_confidence": 0,
                }

            # Calculate stats
            stats = {
                "total_scans": len(scans),
                "decisions": {},
                "strategies": {},
                "symbols_scanned": len(set(s["symbol"] for s in scans)),
                "avg_confidence": 0,
            }

            # Count by decision type
            for scan in scans:
                decision = scan.get("decision", "UNKNOWN")
                stats["decisions"][decision] = stats["decisions"].get(decision, 0) + 1

                strategy = scan.get("strategy_name", "UNKNOWN")
                stats["strategies"][strategy] = stats["strategies"].get(strategy, 0) + 1

            # Calculate average confidence
            confidences = [s["ml_confidence"] for s in scans if s.get("ml_confidence")]
            if confidences:
                stats["avg_confidence"] = sum(confidences) / len(confidences)

            return stats

        except Exception as e:
            logger.error(f"Error calculating decision stats: {e}")
            return {}

    def __del__(self):
        """Ensure batch is flushed on cleanup"""
        if hasattr(self, "batch") and self.batch:
            self.flush()
