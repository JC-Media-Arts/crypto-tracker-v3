#!/usr/bin/env python3
"""
Risk Manager Service for Freqtrade
Monitors portfolio risk and controls trading based on risk limits
"""

import sys
import asyncio
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from loguru import logger
import signal

sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from src.config.config_loader import ConfigLoader
from src.trading.risk_manager import RiskManager
from src.notifications.slack_notifier import SlackNotifier, NotificationType


class RiskManagerService:
    """Risk management service for Freqtrade"""
    
    def __init__(self):
        self.supabase = SupabaseClient()
        self.config = ConfigLoader()
        self.risk_manager = RiskManager(
            self.supabase,
            self.config,
            initial_balance=10000  # TODO: Get from config
        )
        self.slack = SlackNotifier()
        
        # Service settings
        self.check_interval = 60  # Check risk every minute
        self.report_interval = 3600  # Report every hour
        self.config_reload_interval = 300  # Reload config every 5 minutes
        self.running = True
        
        # Track state
        self.last_report = datetime.now(timezone.utc)
        self.last_config_reload = datetime.now(timezone.utc)
        self.consecutive_violations = 0
        self.last_violations = []
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
    
    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info("Shutdown signal received, stopping risk manager...")
        self.running = False
    
    async def monitor_risk(self):
        """Main risk monitoring loop"""
        logger.info("Starting risk monitoring...")
        
        while self.running:
            try:
                # Reload config periodically to pick up admin panel changes
                now = datetime.now(timezone.utc)
                if (now - self.last_config_reload).total_seconds() >= self.config_reload_interval:
                    logger.info("Reloading configuration from unified config...")
                    self.config.reload()  # Reload the config loader
                    self.risk_manager.reload_config()  # Reload risk limits
                    self.last_config_reload = now
                
                # Calculate current risk metrics
                metrics = self.risk_manager.calculate_risk_metrics()
                
                # Check for violations
                violations = self.risk_manager.check_risk_limits(metrics)
                
                # Log current status
                logger.info(
                    f"Risk check - Score: {metrics.risk_score:.0f}, "
                    f"Positions: {metrics.open_positions}, "
                    f"Daily P&L: ${metrics.daily_pnl:.2f}, "
                    f"Balance: ${metrics.current_balance:.2f}"
                )
                
                # Handle violations
                if violations:
                    await self.handle_violations(violations, metrics)
                else:
                    # Reset violation counter if no violations
                    if self.consecutive_violations > 0:
                        self.consecutive_violations = 0
                        logger.info("Risk levels returned to normal")
                        
                        # Re-enable trading if it was paused
                        if not self.risk_manager.trading_enabled and not self.risk_manager.emergency_stop:
                            self.risk_manager.trading_enabled = True
                            logger.info("Trading re-enabled")
                            await self.send_notification(
                                "✅ Trading Resumed",
                                "Risk levels have returned to normal. Trading has been re-enabled.",
                                {"Risk Score": metrics.risk_score},
                                "good"
                            )
                
                # Store last violations for comparison
                self.last_violations = violations
                
                # Log risk event
                self.risk_manager.log_risk_event(
                    "RISK_CHECK",
                    {
                        "risk_score": metrics.risk_score,
                        "violations": len(violations),
                        "trading_enabled": self.risk_manager.trading_enabled
                    }
                )
                
            except Exception as e:
                logger.error(f"Error in risk monitoring: {e}")
            
            # Wait before next check
            await asyncio.sleep(self.check_interval)
    
    async def handle_violations(self, violations: list, metrics):
        """Handle risk violations"""
        
        self.consecutive_violations += 1
        
        # Execute risk actions
        actions = self.risk_manager.execute_risk_actions(violations)
        
        # Log violations
        for violation in violations:
            logger.warning(
                f"Risk violation: {violation['type']} - {violation['message']}"
            )
        
        # Send notifications for critical violations
        critical_violations = [v for v in violations if v['severity'] in ['HIGH', 'CRITICAL']]
        
        if critical_violations:
            await self.send_critical_alert(critical_violations, metrics, actions)
        
        # Update Freqtrade control file if trading is disabled
        if not self.risk_manager.trading_enabled:
            await self.update_freqtrade_control(enabled=False)
    
    async def send_critical_alert(self, violations, metrics, actions):
        """Send critical risk alerts"""
        
        title = "🚨 Risk Alert - Action Required"
        
        if self.risk_manager.emergency_stop:
            title = "🛑 EMERGENCY STOP ACTIVATED"
            color = "danger"
        elif not self.risk_manager.trading_enabled:
            title = "⚠️ Trading Paused - Risk Limits Exceeded"
            color = "warning"
        else:
            color = "warning"
        
        # Build message
        violation_msgs = [f"• {v['message']}" for v in violations]
        message = "\n".join(violation_msgs)
        
        # Build details
        details = {
            "Risk Score": f"{metrics.risk_score:.0f}/100",
            "Open Positions": metrics.open_positions,
            "Daily P&L": f"${metrics.daily_pnl:.2f}",
            "Weekly P&L": f"${metrics.weekly_pnl:.2f}",
            "Current Balance": f"${metrics.current_balance:.2f}",
            "Actions Taken": ", ".join(actions['actions']) if actions['actions'] else "None"
        }
        
        await self.send_notification(title, message, details, color)
    
    async def send_notification(self, title, message, details, color="info"):
        """Send Slack notification"""
        
        if self.slack.enabled:
            try:
                await self.slack.send_notification(
                    NotificationType.RISK_ALERT,
                    title,
                    message,
                    details,
                    color
                )
            except Exception as e:
                logger.error(f"Error sending notification: {e}")
    
    async def update_freqtrade_control(self, enabled: bool):
        """Update Freqtrade control status"""
        
        try:
            # Store control status in database
            control_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trading_enabled": enabled,
                "reason": "Risk Manager Control",
                "emergency_stop": self.risk_manager.emergency_stop
            }
            
            # Could write to a control table or file that Freqtrade checks
            logger.info(f"Freqtrade trading {'enabled' if enabled else 'disabled'}")
            
            # Log to risk events
            self.risk_manager.log_risk_event(
                "TRADING_CONTROL",
                control_data
            )
            
        except Exception as e:
            logger.error(f"Error updating Freqtrade control: {e}")
    
    async def generate_risk_report(self):
        """Generate periodic risk reports"""
        
        while self.running:
            try:
                # Wait for report interval
                await asyncio.sleep(self.report_interval)
                
                # Get current status
                status = self.risk_manager.get_risk_status()
                
                # Build report
                title = "📊 Risk Management Report"
                
                risk_level = status['risk_level']
                if risk_level == "LOW":
                    emoji = "🟢"
                elif risk_level == "MODERATE":
                    emoji = "🟡"
                elif risk_level in ["ELEVATED", "HIGH"]:
                    emoji = "🟠"
                else:
                    emoji = "🔴"
                
                message = f"{emoji} Risk Level: {risk_level} (Score: {status['metrics']['risk_score']:.0f}/100)"
                
                details = {
                    "Open Positions": status['metrics']['open_positions'],
                    "Total Exposure": f"${status['metrics']['total_exposure']:.2f}",
                    "Daily P&L": f"${status['metrics']['daily_pnl']:.2f}",
                    "Weekly P&L": f"${status['metrics']['weekly_pnl']:.2f}",
                    "Win Rate": f"{status['metrics']['win_rate']:.1%}",
                    "Current Balance": f"${status['metrics']['current_balance']:.2f}",
                    "Trading Status": "Enabled" if status['trading_enabled'] else "Disabled",
                    "Active Violations": len(status['violations'])
                }
                
                # Determine color based on risk level
                if risk_level in ["LOW", "MODERATE"]:
                    color = "good"
                elif risk_level == "ELEVATED":
                    color = "warning"
                else:
                    color = "danger"
                
                await self.send_notification(title, message, details, color)
                
                logger.info(f"Risk report sent - Level: {risk_level}, Score: {status['metrics']['risk_score']:.0f}")
                
            except Exception as e:
                logger.error(f"Error generating risk report: {e}")
    
    async def run(self):
        """Run all risk management services"""
        
        logger.info("="*60)
        logger.info("RISK MANAGER SERVICE STARTING")
        logger.info("="*60)
        logger.info(f"Check interval: {self.check_interval} seconds")
        logger.info(f"Report interval: {self.report_interval} seconds")
        logger.info(f"Initial balance: ${self.risk_manager.initial_balance:.2f}")
        logger.info("="*60)
        
        # Send startup notification
        await self.send_notification(
            "🛡️ Risk Manager Started",
            "Risk management service is now monitoring portfolio risk.",
            {
                "Check Interval": f"{self.check_interval}s",
                "Report Interval": f"{self.report_interval/3600:.1f}h",
                "Initial Balance": f"${self.risk_manager.initial_balance:.2f}"
            },
            "good"
        )
        
        # Create tasks
        tasks = [
            asyncio.create_task(self.monitor_risk()),
            asyncio.create_task(self.generate_risk_report())
        ]
        
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("Shutting down risk manager...")
            self.running = False
        except Exception as e:
            logger.error(f"Risk manager error: {e}")
            await self.send_notification(
                "❌ Risk Manager Error",
                f"Risk manager encountered an error: {str(e)}",
                {},
                "danger"
            )


async def main():
    """Main entry point"""
    service = RiskManagerService()
    await service.run()


if __name__ == "__main__":
    asyncio.run(main())
