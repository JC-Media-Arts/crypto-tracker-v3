#!/usr/bin/env python3
"""
Shadow Testing Slack Reporter
Sends daily shadow performance summaries and adjustment alerts to Slack
"""

import sys
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger

sys.path.append(".")

from src.data.supabase_client import SupabaseClient
from src.analysis.shadow_analyzer import ShadowAnalyzer
from src.analysis.shadow_evaluator import ShadowEvaluator
from src.trading.threshold_manager import ThresholdManager
from src.notifications.slack_notifier import SlackNotifier, NotificationType
from src.config.shadow_config import ShadowConfig


class ShadowSlackReporter:
    """Handles Slack reporting for shadow testing system"""

    def __init__(self):
        self.supabase = SupabaseClient()
        self.analyzer = ShadowAnalyzer(self.supabase.client)
        self.evaluator = ShadowEvaluator(self.supabase.client)
        self.threshold_manager = ThresholdManager(self.supabase.client)
        self.slack = SlackNotifier()

    async def send_daily_summary(self):
        """Send comprehensive daily shadow testing summary"""

        if not self.slack.enabled:
            logger.info("Slack notifications disabled")
            return

        logger.info("Generating shadow testing daily summary...")

        try:
            # Get performance data
            performance = await self._get_performance_summary()

            # Get top performers
            top_performers = await self.analyzer.get_top_performers("24h", top_n=3)

            # Get recommendations
            recommendations = await self.analyzer.generate_recommendations()

            # Get recent adjustments
            adjustments = await self._get_recent_adjustments()

            # Build message
            title = "🔬 Shadow Testing Daily Summary"

            # Main message
            if performance["champion_win_rate"] > 0:
                message = (
                    f"Champion Win Rate: {performance['champion_win_rate']:.1%} | "
                    f"Best Challenger: {performance['best_challenger']} "
                    f"({performance['best_win_rate']:.1%})"
                )
            else:
                message = "Gathering shadow testing data..."

            # Build details
            details = {
                "Date": datetime.now().strftime("%Y-%m-%d"),
                "Total Shadow Trades": performance["total_shadows"],
                "Variations Tested": performance["active_variations"],
                "Champion Performance": self._format_champion_stats(performance),
                "Top Performers": self._format_top_performers(top_performers),
                "Recommendations": self._format_recommendations(recommendations),
                "Recent Adjustments": self._format_adjustments(adjustments),
            }

            # Determine color based on performance
            if performance.get("best_outperformance", 0) > 0.05:
                color = "good"
            elif performance.get("best_outperformance", 0) > 0:
                color = "warning"
            else:
                color = "#3AA3E3"  # Slack blue

            # Send notification
            await self.slack.send_notification(
                NotificationType.SHADOW_PERFORMANCE, title, message, details, color
            )

            logger.info("Shadow testing summary sent to Slack")

        except Exception as e:
            logger.error(f"Error sending shadow summary: {e}")

    async def send_adjustment_alert(self, adjustment_results: List):
        """Send alert when thresholds are adjusted"""

        if not self.slack.enabled or not adjustment_results:
            return

        try:
            successful = [r for r in adjustment_results if r.success]
            failed = [r for r in adjustment_results if not r.success]

            if successful:
                title = "⚙️ Threshold Adjustments Applied"
                message = f"✅ {len(successful)} parameter(s) adjusted successfully"

                details = {}
                for result in successful:
                    param_detail = (
                        f"{result.old_value:.3f} → {result.new_value:.3f} "
                        f"({(result.new_value - result.old_value) / result.old_value:+.1%})"
                    )
                    details[result.parameter_name] = param_detail

                if failed:
                    details["Failed"] = f"{len(failed)} adjustments failed"

                await self.slack.send_notification(
                    NotificationType.THRESHOLD_ADJUSTMENT,
                    title,
                    message,
                    details,
                    "good",
                )

            if failed and not successful:
                title = "⚠️ Threshold Adjustments Failed"
                message = f"❌ All {len(failed)} adjustments failed"

                details = {}
                for result in failed:
                    details[result.parameter_name] = result.reason

                await self.slack.send_notification(
                    NotificationType.THRESHOLD_ADJUSTMENT,
                    title,
                    message,
                    details,
                    "danger",
                )

        except Exception as e:
            logger.error(f"Error sending adjustment alert: {e}")

    async def send_rollback_alert(self, adjustment_id: int, reason: str):
        """Send alert when an adjustment is rolled back"""

        if not self.slack.enabled:
            return

        try:
            # Get adjustment details
            result = (
                self.supabase.client.table("threshold_adjustments")
                .select("*")
                .eq("adjustment_id", adjustment_id)
                .single()
                .execute()
            )

            if result.data:
                adj = result.data

                title = "🔄 Threshold Rollback Triggered"
                message = f"⚠️ {adj['parameter_name']} rolled back due to: {reason}"

                details = {
                    "Strategy": adj["strategy_name"],
                    "Parameter": adj["parameter_name"],
                    "Reverted": f"{adj['new_value']} → {adj['old_value']}",
                    "Original Change": f"{adj['old_value']} → {adj['new_value']}",
                    "Time Active": self._calculate_time_active(adj["adjusted_at"]),
                    "Rollback Reason": reason,
                }

                await self.slack.send_notification(
                    NotificationType.ROLLBACK_ALERT, title, message, details, "danger"
                )

        except Exception as e:
            logger.error(f"Error sending rollback alert: {e}")

    async def send_champion_challenger_update(self):
        """Send update when a challenger becomes the new champion"""

        if not self.slack.enabled:
            return

        try:
            # Check for champion changes in last hour
            cutoff = (datetime.utcnow() - timedelta(hours=1)).isoformat()

            result = (
                self.supabase.client.table("threshold_adjustments")
                .select("*")
                .gte("adjusted_at", cutoff)
                .eq("variation_source", "CHAMPION_UPDATE")
                .execute()
            )

            if result.data:
                for change in result.data:
                    title = "👑 New Champion Variation"
                    message = f"🎯 {change['variation_source']} is now the champion for {change['strategy_name']}"

                    details = {
                        "Strategy": change["strategy_name"],
                        "Previous Champion": "CHAMPION",
                        "New Champion": change["variation_source"],
                        "Improvement": f"{change['outperformance_percentage']:.1f}%",
                        "Evidence": f"{change['evidence_trades']} trades",
                        "Confidence": change["adjustment_confidence"],
                    }

                    await self.slack.send_notification(
                        NotificationType.SHADOW_PERFORMANCE,
                        title,
                        message,
                        details,
                        "good",
                    )

        except Exception as e:
            logger.error(f"Error sending champion update: {e}")

    async def _get_performance_summary(self) -> Dict:
        """Get overall performance summary"""
        try:
            # Get champion performance
            champion_result = (
                self.supabase.client.table("shadow_performance")
                .select("*")
                .eq("variation_name", "CHAMPION")
                .eq("strategy_name", "OVERALL")
                .eq("timeframe", "24h")
                .single()
                .execute()
            )

            # Get best challenger
            challenger_result = (
                self.supabase.client.table("shadow_performance")
                .select("*")
                .eq("strategy_name", "OVERALL")
                .eq("timeframe", "24h")
                .neq("variation_name", "CHAMPION")
                .order("outperformance_vs_champion", desc=True)
                .limit(1)
                .execute()
            )

            # Count total shadows
            shadow_count = (
                self.supabase.client.table("shadow_outcomes")
                .select("outcome_id", count="exact")
                .gte(
                    "evaluated_at",
                    (datetime.utcnow() - timedelta(hours=24)).isoformat(),
                )
                .execute()
            )

            summary = {
                "champion_win_rate": 0,
                "best_challenger": "None",
                "best_win_rate": 0,
                "best_outperformance": 0,
                "total_shadows": shadow_count.count
                if hasattr(shadow_count, "count")
                else 0,
                "active_variations": len(ShadowConfig.get_active_variations()),
            }

            if champion_result.data:
                summary["champion_win_rate"] = champion_result.data["win_rate"]
                summary["champion_trades"] = champion_result.data["trades_completed"]
                summary["champion_pnl"] = champion_result.data["avg_pnl_percentage"]

            if challenger_result.data and len(challenger_result.data) > 0:
                best = challenger_result.data[0]
                summary["best_challenger"] = best["variation_name"]
                summary["best_win_rate"] = best["win_rate"]
                summary["best_outperformance"] = best["outperformance_vs_champion"]

            return summary

        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            return {
                "champion_win_rate": 0,
                "best_challenger": "Error",
                "best_win_rate": 0,
                "best_outperformance": 0,
                "total_shadows": 0,
                "active_variations": 0,
            }

    async def _get_recent_adjustments(self) -> List[Dict]:
        """Get adjustments made in last 24 hours"""
        try:
            cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()

            result = (
                self.supabase.client.table("threshold_adjustments")
                .select("*")
                .gte("adjusted_at", cutoff)
                .order("adjusted_at", desc=True)
                .limit(5)
                .execute()
            )

            return result.data if result.data else []

        except Exception as e:
            logger.error(f"Error getting recent adjustments: {e}")
            return []

    def _format_champion_stats(self, performance: Dict) -> str:
        """Format champion statistics for Slack"""
        if performance.get("champion_trades", 0) > 0:
            return (
                f"Win Rate: {performance['champion_win_rate']:.1%} | "
                f"Avg P&L: {performance.get('champion_pnl', 0):.2f}% | "
                f"Trades: {performance.get('champion_trades', 0)}"
            )
        return "No champion data available"

    def _format_top_performers(self, performers: List) -> str:
        """Format top performers for Slack"""
        if not performers:
            return "No challengers outperforming champion"

        lines = []
        for i, perf in enumerate(performers[:3], 1):
            emoji = ["🥇", "🥈", "🥉"][i - 1]
            lines.append(
                f"{emoji} {perf.variation_name}: "
                f"{perf.win_rate:.1%} win rate "
                f"({perf.outperformance_vs_champion:+.1%} vs champion)"
            )

        return "\n".join(lines)

    def _format_recommendations(self, recommendations: List) -> str:
        """Format recommendations for Slack"""
        if not recommendations:
            return "No adjustments recommended at this time"

        lines = []
        for rec in recommendations[:3]:
            conf_emoji = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "⚪"}.get(
                rec.confidence_level, "⚪"
            )

            lines.append(
                f"{conf_emoji} {rec.strategy_name}.{rec.parameter_name}: "
                f"{rec.current_value:.2f} → {rec.recommended_value:.2f}"
            )

        return "\n".join(lines)

    def _format_adjustments(self, adjustments: List[Dict]) -> str:
        """Format recent adjustments for Slack"""
        if not adjustments:
            return "No adjustments in last 24 hours"

        lines = []
        for adj in adjustments[:3]:
            if adj.get("rollback_triggered"):
                status = "🔄 Rolled back"
            else:
                status = "✅ Active"

            lines.append(
                f"{status} {adj['strategy_name']}.{adj['parameter_name']}: "
                f"{adj['old_value']:.2f} → {adj['new_value']:.2f}"
            )

        return "\n".join(lines)

    def _calculate_time_active(self, adjusted_at: str) -> str:
        """Calculate how long an adjustment was active"""
        try:
            adj_time = datetime.fromisoformat(adjusted_at.replace("Z", "+00:00"))
            duration = datetime.utcnow() - adj_time.replace(tzinfo=None)

            hours = duration.total_seconds() / 3600
            if hours < 1:
                return f"{int(duration.total_seconds() / 60)} minutes"
            elif hours < 24:
                return f"{hours:.1f} hours"
            else:
                return f"{hours / 24:.1f} days"

        except Exception:
            return "Unknown"


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Shadow Testing Slack Reporter")
    parser.add_argument("--summary", action="store_true", help="Send daily summary")
    parser.add_argument("--test", action="store_true", help="Send test notification")

    args = parser.parse_args()

    reporter = ShadowSlackReporter()

    if args.test:
        # Send test notification
        await reporter.slack.send_notification(
            NotificationType.SHADOW_PERFORMANCE,
            "🔬 Shadow Testing System Active",
            "Test notification - Shadow testing is configured and running",
            {
                "Status": "Operational",
                "Variations": ", ".join(ShadowConfig.get_active_variations()),
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            "good",
        )
        print("Test notification sent")
    else:
        # Send daily summary
        await reporter.send_daily_summary()
        print("Daily summary sent")


if __name__ == "__main__":
    asyncio.run(main())
