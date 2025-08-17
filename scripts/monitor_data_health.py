#!/usr/bin/env python3
"""
Data Health Monitoring
Monitors OHLC data freshness, completeness, and quality
Sends alerts for critical issues
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dateutil import tz
import argparse

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.config.settings import get_settings
from src.data.supabase_client import SupabaseClient
from src.notifications.slack_notifier import SlackNotifier
from loguru import logger
import pandas as pd

# Configure logging
logger.remove()
logger.add(
    "logs/health_monitor.log",
    rotation="1 day",
    retention="7 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)
logger.add(sys.stdout, level="INFO")


class DataHealthMonitor:
    """Monitors health of OHLC data pipeline"""

    def __init__(self):
        self.settings = get_settings()
        self.supabase = SupabaseClient()
        self.slack = (
            SlackNotifier() if hasattr(self.settings, "slack_webhook_url") else None
        )

        # Health check thresholds
        self.thresholds = {
            "data_staleness": {  # Maximum age of latest data
                "1m": timedelta(minutes=15),
                "15m": timedelta(minutes=45),
                "1h": timedelta(hours=2),
                "1d": timedelta(days=2),
            },
            "min_completeness": {  # Minimum acceptable completeness %
                "1m": 95,
                "15m": 98,
                "1h": 99,
                "1d": 99,
            },
            "max_gap_duration": {  # Maximum acceptable gap duration
                "1m": timedelta(minutes=10),
                "15m": timedelta(minutes=30),
                "1h": timedelta(hours=2),
                "1d": timedelta(days=2),
            },
        }

        self.health_issues = []
        self.health_metrics = {}

    def get_priority_symbols(self) -> List[str]:
        """Get list of priority symbols to monitor closely"""
        return ["BTC", "ETH", "SOL", "BNB", "XRP"]

    def check_data_freshness(self) -> Dict:
        """Check if data is up to date"""
        freshness_results = {"status": "healthy", "issues": [], "details": {}}

        now = datetime.now(tz.UTC)
        priority_symbols = self.get_priority_symbols()

        for timeframe in ["1m", "15m", "1h", "1d"]:
            stale_symbols = []

            for symbol in priority_symbols:
                try:
                    # Get latest timestamp
                    response = (
                        self.supabase.client.table("ohlc_data")
                        .select("timestamp")
                        .eq("symbol", symbol)
                        .eq("timeframe", timeframe)
                        .order("timestamp", desc=True)
                        .limit(1)
                        .execute()
                    )

                    if response.data:
                        latest_timestamp = pd.to_datetime(response.data[0]["timestamp"])
                        if latest_timestamp.tzinfo is None:
                            latest_timestamp = latest_timestamp.replace(tzinfo=tz.UTC)

                        age = now - latest_timestamp

                        if age > self.thresholds["data_staleness"][timeframe]:
                            stale_symbols.append(
                                {
                                    "symbol": symbol,
                                    "latest": latest_timestamp.isoformat(),
                                    "age_minutes": age.total_seconds() / 60,
                                }
                            )
                    else:
                        stale_symbols.append(
                            {"symbol": symbol, "latest": None, "age_minutes": None}
                        )

                except Exception as e:
                    logger.error(
                        f"Error checking freshness for {symbol}/{timeframe}: {e}"
                    )

            if stale_symbols:
                freshness_results["status"] = "unhealthy"
                freshness_results["issues"].append(
                    {"timeframe": timeframe, "stale_symbols": stale_symbols}
                )

            freshness_results["details"][timeframe] = {
                "checked": len(priority_symbols),
                "stale": len(stale_symbols),
            }

        return freshness_results

    def check_data_quality(self) -> Dict:
        """Check for data quality issues"""
        quality_results = {"status": "healthy", "issues": [], "details": {}}

        # Check for impossible values in recent data
        try:
            # Get recent data
            since = (datetime.now(tz.UTC) - timedelta(hours=1)).isoformat()

            response = (
                self.supabase.client.table("ohlc_data")
                .select("symbol", "timeframe", "open", "high", "low", "close", "volume")
                .gte("timestamp", since)
                .limit(1000)
                .execute()
            )

            if response.data:
                df = pd.DataFrame(response.data)

                # Check for invalid OHLC relationships
                invalid_ohlc = df[
                    (df["high"] < df["low"])
                    | (df["high"] < df["open"])
                    | (df["high"] < df["close"])
                    | (df["low"] > df["open"])
                    | (df["low"] > df["close"])
                ]

                if not invalid_ohlc.empty:
                    quality_results["status"] = "unhealthy"
                    quality_results["issues"].append(
                        {
                            "type": "invalid_ohlc",
                            "count": len(invalid_ohlc),
                            "samples": invalid_ohlc.head(5).to_dict("records"),
                        }
                    )

                # Check for negative values
                negative_values = df[
                    (df["open"] < 0)
                    | (df["high"] < 0)
                    | (df["low"] < 0)
                    | (df["close"] < 0)
                    | (df["volume"] < 0)
                ]

                if not negative_values.empty:
                    quality_results["status"] = "unhealthy"
                    quality_results["issues"].append(
                        {
                            "type": "negative_values",
                            "count": len(negative_values),
                            "samples": negative_values.head(5).to_dict("records"),
                        }
                    )

                # Check for extreme price changes (>50% in 1 minute)
                for symbol in df["symbol"].unique():
                    symbol_data = df[df["symbol"] == symbol].copy()
                    if len(symbol_data) > 1:
                        symbol_data["price_change"] = symbol_data["close"].pct_change()
                        extreme_changes = symbol_data[
                            symbol_data["price_change"].abs() > 0.5
                        ]

                        if not extreme_changes.empty:
                            quality_results["issues"].append(
                                {
                                    "type": "extreme_price_change",
                                    "symbol": symbol,
                                    "count": len(extreme_changes),
                                }
                            )

                quality_results["details"] = {
                    "records_checked": len(df),
                    "invalid_ohlc": len(invalid_ohlc),
                    "negative_values": len(negative_values),
                }

        except Exception as e:
            logger.error(f"Error checking data quality: {e}")
            quality_results["status"] = "error"
            quality_results["issues"].append({"type": "check_failed", "error": str(e)})

        return quality_results

    def check_pipeline_status(self) -> Dict:
        """Check status of recent pipeline runs"""
        pipeline_results = {"status": "healthy", "issues": [], "details": {}}

        try:
            # Get recent pipeline runs
            since = (datetime.now(tz.UTC) - timedelta(hours=24)).isoformat()

            response = (
                self.supabase.client.table("pipeline_runs")
                .select("*")
                .gte("started_at", since)
                .order("started_at", desc=True)
                .limit(100)
                .execute()
            )

            if response.data:
                df = pd.DataFrame(response.data)

                # Check for failed runs
                failed_runs = df[df["symbols_failed"] > 0]
                if not failed_runs.empty:
                    pipeline_results["issues"].append(
                        {
                            "type": "failed_symbols",
                            "count": len(failed_runs),
                            "total_failed_symbols": failed_runs["symbols_failed"].sum(),
                        }
                    )

                # Check for long-running jobs
                df["started_at"] = pd.to_datetime(df["started_at"])
                df["completed_at"] = pd.to_datetime(df["completed_at"])
                df["duration_minutes"] = (
                    df["completed_at"] - df["started_at"]
                ).dt.total_seconds() / 60

                long_runs = df[df["duration_minutes"] > 30]  # Jobs taking > 30 minutes
                if not long_runs.empty:
                    pipeline_results["issues"].append(
                        {
                            "type": "long_running_jobs",
                            "count": len(long_runs),
                            "max_duration_minutes": long_runs["duration_minutes"].max(),
                        }
                    )

                pipeline_results["details"] = {
                    "total_runs": len(df),
                    "successful_runs": len(df[df["symbols_failed"] == 0]),
                    "failed_runs": len(failed_runs),
                    "avg_duration_minutes": df["duration_minutes"].mean(),
                }

                if pipeline_results["issues"]:
                    pipeline_results["status"] = "unhealthy"

        except Exception as e:
            logger.error(f"Error checking pipeline status: {e}")
            pipeline_results["status"] = "error"
            pipeline_results["issues"].append({"type": "check_failed", "error": str(e)})

        return pipeline_results

    def check_gap_status(self) -> Dict:
        """Check for recent data gaps"""
        gap_results = {"status": "healthy", "issues": [], "details": {}}

        try:
            # Get unhealed gaps from last 24 hours
            since = (datetime.now(tz.UTC) - timedelta(hours=24)).isoformat()

            response = (
                self.supabase.client.table("data_gaps")
                .select("*")
                .eq("healed", False)
                .gte("detected_at", since)
                .execute()
            )

            if response.data:
                df = pd.DataFrame(response.data)

                # Group by timeframe
                for timeframe in ["1m", "15m", "1h", "1d"]:
                    tf_gaps = df[df["timeframe"] == timeframe]
                    if not tf_gaps.empty:
                        # Check if any gaps exceed threshold
                        tf_gaps["duration_td"] = pd.to_timedelta(
                            tf_gaps["duration_minutes"], unit="minutes"
                        )
                        critical_gaps = tf_gaps[
                            tf_gaps["duration_td"]
                            > self.thresholds["max_gap_duration"][timeframe]
                        ]

                        if not critical_gaps.empty:
                            gap_results["status"] = "unhealthy"
                            gap_results["issues"].append(
                                {
                                    "timeframe": timeframe,
                                    "critical_gaps": len(critical_gaps),
                                    "symbols": critical_gaps["symbol"]
                                    .unique()
                                    .tolist(),
                                }
                            )

                gap_results["details"] = {
                    "total_gaps": len(df),
                    "gaps_by_timeframe": df.groupby("timeframe").size().to_dict(),
                }

        except Exception as e:
            logger.error(f"Error checking gap status: {e}")
            gap_results["status"] = "error"
            gap_results["issues"].append({"type": "check_failed", "error": str(e)})

        return gap_results

    def run_all_checks(self) -> Dict:
        """Run all health checks"""
        logger.info("Starting comprehensive health check...")

        results = {
            "timestamp": datetime.now(tz.UTC).isoformat(),
            "overall_status": "healthy",
            "checks": {},
        }

        # Run individual checks
        checks = {
            "data_freshness": self.check_data_freshness(),
            "data_quality": self.check_data_quality(),
            "pipeline_status": self.check_pipeline_status(),
            "gap_status": self.check_gap_status(),
        }

        # Determine overall status
        for check_name, check_result in checks.items():
            results["checks"][check_name] = check_result
            if check_result["status"] != "healthy":
                results["overall_status"] = "unhealthy"

        # Save results
        self.save_health_report(results)

        # Send alerts if needed
        if results["overall_status"] != "healthy":
            self.send_alerts(results)

        return results

    def save_health_report(self, results: Dict):
        """Save health report to file and database"""
        try:
            # Save to file
            report_path = Path("data/health_reports")
            report_path.mkdir(exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = report_path / f"health_report_{timestamp}.json"

            with open(report_file, "w") as f:
                json.dump(results, f, indent=2, default=str)

            logger.info(f"Health report saved to {report_file}")

            # Save to database
            self.supabase.client.table("health_metrics").insert(
                {
                    "timestamp": results["timestamp"],
                    "metric_name": "overall_health",
                    "status": results["overall_status"],
                    "value": 1.0 if results["overall_status"] == "healthy" else 0.0,
                    "details": json.dumps(results),
                }
            ).execute()

        except Exception as e:
            logger.error(f"Error saving health report: {e}")

    def send_alerts(self, results: Dict):
        """Send alerts for critical issues"""
        if not self.slack:
            logger.warning("Slack notifier not configured, skipping alerts")
            return

        try:
            # Build alert message
            message = "🚨 **Data Pipeline Health Alert**\n\n"
            message += f"Overall Status: {results['overall_status']}\n\n"

            for check_name, check_result in results["checks"].items():
                if check_result["status"] != "healthy":
                    message += f"**{check_name.replace('_', ' ').title()}**: {check_result['status']}\n"

                    if check_result.get("issues"):
                        for issue in check_result["issues"][
                            :3
                        ]:  # Limit to first 3 issues
                            if isinstance(issue, dict):
                                if "type" in issue:
                                    message += f"  - {issue['type']}: "
                                    if "count" in issue:
                                        message += f"{issue['count']} occurrences"
                                    message += "\n"

            # Send to Slack
            self.slack.send_alert(message, alert_type="critical")
            logger.info("Health alert sent to Slack")

        except Exception as e:
            logger.error(f"Error sending alerts: {e}")

    def generate_summary_report(self) -> str:
        """Generate a human-readable summary report"""
        results = self.run_all_checks()

        report = []
        report.append("=" * 60)
        report.append("DATA PIPELINE HEALTH REPORT")
        report.append("=" * 60)
        report.append(f"Timestamp: {results['timestamp']}")
        report.append(f"Overall Status: {results['overall_status'].upper()}")
        report.append("")

        for check_name, check_result in results["checks"].items():
            report.append(f"{check_name.replace('_', ' ').title()}:")
            report.append(f"  Status: {check_result['status']}")

            if check_result.get("details"):
                for key, value in check_result["details"].items():
                    report.append(f"  {key}: {value}")

            if check_result.get("issues"):
                report.append("  Issues:")
                for issue in check_result["issues"]:
                    if isinstance(issue, dict) and "type" in issue:
                        report.append(f"    - {issue}")
            report.append("")

        report.append("=" * 60)

        return "\n".join(report)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Data Health Monitor")
    parser.add_argument(
        "--check",
        choices=["freshness", "quality", "pipeline", "gaps", "all"],
        default="all",
        help="Specific check to run",
    )
    parser.add_argument("--alert", action="store_true", help="Send alerts for issues")
    parser.add_argument("--report", action="store_true", help="Generate summary report")

    args = parser.parse_args()

    monitor = DataHealthMonitor()

    if args.report:
        report = monitor.generate_summary_report()
        print(report)
    elif args.check == "all":
        results = monitor.run_all_checks()
        print(json.dumps(results, indent=2, default=str))
    else:
        if args.check == "freshness":
            results = monitor.check_data_freshness()
        elif args.check == "quality":
            results = monitor.check_data_quality()
        elif args.check == "pipeline":
            results = monitor.check_pipeline_status()
        elif args.check == "gaps":
            results = monitor.check_gap_status()

        print(json.dumps(results, indent=2, default=str))

        if args.alert and results["status"] != "healthy":
            monitor.send_alerts({"checks": {args.check: results}})


if __name__ == "__main__":
    main()
