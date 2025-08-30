"""
Risk Manager for Freqtrade
Monitors portfolio risk and can control Freqtrade trading
"""

import os
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import pandas as pd
from loguru import logger
from pathlib import Path


@dataclass
class RiskMetrics:
    """Current risk metrics for the portfolio"""
    total_exposure: float  # Total USD value at risk
    open_positions: int
    daily_pnl: float
    weekly_pnl: float
    max_drawdown: float
    win_rate: float
    sharpe_ratio: float
    current_balance: float
    risk_score: float  # 0-100, higher = more risky


@dataclass
class RiskLimits:
    """Risk limits for the portfolio"""
    max_positions: int = 10
    max_position_size_pct: float = 0.10  # Max 10% per position
    max_total_exposure_pct: float = 0.50  # Max 50% of portfolio
    max_daily_loss_pct: float = 0.05  # Max 5% daily loss
    max_weekly_loss_pct: float = 0.10  # Max 10% weekly loss
    max_drawdown_pct: float = 0.15  # Max 15% drawdown
    min_win_rate: float = 0.40  # Min 40% win rate
    emergency_stop_loss_pct: float = 0.20  # Emergency stop at 20% loss


class RiskManager:
    """Manages portfolio risk for Freqtrade"""
    
    def __init__(self, supabase_client, config_loader, initial_balance: float = 10000):
        """
        Initialize Risk Manager
        
        Args:
            supabase_client: Supabase client for database access
            config_loader: Configuration loader
            initial_balance: Starting portfolio balance
        """
        self.supabase = supabase_client
        self.config = config_loader
        self.initial_balance = initial_balance
        
        # Load risk limits from unified config
        self.risk_limits = self._load_risk_limits()
        
        # Track risk events
        self.risk_events = []
        self.last_check = datetime.now(timezone.utc)
        
        # Freqtrade control flags
        self.trading_enabled = True
        self.emergency_stop = False
        
        # Kill switch state tracking
        self.last_kill_switch_state = None
        self.freqtrade_config_path = self._get_freqtrade_config_path()
        
    def _load_risk_limits(self) -> RiskLimits:
        """Load risk limits from unified config file"""
        try:
            # Get config from the config loader
            config = self.config.load()
            
            # Get risk management settings
            risk_config = config.get('risk_management', {})
            position_config = config.get('position_management', {})
            
            # Map config values to RiskLimits
            return RiskLimits(
                max_positions=position_config.get('max_positions_total', 10),
                max_position_size_pct=position_config.get('position_sizing', {}).get('max_percent_of_balance', 0.10),
                max_total_exposure_pct=position_config.get('position_sizing', {}).get('max_percent_of_balance', 0.50),
                max_daily_loss_pct=risk_config.get('max_daily_loss_pct', 15) / 100.0,  # Convert percentage to decimal
                max_weekly_loss_pct=risk_config.get('max_daily_loss', 0.10),  # Using daily loss * 2 for weekly
                max_drawdown_pct=risk_config.get('max_drawdown', 0.20),
                min_win_rate=0.40,  # Not in config yet, using default
                emergency_stop_loss_pct=risk_config.get('emergency_stop_loss', 0.30)
            )
            
        except Exception as e:
            logger.warning(f"Failed to load risk limits from config: {e}")
            logger.info("Using default risk limits")
            return RiskLimits()  # Return defaults if config load fails
    
    def reload_config(self):
        """Reload risk limits from config (can be called when config changes)"""
        logger.info("Reloading risk limits from config")
        self.risk_limits = self._load_risk_limits()
        logger.info(f"Updated risk limits: {self.risk_limits}")
        
        # Also check kill switch state
        self.check_kill_switch()
        
    def calculate_risk_metrics(self) -> RiskMetrics:
        """Calculate current risk metrics from Freqtrade trades"""
        
        try:
            # Get trades from freqtrade_trades table
            result = self.supabase.client.table("freqtrade_trades")\
                .select("*")\
                .execute()
            
            if not result.data:
                return RiskMetrics(
                    total_exposure=0,
                    open_positions=0,
                    daily_pnl=0,
                    weekly_pnl=0,
                    max_drawdown=0,
                    win_rate=0,
                    sharpe_ratio=0,
                    current_balance=self.initial_balance,
                    risk_score=0
                )
            
            trades_df = pd.DataFrame(result.data)
            
            # Calculate metrics
            open_trades = trades_df[trades_df['is_open'] == True]
            closed_trades = trades_df[trades_df['is_open'] == False]
            
            # Total exposure (sum of open position values)
            total_exposure = 0
            if len(open_trades) > 0:
                for _, trade in open_trades.iterrows():
                    position_value = trade['amount'] * trade['open_rate']
                    total_exposure += position_value
            
            # Open positions count
            open_positions = len(open_trades)
            
            # Calculate P&L
            now = datetime.now(timezone.utc)
            day_ago = now - timedelta(days=1)
            week_ago = now - timedelta(days=7)
            
            # Daily P&L
            daily_trades = closed_trades[
                pd.to_datetime(closed_trades['close_date']) > day_ago
            ] if len(closed_trades) > 0 else pd.DataFrame()
            
            daily_pnl = daily_trades['close_profit_abs'].sum() if len(daily_trades) > 0 else 0
            
            # Weekly P&L
            weekly_trades = closed_trades[
                pd.to_datetime(closed_trades['close_date']) > week_ago
            ] if len(closed_trades) > 0 else pd.DataFrame()
            
            weekly_pnl = weekly_trades['close_profit_abs'].sum() if len(weekly_trades) > 0 else 0
            
            # Win rate
            if len(closed_trades) > 0:
                winning_trades = closed_trades[closed_trades['close_profit'] > 0]
                win_rate = len(winning_trades) / len(closed_trades)
            else:
                win_rate = 0
            
            # Max drawdown (simplified - tracks cumulative P&L)
            if len(closed_trades) > 0:
                closed_trades_sorted = closed_trades.sort_values('close_date')
                closed_trades_sorted['cumulative_pnl'] = closed_trades_sorted['close_profit_abs'].cumsum()
                
                # Calculate drawdown
                running_max = closed_trades_sorted['cumulative_pnl'].expanding().max()
                drawdown = (closed_trades_sorted['cumulative_pnl'] - running_max)
                max_drawdown = abs(drawdown.min()) if len(drawdown) > 0 else 0
            else:
                max_drawdown = 0
            
            # Current balance
            total_pnl = closed_trades['close_profit_abs'].sum() if len(closed_trades) > 0 else 0
            current_balance = self.initial_balance + total_pnl
            
            # Calculate Sharpe ratio (simplified)
            if len(closed_trades) > 20:
                returns = closed_trades['close_profit'].values
                sharpe_ratio = (returns.mean() / returns.std()) * (252 ** 0.5) if returns.std() > 0 else 0
            else:
                sharpe_ratio = 0
            
            # Calculate risk score (0-100)
            risk_score = self._calculate_risk_score(
                total_exposure=total_exposure,
                open_positions=open_positions,
                daily_pnl=daily_pnl,
                weekly_pnl=weekly_pnl,
                max_drawdown=max_drawdown,
                win_rate=win_rate,
                current_balance=current_balance
            )
            
            return RiskMetrics(
                total_exposure=total_exposure,
                open_positions=open_positions,
                daily_pnl=daily_pnl,
                weekly_pnl=weekly_pnl,
                max_drawdown=max_drawdown,
                win_rate=win_rate,
                sharpe_ratio=sharpe_ratio,
                current_balance=current_balance,
                risk_score=risk_score
            )
            
        except Exception as e:
            logger.error(f"Error calculating risk metrics: {e}")
            return RiskMetrics(
                total_exposure=0,
                open_positions=0,
                daily_pnl=0,
                weekly_pnl=0,
                max_drawdown=0,
                win_rate=0,
                sharpe_ratio=0,
                current_balance=self.initial_balance,
                risk_score=0
            )
    
    def _calculate_risk_score(
        self,
        total_exposure: float,
        open_positions: int,
        daily_pnl: float,
        weekly_pnl: float,
        max_drawdown: float,
        win_rate: float,
        current_balance: float
    ) -> float:
        """Calculate overall risk score (0-100)"""
        
        score = 0
        
        # Exposure risk (0-30 points)
        exposure_pct = total_exposure / current_balance if current_balance > 0 else 0
        if exposure_pct > self.risk_limits.max_total_exposure_pct:
            score += 30
        else:
            score += (exposure_pct / self.risk_limits.max_total_exposure_pct) * 20
        
        # Position concentration risk (0-20 points)
        if open_positions > self.risk_limits.max_positions:
            score += 20
        else:
            score += (open_positions / self.risk_limits.max_positions) * 10
        
        # Loss risk (0-30 points)
        daily_loss_pct = abs(daily_pnl / current_balance) if daily_pnl < 0 and current_balance > 0 else 0
        weekly_loss_pct = abs(weekly_pnl / current_balance) if weekly_pnl < 0 and current_balance > 0 else 0
        
        if daily_loss_pct > self.risk_limits.max_daily_loss_pct:
            score += 15
        if weekly_loss_pct > self.risk_limits.max_weekly_loss_pct:
            score += 15
        
        # Drawdown risk (0-20 points)
        drawdown_pct = max_drawdown / self.initial_balance if self.initial_balance > 0 else 0
        if drawdown_pct > self.risk_limits.max_drawdown_pct:
            score += 20
        else:
            score += (drawdown_pct / self.risk_limits.max_drawdown_pct) * 15
        
        return min(score, 100)
    
    def check_risk_limits(self, metrics: RiskMetrics) -> List[Dict]:
        """Check if any risk limits are violated"""
        
        violations = []
        
        # Check position limits
        if metrics.open_positions > self.risk_limits.max_positions:
            violations.append({
                "type": "MAX_POSITIONS",
                "severity": "WARNING",
                "message": f"Too many open positions: {metrics.open_positions}/{self.risk_limits.max_positions}",
                "action": "REDUCE_POSITIONS"
            })
        
        # Check exposure limits
        exposure_pct = metrics.total_exposure / metrics.current_balance if metrics.current_balance > 0 else 0
        if exposure_pct > self.risk_limits.max_total_exposure_pct:
            violations.append({
                "type": "MAX_EXPOSURE",
                "severity": "WARNING",
                "message": f"Exposure too high: {exposure_pct:.1%} of portfolio",
                "action": "REDUCE_EXPOSURE"
            })
        
        # Check daily loss limit
        daily_loss_pct = abs(metrics.daily_pnl / metrics.current_balance) if metrics.daily_pnl < 0 and metrics.current_balance > 0 else 0
        if daily_loss_pct > self.risk_limits.max_daily_loss_pct:
            violations.append({
                "type": "DAILY_LOSS_LIMIT",
                "severity": "HIGH",
                "message": f"Daily loss exceeded: {daily_loss_pct:.1%}",
                "action": "PAUSE_TRADING"
            })
        
        # Check weekly loss limit
        weekly_loss_pct = abs(metrics.weekly_pnl / metrics.current_balance) if metrics.weekly_pnl < 0 and metrics.current_balance > 0 else 0
        if weekly_loss_pct > self.risk_limits.max_weekly_loss_pct:
            violations.append({
                "type": "WEEKLY_LOSS_LIMIT",
                "severity": "HIGH",
                "message": f"Weekly loss exceeded: {weekly_loss_pct:.1%}",
                "action": "PAUSE_TRADING"
            })
        
        # Check drawdown limit
        drawdown_pct = metrics.max_drawdown / self.initial_balance if self.initial_balance > 0 else 0
        if drawdown_pct > self.risk_limits.max_drawdown_pct:
            violations.append({
                "type": "MAX_DRAWDOWN",
                "severity": "CRITICAL",
                "message": f"Max drawdown exceeded: {drawdown_pct:.1%}",
                "action": "STOP_TRADING"
            })
        
        # Check emergency stop
        total_loss_pct = (self.initial_balance - metrics.current_balance) / self.initial_balance if self.initial_balance > 0 else 0
        if total_loss_pct > self.risk_limits.emergency_stop_loss_pct:
            violations.append({
                "type": "EMERGENCY_STOP",
                "severity": "CRITICAL",
                "message": f"Emergency stop triggered: {total_loss_pct:.1%} loss",
                "action": "EMERGENCY_STOP"
            })
        
        # Check win rate (warning only)
        if metrics.win_rate < self.risk_limits.min_win_rate and metrics.win_rate > 0:
            violations.append({
                "type": "LOW_WIN_RATE",
                "severity": "INFO",
                "message": f"Win rate below target: {metrics.win_rate:.1%}",
                "action": "REVIEW_STRATEGY"
            })
        
        return violations
    
    def execute_risk_actions(self, violations: List[Dict]) -> Dict:
        """Execute risk management actions based on violations"""
        
        actions_taken = {
            "trading_enabled": self.trading_enabled,
            "emergency_stop": self.emergency_stop,
            "actions": []
        }
        
        for violation in violations:
            action = violation["action"]
            
            if action == "EMERGENCY_STOP":
                self.emergency_stop = True
                self.trading_enabled = False
                actions_taken["emergency_stop"] = True
                actions_taken["trading_enabled"] = False
                actions_taken["actions"].append("EMERGENCY_STOP: All trading halted")
                logger.critical(f"EMERGENCY STOP: {violation['message']}")
                
            elif action == "STOP_TRADING":
                self.trading_enabled = False
                actions_taken["trading_enabled"] = False
                actions_taken["actions"].append("STOP_TRADING: New trades disabled")
                logger.error(f"Trading stopped: {violation['message']}")
                
            elif action == "PAUSE_TRADING":
                self.trading_enabled = False
                actions_taken["trading_enabled"] = False
                actions_taken["actions"].append("PAUSE_TRADING: Temporary trading pause")
                logger.warning(f"Trading paused: {violation['message']}")
                
            elif action == "REDUCE_POSITIONS":
                actions_taken["actions"].append("REDUCE_POSITIONS: Position size limits enforced")
                logger.warning(f"Position reduction needed: {violation['message']}")
                
            elif action == "REDUCE_EXPOSURE":
                actions_taken["actions"].append("REDUCE_EXPOSURE: Exposure limits enforced")
                logger.warning(f"Exposure reduction needed: {violation['message']}")
                
            elif action == "REVIEW_STRATEGY":
                actions_taken["actions"].append("REVIEW_STRATEGY: Performance review needed")
                logger.info(f"Strategy review: {violation['message']}")
        
        return actions_taken
    
    def log_risk_event(self, event_type: str, details: Dict):
        """Log risk events to database"""
        
        try:
            event = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": event_type,
                "details": details,
                "risk_score": details.get("risk_score", 0),
                "trading_enabled": self.trading_enabled,
                "emergency_stop": self.emergency_stop
            }
            
            # Store in memory (could also log to database)
            self.risk_events.append(event)
            
            # Keep only last 100 events
            if len(self.risk_events) > 100:
                self.risk_events = self.risk_events[-100:]
                
        except Exception as e:
            logger.error(f"Error logging risk event: {e}")
    
    def get_risk_status(self) -> Dict:
        """Get current risk status summary"""
        
        metrics = self.calculate_risk_metrics()
        violations = self.check_risk_limits(metrics)
        
        status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": {
                "total_exposure": metrics.total_exposure,
                "open_positions": metrics.open_positions,
                "daily_pnl": metrics.daily_pnl,
                "weekly_pnl": metrics.weekly_pnl,
                "max_drawdown": metrics.max_drawdown,
                "win_rate": metrics.win_rate,
                "sharpe_ratio": metrics.sharpe_ratio,
                "current_balance": metrics.current_balance,
                "risk_score": metrics.risk_score
            },
            "violations": violations,
            "trading_enabled": self.trading_enabled,
            "emergency_stop": self.emergency_stop,
            "risk_level": self._get_risk_level(metrics.risk_score)
        }
        
        return status
    
    def _get_risk_level(self, risk_score: float) -> str:
        """Convert risk score to risk level"""
        if risk_score < 20:
            return "LOW"
        elif risk_score < 40:
            return "MODERATE"
        elif risk_score < 60:
            return "ELEVATED"
        elif risk_score < 80:
            return "HIGH"
        else:
            return "CRITICAL"
    
    def should_allow_trade(self, symbol: str, position_size: float) -> Tuple[bool, str]:
        """Check if a new trade should be allowed"""
        
        if self.emergency_stop:
            return False, "Emergency stop active"
        
        if not self.trading_enabled:
            return False, "Trading disabled by risk manager"
        
        # Check current metrics
        metrics = self.calculate_risk_metrics()
        
        # Check if adding this trade would violate limits
        if metrics.open_positions >= self.risk_limits.max_positions:
            return False, f"Max positions reached ({self.risk_limits.max_positions})"
        
        # Check exposure
        new_exposure = metrics.total_exposure + position_size
        exposure_pct = new_exposure / metrics.current_balance if metrics.current_balance > 0 else 0
        
        if exposure_pct > self.risk_limits.max_total_exposure_pct:
            return False, f"Would exceed max exposure ({self.risk_limits.max_total_exposure_pct:.0%})"
        
        # Check position size
        position_pct = position_size / metrics.current_balance if metrics.current_balance > 0 else 0
        if position_pct > self.risk_limits.max_position_size_pct:
            return False, f"Position too large ({position_pct:.1%} > {self.risk_limits.max_position_size_pct:.0%})"
        
        return True, "Trade allowed"
    
    def _get_freqtrade_config_path(self) -> Path:
        """Get the path to Freqtrade's config file"""
        # Check if running in Docker/Railway
        if os.path.exists("/freqtrade/config/config.json"):
            return Path("/freqtrade/config/config.json")
        
        # Local development path
        project_root = Path(__file__).parent.parent.parent
        local_path = project_root / "freqtrade" / "config" / "config.json"
        if local_path.exists():
            return local_path
            
        logger.warning("Freqtrade config not found, kill switch will not control Freqtrade")
        return None
    
    def check_kill_switch(self):
        """Check kill switch state and update Freqtrade config if needed"""
        try:
            # Load current unified config
            config = self.config.load()
            
            # Check if trading is enabled
            trading_enabled = config.get('global_settings', {}).get('trading_enabled', True)
            
            # Check if state changed
            if self.last_kill_switch_state is not None and self.last_kill_switch_state != trading_enabled:
                logger.info(f"Kill switch state changed: {'ENABLED' if trading_enabled else 'DISABLED'}")
                self.update_freqtrade_trading(trading_enabled)
                
                # Log the event
                self.log_risk_event(
                    "KILL_SWITCH",
                    {
                        "trading_enabled": trading_enabled,
                        "source": "admin_panel"
                    }
                )
            
            self.last_kill_switch_state = trading_enabled
            
        except Exception as e:
            logger.error(f"Error checking kill switch: {e}")
    
    def update_freqtrade_trading(self, enabled: bool):
        """Update Freqtrade's config to enable/disable trading"""
        
        if not self.freqtrade_config_path or not self.freqtrade_config_path.exists():
            logger.warning("Cannot update Freqtrade config - file not found")
            return False
            
        try:
            # Read current Freqtrade config
            with open(self.freqtrade_config_path, 'r') as f:
                freqtrade_config = json.load(f)
            
            # Update max_open_trades based on kill switch
            if enabled:
                # Enable trading - restore normal max_open_trades
                freqtrade_config['max_open_trades'] = 10  # Or get from unified config
                logger.info("Freqtrade trading ENABLED - max_open_trades set to 10")
            else:
                # Disable trading - set max_open_trades to 0
                freqtrade_config['max_open_trades'] = 0
                logger.info("Freqtrade trading DISABLED - max_open_trades set to 0")
            
            # Write updated config back
            with open(self.freqtrade_config_path, 'w') as f:
                json.dump(freqtrade_config, f, indent=4)
            
            logger.info(f"Freqtrade config updated successfully - trading {'enabled' if enabled else 'disabled'}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating Freqtrade config: {e}")
            return False
    
    def override_trading(self, enabled: bool, reason: str):
        """Override trading state (used by risk violations)"""
        
        # Update internal state
        self.trading_enabled = enabled
        
        # Update Freqtrade config
        success = self.update_freqtrade_trading(enabled)
        
        # Log the event
        self.log_risk_event(
            "TRADING_OVERRIDE",
            {
                "trading_enabled": enabled,
                "reason": reason,
                "success": success
            }
        )
        
        return success
