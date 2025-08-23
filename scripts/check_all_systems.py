#!/usr/bin/env python3
"""
Comprehensive System Status Checker
Checks status of all trading system components
"""

import psutil
import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from colorama import Fore, Style, init
import subprocess
import json
from typing import Dict, List, Optional, Any

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from src.config.settings import get_settings
from loguru import logger

init(autoreset=True)


class SystemStatusChecker:
    """Check status of all trading system components"""

    def __init__(self):
        """Initialize the checker with Supabase client"""
        try:
            self.supabase = SupabaseClient()
            self.settings = get_settings()
            self.results = {}
            logger.info("System status checker initialized")
        except Exception as e:
            print(f"{Fore.RED}Failed to initialize: {e}")
            sys.exit(1)

    def run_complete_check(self):
        """Run comprehensive system check (synchronous)"""
        print(f"{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}COMPLETE SYSTEM STATUS CHECK")
        print(f"{Fore.CYAN}Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"{Fore.CYAN}{'='*60}\n")

        # Check all major components
        self.check_paper_trading()
        self.check_ml_engine()
        self.check_shadow_testing()
        self.check_data_pipeline()
        self.check_strategy_engines()
        self.check_risk_management()
        self.check_railway_services()
        self.check_database_activity()

        # Generate summary
        self.print_summary()

    def check_paper_trading(self):
        """Check if paper trading is running"""
        print(f"\n{Fore.YELLOW}1. PAPER TRADING ENGINE")
        print("-" * 40)

        checks = {}

        # Check if process is running
        paper_trading_running = self.check_process("run_paper_trading")
        checks["Process Running"] = paper_trading_running

        # Check recent trades in database
        recent_trades = self.check_recent_table_activity("trade_logs", "created_at", 60)
        checks["Recent Trades (last hour)"] = f"{recent_trades} trades"

        # Check open positions
        try:
            result = self.supabase.client.table("trade_logs").select("*", count="exact").eq("status", "OPEN").execute()

            open_positions = result.count if result else 0
            checks["Open Positions"] = open_positions
        except Exception as e:
            checks["Open Positions"] = f"Error: {str(e)[:50]}"

        # Check last trade time
        try:
            result = (
                self.supabase.client.table("trade_logs")
                .select("created_at")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

            if result.data and len(result.data) > 0:
                last_trade_str = result.data[0]["created_at"]
                last_trade = datetime.fromisoformat(last_trade_str.replace("Z", "+00:00"))
                time_since = datetime.now(timezone.utc) - last_trade
                hours_ago = time_since.total_seconds() / 3600
                checks["Last Trade"] = f"{hours_ago:.1f} hours ago"
                checks["Trade Freshness"] = hours_ago < 24
            else:
                checks["Last Trade"] = "No trades found"
                checks["Trade Freshness"] = False
        except Exception as e:
            checks["Last Trade"] = f"Error: {str(e)[:50]}"

        self.print_component_status("Paper Trading", checks)
        self.results["Paper Trading"] = checks

    def check_ml_engine(self):
        """Check if ML engine is running"""
        print(f"\n{Fore.YELLOW}2. ML ENGINE")
        print("-" * 40)

        checks = {}

        # Check ML predictor process
        ml_running = self.check_process("predictor") or self.check_process("feature_calculator")
        checks["ML Process"] = ml_running

        # Check recent ML features
        recent_features = self.check_recent_table_activity("ml_features", "timestamp", 30)
        checks["Recent Features (30 min)"] = f"{recent_features} records"

        # Check model files exist
        model_files = [
            "models/dca/xgboost_multi_output.pkl",
            "models/swing/swing_classifier.pkl",
            "models/channel/classifier.pkl",
        ]
        models_exist = sum(1 for f in model_files if os.path.exists(f))
        checks["Models Available"] = f"{models_exist}/{len(model_files)}"

        # Check feature calculation freshness
        try:
            result = (
                self.supabase.client.table("ml_features")
                .select("timestamp")
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )

            if result.data and len(result.data) > 0:
                last_feature_str = result.data[0]["timestamp"]
                last_feature = datetime.fromisoformat(last_feature_str.replace("Z", "+00:00"))
                time_since = datetime.now(timezone.utc) - last_feature
                minutes_ago = time_since.total_seconds() / 60
                checks["Feature Freshness"] = f"{minutes_ago:.1f} min ago"
            else:
                checks["Feature Freshness"] = "No features found"
        except Exception as e:
            checks["Feature Freshness"] = f"Error: {str(e)[:50]}"

        self.print_component_status("ML Engine", checks)
        self.results["ML Engine"] = checks

    def check_shadow_testing(self):
        """Check if shadow testing is running"""
        print(f"\n{Fore.YELLOW}3. SHADOW TESTING SYSTEM")
        print("-" * 40)

        checks = {}

        # Check shadow testing tables
        shadow_tables = [
            ("shadow_testing_scans", "created_at"),
            ("shadow_testing_trades", "created_at"),
            ("shadow_variations", "created_at"),
            ("shadow_outcomes", "created_at"),
        ]

        for table, time_col in shadow_tables:
            try:
                # Check if table exists and has recent activity
                result = self.supabase.client.table(table).select("*", count="exact").execute()

                if result:
                    total_records = result.count if result.count else 0
                    recent = self.check_recent_table_activity(table, time_col, 60)
                    checks[f"{table}"] = f"{recent} recent / {total_records} total"
                else:
                    checks[f"{table}"] = "No data"
            except Exception as e:
                if "relation" in str(e) and "does not exist" in str(e):
                    checks[f"{table}"] = "Table not found"
                else:
                    checks[f"{table}"] = f"Error: {str(e)[:30]}"

        # Check shadow evaluator process
        shadow_running = self.check_process("shadow") and self.check_process("evaluator")
        checks["Shadow Evaluator Process"] = shadow_running

        self.print_component_status("Shadow Testing", checks)
        self.results["Shadow Testing"] = checks

    def check_data_pipeline(self):
        """Check data collection pipeline"""
        print(f"\n{Fore.YELLOW}4. DATA PIPELINE")
        print("-" * 40)

        checks = {}

        # Check WebSocket/Data collector process
        ws_running = (
            self.check_process("websocket")
            or self.check_process("data_collector")
            or self.check_process("singleton_websocket")
        )
        checks["WebSocket/Collector Active"] = ws_running

        # Check data freshness in ohlc_data
        try:
            result = (
                self.supabase.client.table("ohlc_data")
                .select("timestamp")
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )

            if result.data and len(result.data) > 0:
                last_data_str = result.data[0]["timestamp"]
                last_data = datetime.fromisoformat(last_data_str.replace("Z", "+00:00"))
                time_since = datetime.now(timezone.utc) - last_data
                minutes_ago = time_since.total_seconds() / 60
                checks["Data Freshness"] = f"{minutes_ago:.1f} min ago"
                checks["Data Fresh (<5min)"] = minutes_ago < 5
            else:
                checks["Data Freshness"] = "No data"
                checks["Data Fresh (<5min)"] = False
        except Exception as e:
            checks["Data Freshness"] = f"Error: {str(e)[:50]}"

        # Check symbol coverage (last hour)
        try:
            one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
            result = self.supabase.client.table("ohlc_data").select("symbol").gte("timestamp", one_hour_ago).execute()

            if result.data:
                unique_symbols = len(set(row["symbol"] for row in result.data))
                checks["Active Symbols (1hr)"] = f"{unique_symbols}/90"
            else:
                checks["Active Symbols (1hr)"] = "0/90"
        except Exception as e:
            checks["Active Symbols (1hr)"] = f"Error: {str(e)[:50]}"

        # Check total OHLC records
        try:
            result = self.supabase.client.table("ohlc_data").select("*", count="exact").execute()

            if result:
                total_records = result.count if result.count else 0
                checks["Total OHLC Records"] = f"{total_records:,}"
        except Exception as e:
            checks["Total OHLC Records"] = f"Error: {str(e)[:50]}"

        self.print_component_status("Data Pipeline", checks)
        self.results["Data Pipeline"] = checks

    def check_strategy_engines(self):
        """Check all strategy engines"""
        print(f"\n{Fore.YELLOW}5. STRATEGY ENGINES")
        print("-" * 40)

        checks = {}

        strategies = ["DCA", "SWING", "CHANNEL"]

        for strategy in strategies:
            # Check recent scans in scan_history
            try:
                one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
                result = (
                    self.supabase.client.table("scan_history")
                    .select("*", count="exact")
                    .eq("strategy_name", strategy)
                    .gte("timestamp", one_hour_ago)
                    .execute()
                )

                scan_count = result.count if result and result.count else 0
                checks[f"{strategy} Scans (1hr)"] = scan_count
            except Exception as e:
                checks[f"{strategy} Scans (1hr)"] = f"Error: {str(e)[:30]}"

            # Check for strategy-specific tables
            strategy_table = f"{strategy.lower()}_strategy_setups"
            try:
                # Try to get recent setups from strategy-specific table
                result = self.supabase.client.table(strategy_table).select("*", count="exact").execute()

                if result:
                    setup_count = result.count if result.count else 0
                    checks[f"{strategy} Setups"] = setup_count
            except Exception as e:
                if "relation" in str(e) and "does not exist" in str(e):
                    # Table doesn't exist, check scan_history for signals instead
                    try:
                        twenty_four_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
                        result = (
                            self.supabase.client.table("scan_history")
                            .select("*", count="exact")
                            .eq("strategy_name", strategy)
                            .eq("signal_strength", "strong")
                            .gte("timestamp", twenty_four_hours_ago)
                            .execute()
                        )

                        signal_count = result.count if result and result.count else 0
                        checks[f"{strategy} Signals (24hr)"] = signal_count
                    except:
                        checks[f"{strategy} Signals"] = "N/A"
                else:
                    checks[f"{strategy} Setups"] = "Error"

        # Check strategy manager process
        manager_running = self.check_process("strategy_manager") or self.check_process("signal_generator")
        checks["Strategy Manager Process"] = manager_running

        self.print_component_status("Strategy Engines", checks)
        self.results["Strategy Engines"] = checks

    def check_risk_management(self):
        """Check risk management systems"""
        print(f"\n{Fore.YELLOW}6. RISK MANAGEMENT")
        print("-" * 40)

        checks = {}

        # Check open positions count
        try:
            result = self.supabase.client.table("trade_logs").select("*", count="exact").eq("status", "OPEN").execute()

            open_positions = result.count if result and result.count else 0
            max_positions = 5  # Your configured max
            checks["Position Limit"] = f"{open_positions}/{max_positions}"
            checks["Position Limit OK"] = open_positions <= max_positions
        except Exception as e:
            checks["Position Limit"] = f"Error: {str(e)[:50]}"

        # Check daily P&L
        try:
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            result = self.supabase.client.table("trade_logs").select("pnl").gte("created_at", today_start).execute()

            if result.data:
                daily_pnl = sum(float(trade.get("pnl", 0)) for trade in result.data if trade.get("pnl"))
                checks["Daily P&L"] = f"${daily_pnl:.2f}"
                checks["Daily Loss Limit OK"] = daily_pnl > -100  # Assuming $100 daily loss limit
            else:
                checks["Daily P&L"] = "$0.00"
                checks["Daily Loss Limit OK"] = True
        except Exception as e:
            checks["Daily P&L"] = f"Error: {str(e)[:50]}"

        # Check if stop losses are set on open positions
        try:
            result = self.supabase.client.table("trade_logs").select("stop_loss_price").eq("status", "OPEN").execute()

            if result.data and len(result.data) > 0:
                stops_set = sum(1 for trade in result.data if trade.get("stop_loss_price"))
                total_open = len(result.data)
                checks["Stop Losses Set"] = f"{stops_set}/{total_open}"
            else:
                checks["Stop Losses Set"] = "No open positions"
        except Exception as e:
            checks["Stop Losses Set"] = f"Error: {str(e)[:50]}"

        self.print_component_status("Risk Management", checks)
        self.results["Risk Management"] = checks

    def check_railway_services(self):
        """Check Railway deployment status"""
        print(f"\n{Fore.YELLOW}7. RAILWAY SERVICES")
        print("-" * 40)

        checks = {}

        # Check if railway CLI is available
        try:
            result = subprocess.run(["railway", "status"], capture_output=True, text=True, timeout=5)
            railway_available = result.returncode == 0

            if railway_available:
                checks["Railway CLI"] = "Available"
                # Parse railway status output if needed
                if "Connected" in result.stdout:
                    checks["Railway Connection"] = "Connected"
                else:
                    checks["Railway Connection"] = "Not connected"
            else:
                checks["Railway CLI"] = "Not available"
        except FileNotFoundError:
            checks["Railway CLI"] = "Not installed"
        except subprocess.TimeoutExpired:
            checks["Railway CLI"] = "Timeout"
        except Exception as e:
            checks["Railway CLI"] = f"Error: {str(e)[:30]}"

        # List expected Railway services
        services = [
            "Data Collector",
            "Feature Calculator",
            "ML Trainer",
            "Data Scheduler",
            "ML Retrainer Cron",
        ]

        checks["Expected Services"] = ", ".join(services)
        checks["Service Status"] = "Check Railway Dashboard"

        self.print_component_status("Railway Services", checks)
        self.results["Railway Services"] = checks

    def check_database_activity(self):
        """Check database health and activity"""
        print(f"\n{Fore.YELLOW}8. DATABASE HEALTH")
        print("-" * 40)

        checks = {}

        # Check table sizes
        tables = ["ohlc_data", "ml_features", "trade_logs", "scan_history"]
        for table in tables:
            try:
                result = self.supabase.client.table(table).select("*", count="exact").execute()

                if result:
                    count = result.count if result.count else 0
                    checks[f"{table} rows"] = f"{count:,}"
            except Exception as e:
                checks[f"{table} rows"] = f"Error: {str(e)[:30]}"

        # Check recent activity across key tables
        try:
            one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

            # Check OHLC data activity
            result = (
                self.supabase.client.table("ohlc_data")
                .select("*", count="exact")
                .gte("timestamp", one_hour_ago)
                .execute()
            )

            ohlc_recent = result.count if result and result.count else 0
            checks["OHLC Updates (1hr)"] = f"{ohlc_recent:,}"

            # Check ML features activity
            result = (
                self.supabase.client.table("ml_features")
                .select("*", count="exact")
                .gte("timestamp", one_hour_ago)
                .execute()
            )

            ml_recent = result.count if result and result.count else 0
            checks["ML Features (1hr)"] = f"{ml_recent:,}"

        except Exception as e:
            checks["Recent Activity"] = f"Error: {str(e)[:50]}"

        self.print_component_status("Database Health", checks)
        self.results["Database Health"] = checks

    def check_process(self, process_name):
        """Check if a process is running"""
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmdline = " ".join(proc.info["cmdline"] or [])
                if process_name.lower() in cmdline.lower():
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return False

    def check_recent_table_activity(self, table_name: str, time_column: str, minutes: int) -> int:
        """Check if table has recent activity"""
        try:
            cutoff_time = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()

            result = (
                self.supabase.client.table(table_name)
                .select("*", count="exact")
                .gte(time_column, cutoff_time)
                .execute()
            )

            return result.count if result and result.count else 0
        except Exception as e:
            logger.error(f"Error checking {table_name} activity: {e}")
            return 0

    def print_component_status(self, component: str, checks: Dict[str, Any]):
        """Print status for a component"""
        # Determine overall status
        critical_checks = [v for k, v in checks.items() if isinstance(v, bool)]

        if not critical_checks:
            # No boolean checks, look at other indicators
            all_good = all(
                (isinstance(v, str) and "Error" not in v and "not found" not in v.lower())
                or (isinstance(v, (int, float)) and v > 0)
                for v in checks.values()
            )
        else:
            # Use boolean checks as primary indicator
            all_good = all(critical_checks)
            partial_good = any(critical_checks)

        if all_good:
            status = f"{Fore.GREEN}✅ RUNNING"
        elif "partial_good" in locals() and partial_good:
            status = f"{Fore.YELLOW}⚠️  PARTIAL"
        else:
            status = f"{Fore.RED}❌ DOWN"

        print(f"Status: {status}")

        for check, value in checks.items():
            if isinstance(value, bool):
                emoji = "✅" if value else "❌"
            elif isinstance(value, str):
                if "Error" in value or "not found" in value.lower() or "N/A" in value:
                    emoji = "❌"
                elif "No " in value or value == "0":
                    emoji = "⚠️"
                else:
                    emoji = "📊"
            elif isinstance(value, (int, float)):
                emoji = "✅" if value > 0 else "⚠️"
            else:
                emoji = "📊"

            print(f"  {emoji} {check}: {value}")

    def print_summary(self):
        """Print overall system summary"""
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}SYSTEM SUMMARY")
        print(f"{Fore.CYAN}{'='*60}")

        critical_systems = [
            "Paper Trading",
            "ML Engine",
            "Data Pipeline",
            "Risk Management",
        ]
        critical_ok = 0

        for system in critical_systems:
            if system in self.results:
                checks = self.results[system]
                # System is considered OK if it has some positive indicators
                has_positive = any(
                    (isinstance(v, bool) and v)
                    or (isinstance(v, str) and "Error" not in v and "No " not in v)
                    or (isinstance(v, (int, float)) and v > 0)
                    for v in checks.values()
                )
                if has_positive:
                    critical_ok += 1

        health_score = (critical_ok / len(critical_systems)) * 100

        if health_score >= 75:
            print(f"{Fore.GREEN}✅ SYSTEM OPERATIONAL ({health_score:.0f}% health)")
        elif health_score >= 50:
            print(f"{Fore.YELLOW}⚠️  DEGRADED PERFORMANCE ({health_score:.0f}% health)")
        else:
            print(f"{Fore.RED}❌ CRITICAL ISSUES ({health_score:.0f}% health)")

        # Action items
        print(f"\n{Fore.CYAN}ACTION ITEMS:")
        print("-" * 40)

        issues = []
        for component, checks in self.results.items():
            for check, value in checks.items():
                if isinstance(value, bool) and not value:
                    issues.append(f"Fix {component}: {check}")
                elif isinstance(value, str) and ("Error" in value or "not found" in value.lower()):
                    issues.append(f"Fix {component}: {check}")
                elif isinstance(value, (int, float)) and value == 0 and "rows" not in check:
                    issues.append(f"Check {component}: {check}")

        if issues:
            for issue in issues[:10]:  # Show top 10 issues
                print(f"  • {issue}")
        else:
            print(f"{Fore.GREEN}  No critical issues detected!")

        # Show what's working well
        print(f"\n{Fore.CYAN}WORKING COMPONENTS:")
        print("-" * 40)

        working = []
        for component, checks in self.results.items():
            positive_checks = [
                k
                for k, v in checks.items()
                if (isinstance(v, bool) and v)
                or (isinstance(v, (int, float)) and v > 0)
                or (isinstance(v, str) and "Error" not in v and "not found" not in v.lower() and v != "0")
            ]
            if positive_checks:
                working.append(f"{component}: {', '.join(positive_checks[:3])}")

        for item in working[:5]:  # Show top 5 working components
            print(f"  ✅ {item}")


def main():
    """Run the system check"""
    try:
        checker = SystemStatusChecker()
        checker.run_complete_check()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Check interrupted by user")
    except Exception as e:
        print(f"\n{Fore.RED}Error running system check: {e}")
        logger.exception("System check failed")


if __name__ == "__main__":
    main()
