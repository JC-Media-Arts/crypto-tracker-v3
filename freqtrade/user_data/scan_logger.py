"""
Scan Logger for Freqtrade
Captures trading decisions for ML training pipeline
"""

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from supabase import create_client, Client
from collections import deque
import threading
import time

logger = logging.getLogger(__name__)


class ScanLogger:
    """
    Logs Freqtrade scanning decisions to Supabase for ML training
    Implements batching for efficient database writes
    """

    def __init__(self, batch_size: int = 500, flush_interval: int = 300):
        """
        Initialize the scan logger

        Args:
            batch_size: Number of records to batch before writing
            flush_interval: Seconds between forced flushes
        """
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")

        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment")

        self.client: Client = create_client(self.supabase_url, self.supabase_key)

        # Batching configuration
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.scan_buffer = deque()
        self.buffer_lock = threading.Lock()

        # Start background flush thread
        self.flush_thread = threading.Thread(target=self._flush_worker, daemon=True)
        self.flush_thread.start()

        logger.info(
            f"ScanLogger initialized with batch_size={batch_size}, flush_interval={flush_interval}s"
        )

    def log_scan(
        self,
        symbol: str,
        strategy: str,
        decision: str,
        features: Dict[str, Any],
        metadata: Dict[str, Any] = None,
    ):
        """
        Log a scan decision

        Args:
            symbol: Trading symbol (e.g., "BTC")
            strategy: Strategy name (e.g., "CHANNEL")
            decision: Decision made ("TAKE", "SKIP", "EXIT")
            features: Feature values used in decision
            metadata: Additional metadata
        """

        # Create scan record
        scan_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol.replace("/USDT", ""),  # Remove pair suffix
            "strategy_name": strategy,  # Use correct column name
            "decision": decision,
            "features": json.dumps(features),
            "reason": metadata.get("reason", "") if metadata else "",  # Add reason field
            "ml_confidence": features.get("ml_confidence", 0.0),  # Add ML confidence
        }

        # Add to buffer
        with self.buffer_lock:
            self.scan_buffer.append(scan_record)

            # Flush if buffer is full
            if len(self.scan_buffer) >= self.batch_size:
                self._flush_buffer()

    def log_entry_analysis(
        self,
        pair: str,
        dataframe_row: Dict[str, Any],
        entry_signal: bool,
        strategy: str = "CHANNEL",
    ):
        """
        Log entry analysis from strategy

        Args:
            pair: Trading pair
            dataframe_row: Row from strategy dataframe
            entry_signal: Whether entry signal was generated
            strategy: Strategy name
        """

        features = {
            "channel_position": dataframe_row.get("channel_position", 0),
            "rsi": dataframe_row.get("rsi", 50),
            "volume_ratio": dataframe_row.get("volume_ratio", 1),
            "volatility": dataframe_row.get("volatility", 0),
            "price_drop_pct": dataframe_row.get("price_drop_pct", 0),
            "bb_upper": dataframe_row.get("bb_upper", 0),
            "bb_lower": dataframe_row.get("bb_lower", 0),
            "close": dataframe_row.get("close", 0),
            "volume": dataframe_row.get("volume", 0),
        }

        decision = "TAKE" if entry_signal else "SKIP"

        self.log_scan(
            symbol=pair,
            strategy=strategy,
            decision=decision,
            features=features,
            metadata={"scan_type": "entry_analysis"},
        )

    def log_exit_analysis(
        self,
        pair: str,
        dataframe_row: Dict[str, Any],
        exit_signal: bool,
        strategy: str = "CHANNEL",
    ):
        """
        Log exit analysis from strategy

        Args:
            pair: Trading pair
            dataframe_row: Row from strategy dataframe
            exit_signal: Whether exit signal was generated
            strategy: Strategy name
        """

        features = {
            "channel_position": dataframe_row.get("channel_position", 0),
            "rsi": dataframe_row.get("rsi", 50),
            "current_profit": dataframe_row.get("current_profit", 0),
            "position_duration_hours": dataframe_row.get("position_duration_hours", 0),
        }

        decision = "EXIT" if exit_signal else "HOLD"

        self.log_scan(
            symbol=pair,
            strategy=strategy,
            decision=decision,
            features=features,
            metadata={"scan_type": "exit_analysis"},
        )

    def _flush_buffer(self):
        """Flush the scan buffer to database"""

        if not self.scan_buffer:
            return

        # Copy buffer and clear
        records_to_insert = list(self.scan_buffer)
        self.scan_buffer.clear()

        try:
            # Insert batch to database
            response = (
                self.client.table("scan_history").insert(records_to_insert).execute()
            )
            logger.info(f"Flushed {len(records_to_insert)} scan records to database")

        except Exception as e:
            logger.error(f"Error flushing scan buffer: {e}")
            # Re-add records to buffer on failure
            self.scan_buffer.extend(records_to_insert)

    def _flush_worker(self):
        """Background worker to periodically flush buffer"""

        while True:
            time.sleep(self.flush_interval)

            with self.buffer_lock:
                if self.scan_buffer:
                    logger.debug(f"Periodic flush: {len(self.scan_buffer)} records")
                    self._flush_buffer()

    def flush(self):
        """Force flush the buffer"""

        with self.buffer_lock:
            self._flush_buffer()

    def get_recent_scans(self, symbol: str = None, limit: int = 100) -> List[Dict]:
        """
        Get recent scan history

        Args:
            symbol: Filter by symbol (optional)
            limit: Number of records to return

        Returns:
            List of scan records
        """

        try:
            query = self.client.table("scan_history").select("*")

            if symbol:
                query = query.eq("symbol", symbol.replace("/USDT", ""))

            response = query.order("timestamp", desc=True).limit(limit).execute()

            return response.data

        except Exception as e:
            logger.error(f"Error fetching recent scans: {e}")
            return []

    def get_scan_statistics(
        self, strategy: str = "CHANNEL", hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get scan statistics for a strategy

        Args:
            strategy: Strategy name
            hours: Hours to look back

        Returns:
            Statistics dictionary
        """

        try:
            # Calculate time range
            start_time = datetime.now(timezone.utc) - timedelta(hours=hours)

            # Query scan history
            response = (
                self.client.table("scan_history")
                .select("decision")
                .eq("strategy", strategy)
                .gte("timestamp", start_time.isoformat())
                .execute()
            )

            if not response.data:
                return {}

            # Calculate statistics
            decisions = [r["decision"] for r in response.data]

            stats = {
                "total_scans": len(decisions),
                "take_signals": decisions.count("TAKE"),
                "skip_signals": decisions.count("SKIP"),
                "exit_signals": decisions.count("EXIT"),
                "hold_signals": decisions.count("HOLD"),
                "take_rate": decisions.count("TAKE") / len(decisions)
                if decisions
                else 0,
                "timeframe_hours": hours,
            }

            return stats

        except Exception as e:
            logger.error(f"Error calculating scan statistics: {e}")
            return {}


# Global instance for easy access
_scan_logger_instance = None


def get_scan_logger() -> ScanLogger:
    """Get or create the global scan logger instance"""
    global _scan_logger_instance

    if _scan_logger_instance is None:
        try:
            # Use smaller batch size for more frequent database writes
            _scan_logger_instance = ScanLogger(batch_size=50, flush_interval=60)
            logger.info("✅ Scan logger initialized successfully (batch_size=50, flush_interval=60s)")
        except Exception as e:
            logger.error(f"❌ Failed to initialize scan logger: {e}")
            logger.warning("⚠️ Continuing without scan logging - ML training data will not be collected")
            # Return a dummy logger that does nothing
            class DummyScanLogger:
                def log_entry_analysis(self, *args, **kwargs):
                    pass
                def log_exit_analysis(self, *args, **kwargs):
                    pass
                def flush(self):
                    pass
            _scan_logger_instance = DummyScanLogger()

    return _scan_logger_instance
