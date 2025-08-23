"""
Emergency data fetcher that works without indexes.
Uses aggressive limits and date filtering to avoid timeouts.
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
from loguru import logger

from src.config.settings import get_settings
from src.data.supabase_client import SupabaseClient


class EmergencyDataFetcher:
    """Emergency fetcher that works around missing indexes."""

    def __init__(self):
        """Initialize emergency fetcher."""
        self.settings = get_settings()
        self.db = SupabaseClient()

    async def get_latest_price_emergency(self, symbol: str) -> Optional[float]:
        """
        Get latest price with minimal database load.
        """
        try:
            # Only look at last hour to avoid timeout
            one_hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()

            result = (
                self.db.client.table("ohlc_data")
                .select("close, timestamp")
                .eq("symbol", symbol)
                .eq("timeframe", "1m")
                .gte("timestamp", one_hour_ago)
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )

            if result.data:
                return result.data[0]["close"]

            # Fallback to hourly if no 1m data
            result = (
                self.db.client.table("ohlc_data")
                .select("close, timestamp")
                .eq("symbol", symbol)
                .eq("timeframe", "1h")
                .gte("timestamp", one_hour_ago)
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )

            return result.data[0]["close"] if result.data else None

        except Exception as e:
            logger.error(f"Emergency fetch failed for {symbol}: {e}")
            return None

    async def get_recent_data_emergency(self, symbol: str, hours: int = 24) -> List[Dict]:
        """
        Get recent data with aggressive limits to avoid timeout.
        """
        try:
            # Limit to max 24 hours to avoid timeout
            hours = min(hours, 24)
            cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

            # Use 15m timeframe instead of 1m to reduce data volume
            result = (
                self.db.client.table("ohlc_data")
                .select("timestamp, open, high, low, close, volume")
                .eq("symbol", symbol)
                .eq("timeframe", "15m")
                .gte("timestamp", cutoff)
                .order("timestamp", desc=False)
                .execute()
            )

            return result.data

        except Exception as e:
            logger.error(f"Emergency fetch failed for {symbol}: {e}")

            # Fallback to even less data
            try:
                cutoff = (datetime.utcnow() - timedelta(hours=6)).isoformat()
                result = (
                    self.db.client.table("ohlc_data")
                    .select("timestamp, close")
                    .eq("symbol", symbol)
                    .eq("timeframe", "1h")
                    .gte("timestamp", cutoff)
                    .order("timestamp", desc=False)
                    .execute()
                )
                return result.data
            except:
                return []

    async def get_ml_features_emergency(self, symbol: str) -> Dict:
        """
        Get minimal data for ML features without timeout.
        """
        try:
            # Only get last 24 hours of hourly data
            cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()

            result = (
                self.db.client.table("ohlc_data")
                .select("timestamp, close, high, low, volume")
                .eq("symbol", symbol)
                .eq("timeframe", "1h")
                .gte("timestamp", cutoff)
                .order("timestamp", desc=True)
                .limit(24)
                .execute()
            )

            if result.data:
                return {
                    "prices": [r["close"] for r in result.data],
                    "highs": [r["high"] for r in result.data],
                    "lows": [r["low"] for r in result.data],
                    "volumes": [r["volume"] for r in result.data],
                    "timestamps": [r["timestamp"] for r in result.data],
                }

            return {
                "prices": [],
                "highs": [],
                "lows": [],
                "volumes": [],
                "timestamps": [],
            }

        except Exception as e:
            logger.error(f"Emergency ML fetch failed for {symbol}: {e}")
            return {
                "prices": [],
                "highs": [],
                "lows": [],
                "volumes": [],
                "timestamps": [],
            }

    async def get_trading_signal_emergency(self, symbol: str) -> Dict:
        """
        Get bare minimum data for trading signals.
        """
        try:
            # Just get last 4 hours of 15m data (16 candles)
            cutoff = (datetime.utcnow() - timedelta(hours=4)).isoformat()

            result = (
                self.db.client.table("ohlc_data")
                .select("timestamp, close, volume")
                .eq("symbol", symbol)
                .eq("timeframe", "15m")
                .gte("timestamp", cutoff)
                .order("timestamp", desc=True)
                .execute()
            )

            if result.data and len(result.data) >= 2:
                current = result.data[0]["close"]
                previous = result.data[1]["close"]
                change_pct = ((current - previous) / previous) * 100

                return {
                    "symbol": symbol,
                    "price": current,
                    "change_24h": change_pct,
                    "volume": result.data[0]["volume"],
                    "timestamp": result.data[0]["timestamp"],
                    "has_data": True,
                }

            return {"symbol": symbol, "has_data": False}

        except Exception as e:
            logger.error(f"Emergency signal fetch failed for {symbol}: {e}")
            return {"symbol": symbol, "has_data": False, "error": str(e)}
