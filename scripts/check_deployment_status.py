#!/usr/bin/env python3
"""
Quick deployment status checker for code review
"""

import os
import sys
import subprocess
import json
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))


def check_railway_status():
    """Check Railway deployment status"""
    print("=" * 80)
    print("RAILWAY DEPLOYMENT STATUS")
    print("=" * 80)
    print()

    try:
        # Check if railway CLI is installed
        result = subprocess.run(["which", "railway"], capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ Railway CLI not installed")
            print("   Install with: npm install -g @railway/cli")
            return

        print("✅ Railway CLI found")
        print()

        # Try to get project status
        print("Checking Railway project status...")
        result = subprocess.run(["railway", "status"], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
        if result.returncode == 0:
            print(result.stdout)
        else:
            print("⚠️  Could not get Railway status. Are you logged in?")
            print("   Run: railway login")

    except Exception as e:
        print(f"Error checking Railway: {e}")


def check_environment_variables():
    """Check critical environment variables"""
    print()
    print("=" * 80)
    print("ENVIRONMENT VARIABLES")
    print("=" * 80)
    print()

    required_vars = ["POLYGON_API_KEY", "SUPABASE_URL", "SUPABASE_KEY", "SLACK_WEBHOOK_URL"]

    optional_vars = ["KRAKEN_API_KEY", "KRAKEN_API_SECRET", "ENVIRONMENT", "POSITION_SIZE", "MAX_POSITIONS"]

    print("Required Variables:")
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Hide sensitive values
            if "KEY" in var or "SECRET" in var:
                print(f"  ✅ {var}: ***hidden***")
            else:
                print(f"  ✅ {var}: {value[:20]}...")
        else:
            print(f"  ❌ {var}: NOT SET")

    print("\nOptional Variables:")
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            if "KEY" in var or "SECRET" in var:
                print(f"  ✅ {var}: ***hidden***")
            else:
                print(f"  ✅ {var}: {value}")
        else:
            print(f"  ⚠️  {var}: not set (using defaults)")


def check_local_services():
    """Check if any services are running locally"""
    print()
    print("=" * 80)
    print("LOCAL SERVICES")
    print("=" * 80)
    print()

    # Check for running Python processes
    result = subprocess.run(["ps", "aux"], capture_output=True, text=True)

    services = [
        "run_paper_trading.py",
        "run_data_collector.py",
        "run_feature_calculator.py",
        "incremental_ohlc_updater.py",
    ]

    for service in services:
        if service in result.stdout:
            print(f"  ✅ {service} is running")
        else:
            print(f"  ⚠️  {service} is not running")


def check_database_connection():
    """Quick database connection check"""
    print()
    print("=" * 80)
    print("DATABASE CONNECTION")
    print("=" * 80)
    print()

    try:
        from src.config.settings import get_settings
        from supabase import create_client

        settings = get_settings()
        supabase = create_client(settings.supabase_url, settings.supabase_key)

        # Try a simple query
        result = supabase.table("ohlc_data").select("symbol").limit(1).execute()

        if result.data:
            print("✅ Database connection successful")
        else:
            print("⚠️  Database connected but no data found")

    except Exception as e:
        print(f"❌ Database connection failed: {e}")


def check_recent_logs():
    """Check for recent log files"""
    print()
    print("=" * 80)
    print("RECENT LOG FILES")
    print("=" * 80)
    print()

    log_dir = Path(__file__).parent.parent / "logs"

    if not log_dir.exists():
        print("⚠️  No logs directory found")
        return

    # Get recent log files
    log_files = sorted(log_dir.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)

    if log_files:
        print(f"Found {len(log_files)} log files:")
        for log_file in log_files[:5]:  # Show last 5
            size = log_file.stat().st_size / 1024  # KB
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            print(f"  - {log_file.name}: {size:.1f} KB, modified {mtime}")
    else:
        print("⚠️  No log files found")


def main():
    """Run all checks"""
    print("\n" + "=" * 80)
    print("CRYPTO TRACKER V3 - DEPLOYMENT STATUS CHECK")
    print("=" * 80)
    print(f"Check Time: {datetime.now()}")
    print()

    check_environment_variables()
    check_database_connection()
    check_railway_status()
    check_local_services()
    check_recent_logs()

    print("\n" + "=" * 80)
    print("STATUS CHECK COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
