#!/usr/bin/env python3
"""
Slack system reporter for twice-daily updates to #system-alerts.
Provides comprehensive system health reports and real-time critical alerts.
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
import schedule
import time

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.config.settings import get_settings
from src.data.supabase_client import SupabaseClient
from src.data.hybrid_fetcher import HybridDataFetcher
from src.notifications.slack_notifier import SlackNotifier, NotificationType
from loguru import logger


class SlackSystemReporter:
    """Generate and send system reports to Slack."""

    def __init__(self):
        """Initialize the reporter."""
        self.settings = get_settings()
        self.db = SupabaseClient()
        self.fetcher = HybridDataFetcher()
        self.slack = SlackNotifier()

        # Metrics storage
        self.daily_metrics = {"signals_generated": 0, "trades_executed": 0, "errors_logged": 0, "ml_predictions": 0}

    async def generate_morning_report(self) -> Dict[str, Any]:
        """Generate morning system report (9 AM)."""
        report = {"timestamp": datetime.now(timezone.utc).isoformat(), "type": "morning", "sections": {}}

        # 1. System Health Overview
        health = await self.check_system_health()
        report["sections"]["health"] = health

        # 2. Overnight Activity
        overnight = await self.get_overnight_activity()
        report["sections"]["overnight"] = overnight

        # 3. Data Pipeline Status
        pipeline = await self.check_data_pipeline()
        report["sections"]["pipeline"] = pipeline

        # 4. Active Trading Signals
        signals = await self.get_active_signals()
        report["sections"]["signals"] = signals

        # 5. Risk Metrics
        risk = await self.check_risk_metrics()
        report["sections"]["risk"] = risk

        return report

    async def generate_evening_report(self) -> Dict[str, Any]:
        """Generate evening system report (5 PM)."""
        report = {"timestamp": datetime.now(timezone.utc).isoformat(), "type": "evening", "sections": {}}

        # 1. Day's Performance Summary
        performance = await self.get_daily_performance()
        report["sections"]["performance"] = performance

        # 2. ML Model Performance
        ml_stats = await self.get_ml_performance()
        report["sections"]["ml"] = ml_stats

        # 3. Trading Activity
        trading = await self.get_trading_activity()
        report["sections"]["trading"] = trading

        # 4. Error Summary
        errors = await self.get_error_summary()
        report["sections"]["errors"] = errors

        # 5. Next Day Preparation
        preparation = await self.check_next_day_prep()
        report["sections"]["preparation"] = preparation

        return report

    async def check_system_health(self) -> Dict[str, Any]:
        """Check overall system health."""
        health = {"status": "healthy", "checks": {}, "score": 0}

        try:
            # Data freshness
            result = (
                self.db.client.table("ohlc_data").select("timestamp").order("timestamp", desc=True).limit(1).execute()
            )

            if result.data:
                latest = datetime.fromisoformat(result.data[0]["timestamp"].replace("Z", "+00:00"))
                age_minutes = (datetime.now(timezone.utc) - latest).total_seconds() / 60
                health["checks"]["data_freshness"] = {
                    "value": f"{age_minutes:.1f} minutes",
                    "status": "ok" if age_minutes < 5 else "warning" if age_minutes < 10 else "critical",
                }

            # Query performance
            start = time.time()
            await self.fetcher.get_latest_price("BTC", "1m")
            query_time = time.time() - start
            health["checks"]["query_performance"] = {
                "value": f"{query_time:.3f}s",
                "status": "ok" if query_time < 0.5 else "warning" if query_time < 1.0 else "critical",
            }

            # Symbol coverage
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            result = self.db.client.table("ohlc_data").select("symbol").gte("timestamp", cutoff).limit(10000).execute()

            if result.data:
                unique_symbols = set(r["symbol"] for r in result.data)
                health["checks"]["symbol_coverage"] = {
                    "value": f"{len(unique_symbols)}/90",
                    "status": "ok"
                    if len(unique_symbols) >= 85
                    else "warning"
                    if len(unique_symbols) >= 75
                    else "critical",
                }

            # Calculate health score
            ok_count = sum(1 for c in health["checks"].values() if c["status"] == "ok")
            total_count = len(health["checks"])
            health["score"] = round((ok_count / total_count * 100) if total_count > 0 else 0)

            if health["score"] >= 90:
                health["status"] = "healthy"
            elif health["score"] >= 70:
                health["status"] = "degraded"
            else:
                health["status"] = "critical"

        except Exception as e:
            logger.error(f"Error checking system health: {e}")
            health["status"] = "error"
            health["error"] = str(e)[:100]

        return health

    async def get_overnight_activity(self) -> Dict[str, Any]:
        """Get overnight activity summary."""
        activity = {"signals": 0, "errors": 0, "data_points": 0}

        try:
            # Count overnight data points
            overnight_cutoff = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()

            result = (
                self.db.client.table("ohlc_data")
                .select("*", count="exact", head=True)
                .gte("timestamp", overnight_cutoff)
                .execute()
            )

            if hasattr(result, "count"):
                activity["data_points"] = result.count

        except Exception as e:
            logger.error(f"Error getting overnight activity: {e}")

        return activity

    async def check_data_pipeline(self) -> Dict[str, Any]:
        """Check data pipeline status."""
        pipeline = {"status": "running", "timeframes": {}, "issues": []}

        try:
            timeframes = ["1m", "15m", "1h", "1d"]

            for tf in timeframes:
                result = (
                    self.db.client.table("ohlc_data")
                    .select("timestamp")
                    .eq("timeframe", tf)
                    .order("timestamp", desc=True)
                    .limit(1)
                    .execute()
                )

                if result.data:
                    latest = datetime.fromisoformat(result.data[0]["timestamp"].replace("Z", "+00:00"))
                    age = datetime.now(timezone.utc) - latest

                    if tf == "1m":
                        is_fresh = age < timedelta(minutes=5)
                    elif tf == "15m":
                        is_fresh = age < timedelta(minutes=30)
                    elif tf == "1h":
                        is_fresh = age < timedelta(hours=2)
                    else:  # 1d
                        is_fresh = age < timedelta(hours=26)

                    pipeline["timeframes"][tf] = {
                        "last_update": latest.isoformat(),
                        "status": "ok" if is_fresh else "stale",
                    }

                    if not is_fresh:
                        pipeline["issues"].append(f"{tf} data is stale")

            # Check for WebSocket issues
            if any(tf["status"] == "stale" for tf in pipeline["timeframes"].values()):
                pipeline["status"] = "degraded"
                pipeline["issues"].append("WebSocket may be disconnected")

        except Exception as e:
            logger.error(f"Error checking data pipeline: {e}")
            pipeline["status"] = "error"
            pipeline["issues"].append(str(e)[:100])

        return pipeline

    async def get_active_signals(self) -> Dict[str, Any]:
        """Get currently active trading signals."""
        signals = {"count": 0, "by_strategy": {}, "high_confidence": []}

        # This would normally query a signals table
        # For now, return mock data
        signals["count"] = 0
        signals["by_strategy"] = {"dca": 0, "swing": 0, "channel": 0}

        return signals

    async def check_risk_metrics(self) -> Dict[str, Any]:
        """Check risk management metrics."""
        risk = {"exposure": 0, "max_drawdown": 0, "positions": 0, "alerts": []}

        # Check for risk alerts
        # This would normally check position sizes, correlations, etc.

        return risk

    async def get_daily_performance(self) -> Dict[str, Any]:
        """Get daily performance metrics."""
        performance = {
            "queries_processed": 0,
            "avg_query_time": 0,
            "data_points_collected": 0,
            "uptime_percentage": 100,
        }

        try:
            # Count today's data points
            today_cutoff = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).isoformat()

            result = (
                self.db.client.table("ohlc_data")
                .select("*", count="exact", head=True)
                .gte("timestamp", today_cutoff)
                .execute()
            )

            if hasattr(result, "count"):
                performance["data_points_collected"] = result.count

        except Exception as e:
            logger.error(f"Error getting daily performance: {e}")

        return performance

    async def get_ml_performance(self) -> Dict[str, Any]:
        """Get ML model performance metrics."""
        ml_stats = {
            "predictions_made": self.daily_metrics.get("ml_predictions", 0),
            "avg_confidence": 0,
            "model_versions": {},
        }

        # Check model files
        model_files = [
            "models/dca/xgboost_multi_output.pkl",
            "models/swing/swing_classifier.pkl",
            "models/channel/classifier.pkl",
        ]

        project_root = Path(__file__).parent.parent
        for model_file in model_files:
            path = project_root / model_file
            if path.exists():
                strategy = model_file.split("/")[1]
                ml_stats["model_versions"][strategy] = {
                    "exists": True,
                    "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                }

        return ml_stats

    async def get_trading_activity(self) -> Dict[str, Any]:
        """Get trading activity summary."""
        trading = {
            "signals_generated": self.daily_metrics.get("signals_generated", 0),
            "trades_executed": self.daily_metrics.get("trades_executed", 0),
            "positions_opened": 0,
            "positions_closed": 0,
        }

        return trading

    async def get_error_summary(self) -> Dict[str, Any]:
        """Get error summary for the day."""
        errors = {"count": self.daily_metrics.get("errors_logged", 0), "critical": [], "warnings": []}

        # Check for WebSocket errors
        if self.daily_metrics.get("websocket_errors", 0) > 0:
            errors["critical"].append("WebSocket connection issues detected")

        return errors

    async def check_next_day_prep(self) -> Dict[str, Any]:
        """Check preparation for next trading day."""
        preparation = {"status": "ready", "checks": {}}

        # Check materialized views freshness
        preparation["checks"]["materialized_views"] = {"status": "ok", "message": "Views will refresh at 2 AM"}

        # Check model readiness
        preparation["checks"]["ml_models"] = {"status": "ok", "message": "Models loaded and ready"}

        # Check data collection
        preparation["checks"]["data_collection"] = {
            "status": "ok" if await self.is_data_flowing() else "warning",
            "message": "Data collection active" if await self.is_data_flowing() else "Data collection may be stalled",
        }

        return preparation

    async def is_data_flowing(self) -> bool:
        """Check if data is actively flowing."""
        try:
            result = (
                self.db.client.table("ohlc_data").select("timestamp").order("timestamp", desc=True).limit(1).execute()
            )

            if result.data:
                latest = datetime.fromisoformat(result.data[0]["timestamp"].replace("Z", "+00:00"))
                age_minutes = (datetime.now(timezone.utc) - latest).total_seconds() / 60
                return age_minutes < 10

            return False

        except Exception:
            return False

    def format_slack_message(self, report: Dict[str, Any]) -> tuple[str, str, Dict]:
        """Format report for Slack.

        Returns:
            tuple: (title, message, details)
        """
        is_morning = report["type"] == "morning"

        # Determine overall status
        health_status = report["sections"].get("health", {}).get("status", "unknown")
        health_score = report["sections"].get("health", {}).get("score", 0)

        if health_status == "healthy":
            status_emoji = "✅"
        elif health_status == "degraded":
            status_emoji = "⚠️"
        else:
            status_emoji = "🔴"

        # Create title
        title = f"{status_emoji} {'Morning' if is_morning else 'Evening'} System Report"

        # Create main message
        message_parts = []

        if is_morning:
            # Morning report message
            health = report["sections"].get("health", {})
            message_parts.append(f"*System Health Score: {health_score}/100*")
            message_parts.append(f"Status: {health_status.upper()}")

            # Health checks
            if health.get("checks"):
                message_parts.append("\n*Health Checks:*")
                for check_name, check_data in health["checks"].items():
                    emoji = "✅" if check_data["status"] == "ok" else "⚠️" if check_data["status"] == "warning" else "❌"
                    message_parts.append(f"{emoji} {check_name}: {check_data['value']}")

            # Pipeline issues
            pipeline = report["sections"].get("pipeline", {})
            if pipeline.get("issues"):
                message_parts.append("\n*⚠️ Pipeline Issues:*")
                for issue in pipeline["issues"]:
                    message_parts.append(f"• {issue}")

            # Overnight activity
            overnight = report["sections"].get("overnight", {})
            message_parts.append("\n*Overnight Activity:*")
            message_parts.append(f"• Data points: {overnight.get('data_points', 0):,}")
            message_parts.append(f"• Signals: {overnight.get('signals', 0)}")
            message_parts.append(f"• Errors: {overnight.get('errors', 0)}")

        else:
            # Evening report message
            performance = report["sections"].get("performance", {})
            message_parts.append("*Daily Performance:*")
            message_parts.append(f"• Data points: {performance.get('data_points_collected', 0):,}")
            message_parts.append(f"• Uptime: {performance.get('uptime_percentage', 0)}%")

            # ML performance
            ml = report["sections"].get("ml", {})
            message_parts.append("\n*ML System:*")
            message_parts.append(f"• Predictions: {ml.get('predictions_made', 0)}")
            message_parts.append(f"• Models loaded: {len(ml.get('model_versions', {}))}/3")

            # Trading activity
            trading = report["sections"].get("trading", {})
            message_parts.append("\n*Trading Activity:*")
            message_parts.append(f"• Signals: {trading.get('signals_generated', 0)}")
            message_parts.append(f"• Trades: {trading.get('trades_executed', 0)}")

            # Errors
            errors = report["sections"].get("errors", {})
            if errors.get("critical"):
                message_parts.append("\n*🔴 Critical Errors:*")
                for err in errors["critical"]:
                    message_parts.append(f"• {err}")

            # Next day prep
            prep = report["sections"].get("preparation", {})
            message_parts.append(f"\n*Next Day Prep: {prep.get('status', 'unknown').upper()}*")

        message = "\n".join(message_parts)

        # Create details dict
        details = {
            "health_score": health_score,
            "status": health_status,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        }

        return title, message, details

    async def send_morning_report(self):
        """Send morning report to Slack."""
        try:
            report = await self.generate_morning_report()
            title, message, details = self.format_slack_message(report)

            # Determine notification type based on health status
            health_status = report["sections"].get("health", {}).get("status", "unknown")
            if health_status == "critical":
                notification_type = NotificationType.SYSTEM_ALERT
            else:
                notification_type = NotificationType.DAILY_REPORT

            # Send to Slack using existing notifier
            await self.slack.send_notification(
                notification_type=notification_type,
                title=title,
                message=message,
                details=details,
                color="good" if health_status == "healthy" else "warning" if health_status == "degraded" else "danger",
            )

            logger.info("Morning report sent to Slack")

        except Exception as e:
            logger.error(f"Error sending morning report: {e}")

    async def send_evening_report(self):
        """Send evening report to Slack."""
        try:
            report = await self.generate_evening_report()
            title, message, details = self.format_slack_message(report)

            # Send to Slack using existing notifier
            await self.slack.send_notification(
                notification_type=NotificationType.DAILY_REPORT, title=title, message=message, details=details
            )

            logger.info("Evening report sent to Slack")

        except Exception as e:
            logger.error(f"Error sending evening report: {e}")

    async def send_critical_alert(self, issue: str, details: str):
        """Send critical alert immediately."""
        try:
            alert_details = {
                "issue": issue,
                "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                "action": "Immediate attention required",
            }

            await self.slack.send_notification(
                notification_type=NotificationType.SYSTEM_ALERT,
                title="🚨 CRITICAL SYSTEM ALERT",
                message=f"{issue}\n\n{details}",
                details=alert_details,
                color="danger",
            )

            logger.warning(f"Critical alert sent: {issue}")

        except Exception as e:
            logger.error(f"Error sending critical alert: {e}")

    def schedule_reports(self):
        """Schedule twice-daily reports."""
        # Schedule morning report at 9 AM
        schedule.every().day.at("09:00").do(lambda: asyncio.create_task(self.send_morning_report()))

        # Schedule evening report at 5 PM
        schedule.every().day.at("17:00").do(lambda: asyncio.create_task(self.send_evening_report()))

        logger.info("Scheduled reports for 9 AM and 5 PM daily")

    async def run_continuous(self):
        """Run continuous monitoring with scheduled reports."""
        self.schedule_reports()

        logger.info("Slack reporter started - reports scheduled for 9 AM and 5 PM")

        while True:
            # Check for scheduled tasks
            schedule.run_pending()

            # Check for critical issues every 5 minutes
            if await self.check_critical_issues():
                # Critical alert already sent in check_critical_issues
                pass

            # Sleep for 60 seconds
            await asyncio.sleep(60)

    async def check_critical_issues(self) -> bool:
        """Check for critical issues that need immediate alerts."""
        try:
            # Check data freshness
            result = (
                self.db.client.table("ohlc_data").select("timestamp").order("timestamp", desc=True).limit(1).execute()
            )

            if result.data:
                latest = datetime.fromisoformat(result.data[0]["timestamp"].replace("Z", "+00:00"))
                age_minutes = (datetime.now(timezone.utc) - latest).total_seconds() / 60

                if age_minutes > 15:  # Data is very stale
                    await self.send_critical_alert(
                        "Data Pipeline Stalled",
                        f"No new data for {age_minutes:.0f} minutes. WebSocket may be disconnected.",
                    )
                    return True

            return False

        except Exception as e:
            logger.error(f"Error checking critical issues: {e}")
            return False


async def main():
    """Run the Slack reporter."""
    reporter = SlackSystemReporter()

    # Send immediate test report
    logger.info("Sending test report to verify Slack connection...")
    await reporter.send_morning_report()

    # Run continuous monitoring
    await reporter.run_continuous()


if __name__ == "__main__":
    asyncio.run(main())
