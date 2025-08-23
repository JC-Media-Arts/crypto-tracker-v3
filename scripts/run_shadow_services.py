#!/usr/bin/env python3
"""
Shadow Testing Services Runner
Orchestrates all shadow testing components for Railway deployment
"""

import sys
import asyncio
import os
from datetime import datetime, time
from typing import Optional, Dict
from loguru import logger
import signal

sys.path.append(".")

from src.data.supabase_client import SupabaseClient
from src.analysis.shadow_evaluator import ShadowEvaluator
from src.analysis.shadow_analyzer import ShadowAnalyzer
from src.trading.threshold_manager import ThresholdManager
from src.ml.shadow_enhanced_retrainer import ShadowEnhancedRetrainer
from src.notifications.slack_notifier import SlackNotifier, NotificationType
from scripts.shadow_slack_reporter import ShadowSlackReporter


class ShadowServicesRunner:
    """Manages all shadow testing services"""

    def __init__(self):
        self.supabase = SupabaseClient()
        self.evaluator = ShadowEvaluator(self.supabase.client)
        self.analyzer = ShadowAnalyzer(self.supabase.client)
        self.threshold_manager = ThresholdManager(self.supabase.client)
        self.retrainer = ShadowEnhancedRetrainer(self.supabase.client)
        self.slack_reporter = ShadowSlackReporter()
        self.slack = SlackNotifier()

        # Service intervals (in seconds)
        self.evaluation_interval = 300  # 5 minutes
        self.analysis_interval = 10800  # 3 hours
        self.adjustment_hour = 2  # 2 AM PST

        # Control flags
        self.running = True
        self.tasks = []

    async def start(self):
        """Start all shadow testing services"""
        logger.info("=" * 60)
        logger.info("SHADOW TESTING SERVICES STARTING")
        logger.info(f"Time: {datetime.now()}")
        logger.info("=" * 60)

        # Send startup notification
        if self.slack.enabled:
            await self.slack.send_notification(
                NotificationType.SYSTEM_ALERT,
                "🔬 Shadow Testing Services Started",
                "All shadow testing components are now running",
                {
                    "Evaluator": "Every 5 minutes",
                    "Analyzer": "Every 3 hours",
                    "Adjustments": "Daily at 2 AM PST",
                    "ML Retraining": "Daily at 2 AM PST",
                },
                "good",
            )

        # Start service tasks
        self.tasks = [
            asyncio.create_task(self.run_evaluator()),
            asyncio.create_task(self.run_analyzer()),
            asyncio.create_task(self.run_daily_tasks()),
            asyncio.create_task(self.monitor_health()),
        ]

        # Wait for all tasks
        try:
            await asyncio.gather(*self.tasks)
        except asyncio.CancelledError:
            logger.info("Services cancelled")
        except Exception as e:
            logger.error(f"Service error: {e}")
            await self.send_error_notification(str(e))

    async def run_evaluator(self):
        """Run shadow evaluator service"""
        logger.info("Starting shadow evaluator service...")

        while self.running:
            try:
                logger.debug("Running shadow evaluation...")
                outcomes = await self.evaluator.evaluate_pending_shadows()

                if outcomes:
                    logger.info(f"Evaluated {len(outcomes)} shadow trades")

                    # Log statistics
                    wins = sum(1 for o in outcomes if o.outcome_status == "WIN")
                    losses = sum(1 for o in outcomes if o.outcome_status == "LOSS")
                    if wins + losses > 0:
                        win_rate = wins / (wins + losses)
                        logger.info(f"Recent win rate: {win_rate:.1%} ({wins}W/{losses}L)")

                await asyncio.sleep(self.evaluation_interval)

            except Exception as e:
                logger.error(f"Evaluator error: {e}")
                await asyncio.sleep(60)  # Wait before retry

    async def run_analyzer(self):
        """Run performance analyzer service"""
        logger.info("Starting performance analyzer service...")

        while self.running:
            try:
                logger.info("Analyzing shadow performance...")

                # Analyze performance
                performance = await self.analyzer.analyze_performance()

                # Generate recommendations
                recommendations = await self.analyzer.generate_recommendations()

                if recommendations:
                    logger.info(f"Generated {len(recommendations)} recommendations:")
                    for rec in recommendations[:3]:
                        logger.info(
                            f"  - {rec.strategy_name}.{rec.parameter_name}: "
                            f"{rec.current_value:.2f} → {rec.recommended_value:.2f} "
                            f"({rec.confidence_level})"
                        )

                await asyncio.sleep(self.analysis_interval)

            except Exception as e:
                logger.error(f"Analyzer error: {e}")
                await asyncio.sleep(300)  # Wait before retry

    async def run_daily_tasks(self):
        """Run daily tasks at specified time"""
        logger.info(f"Daily tasks scheduled for {self.adjustment_hour}:00 AM PST")

        while self.running:
            try:
                # Calculate time until next run
                now = datetime.now()
                target_time = now.replace(hour=self.adjustment_hour, minute=0, second=0, microsecond=0)

                if now >= target_time:
                    # If past today's time, schedule for tomorrow
                    target_time = target_time.replace(day=target_time.day + 1)

                wait_seconds = (target_time - now).total_seconds()
                logger.info(f"Next daily run in {wait_seconds/3600:.1f} hours")

                # Wait until target time
                await asyncio.sleep(wait_seconds)

                if not self.running:
                    break

                logger.info("=" * 60)
                logger.info("RUNNING DAILY TASKS")
                logger.info("=" * 60)

                # 1. Generate and apply recommendations
                await self.apply_threshold_adjustments()

                # 2. Retrain ML models with shadow data
                await self.retrain_models()

                # 3. Send daily summary
                await self.slack_reporter.send_daily_summary()

                logger.info("Daily tasks completed")

            except Exception as e:
                logger.error(f"Daily tasks error: {e}")
                await self.send_error_notification(f"Daily tasks failed: {e}")
                await asyncio.sleep(3600)  # Wait an hour before retry

    async def apply_threshold_adjustments(self):
        """Apply threshold adjustments based on recommendations"""
        logger.info("Checking for threshold adjustments...")

        try:
            # Get recommendations
            recommendations = await self.analyzer.generate_recommendations()

            if not recommendations:
                logger.info("No adjustments recommended")
                return

            # Apply adjustments
            results = await self.threshold_manager.process_recommendations(recommendations)

            # Send notification
            if results:
                await self.slack_reporter.send_adjustment_alert(results)

                successful = [r for r in results if r.success]
                if successful:
                    logger.info(f"Applied {len(successful)} adjustments successfully")

                    # Start monitoring for rollbacks
                    for result in successful:
                        if result.adjustment_id:
                            asyncio.create_task(self.monitor_adjustment(result.adjustment_id))

        except Exception as e:
            logger.error(f"Error applying adjustments: {e}")

    async def retrain_models(self):
        """Retrain ML models with shadow data"""
        logger.info("Starting ML model retraining with shadow data...")

        try:
            results = self.retrainer.retrain_all_strategies()

            # Log results
            models_updated = 0
            for strategy, result in results.items():
                if result.get("action") == "deployed":
                    models_updated += 1
                    logger.info(f"✅ {strategy}: Model updated with {result['improvement']:.1%} improvement")
                elif result["status"] == "success":
                    logger.info(f"❌ {strategy}: No update (insufficient improvement)")
                else:
                    logger.info(f"⏭️ {strategy}: {result.get('reason', 'Skipped')}")

            # Send notification
            if self.slack.enabled:
                await self.slack.send_notification(
                    NotificationType.DAILY_REPORT,
                    "🤖 Shadow-Enhanced ML Retraining Complete",
                    f"{models_updated} model(s) updated with shadow data",
                    {
                        "DCA": self._format_result(results.get("DCA")),
                        "SWING": self._format_result(results.get("SWING")),
                        "CHANNEL": self._format_result(results.get("CHANNEL")),
                    },
                    "good" if models_updated > 0 else "warning",
                )

        except Exception as e:
            logger.error(f"Error retraining models: {e}")

    async def monitor_adjustment(self, adjustment_id: int):
        """Monitor an adjustment for potential rollback"""
        logger.info(f"Monitoring adjustment {adjustment_id} for rollback...")

        try:
            # Monitor for 48 hours
            for hour in range(48):
                await asyncio.sleep(3600)  # Check every hour

                if not self.running:
                    break

                (
                    should_rollback,
                    reason,
                ) = await self.threshold_manager._check_rollback_conditions(adjustment_id)

                if should_rollback:
                    logger.warning(f"Rolling back adjustment {adjustment_id}: {reason}")
                    await self.threshold_manager.rollback_adjustment(adjustment_id, reason)
                    await self.slack_reporter.send_rollback_alert(adjustment_id, reason)
                    break

        except Exception as e:
            logger.error(f"Error monitoring adjustment {adjustment_id}: {e}")

    async def monitor_health(self):
        """Monitor system health"""
        logger.info("Starting health monitor...")

        while self.running:
            try:
                await asyncio.sleep(3600)  # Check every hour

                # Check if services are running
                if not all(not task.done() for task in self.tasks[:-1]):  # Exclude self
                    logger.error("Some services have stopped!")
                    await self.send_error_notification("Shadow services health check failed")

            except Exception as e:
                logger.error(f"Health monitor error: {e}")

    async def send_error_notification(self, error_message: str):
        """Send error notification to Slack"""
        if self.slack.enabled:
            await self.slack.send_notification(
                NotificationType.ERROR,
                "🚨 Shadow Testing Error",
                error_message,
                {
                    "Service": "Shadow Testing",
                    "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Action": "Manual intervention may be required",
                },
                "danger",
            )

    def _format_result(self, result: Optional[Dict]) -> str:
        """Format retraining result for Slack"""
        if not result:
            return "No data"

        if result.get("action") == "deployed":
            return f"✅ Updated ({result.get('improvement', 0):.1%} improvement)"
        elif result.get("status") == "skipped":
            return f"⏭️ {result.get('reason', 'Skipped')}"
        else:
            return "❌ No improvement"

    async def stop(self):
        """Stop all services gracefully"""
        logger.info("Stopping shadow testing services...")
        self.running = False

        # Cancel all tasks
        for task in self.tasks:
            task.cancel()

        # Send shutdown notification
        if self.slack.enabled:
            await self.slack.send_notification(
                NotificationType.SYSTEM_ALERT,
                "🔬 Shadow Testing Services Stopped",
                "Shadow testing services have been shut down",
                {"Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
                "warning",
            )


async def main():
    """Main entry point"""
    runner = ShadowServicesRunner()

    # Handle shutdown signals
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        asyncio.create_task(runner.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await runner.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        await runner.stop()


if __name__ == "__main__":
    # Configure logging
    log_level = os.getenv("LOG_LEVEL", "INFO")
    logger.remove()
    logger.add(sys.stderr, level=log_level)

    # Run services
    asyncio.run(main())
