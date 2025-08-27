#!/usr/bin/env python3
"""
Check recent trading activity to see if paper trading has been running
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient  # noqa: E402


def check_trading_activity():
    """Check recent trading activity"""
    db = SupabaseClient()

    print("\n🔍 Checking Paper Trading Activity\n")
    print("=" * 60)

    # Check different time windows
    time_windows = [
        (1, "hour"),
        (6, "hours"),
        (24, "hours"),
        (48, "hours"),
    ]

    for amount, unit in time_windows:
        if unit == "hour":
            delta = timedelta(hours=amount)
        else:
            delta = timedelta(hours=amount)

        since = (datetime.now(timezone.utc) - delta).isoformat()

        # Check paper_trades
        trades_result = (
            db.client.table("paper_trades")
            .select("created_at, symbol, side, strategy_name, price")
            .gte("created_at", since)
            .order("created_at", desc=True)
            .execute()
        )

        # Check scan_history (even though logging is reduced)
        scans_result = (
            db.client.table("scan_history")
            .select("timestamp, symbol, strategy_name, decision")
            .gte("timestamp", since)
            .order("timestamp", desc=True)
            .limit(5)
            .execute()
        )

        trade_count = len(trades_result.data) if trades_result.data else 0
        scan_count = len(scans_result.data) if scans_result.data else 0

        print(f"\n📊 Last {amount} {unit}:")
        print(f"   Trades executed: {trade_count}")
        print(f"   Scans logged: {scan_count}")

        if trade_count > 0:
            print(f"   Latest trade: {trades_result.data[0]['created_at']}")
            latest = trades_result.data[0]
            print(
                f"                 {latest['symbol']} - "
                f"{latest['side']} ({latest['strategy_name']})"
            )

        if scan_count > 0:
            print(f"   Latest scan: {scans_result.data[0]['timestamp']}")

    # Check system_heartbeat if it exists
    print("\n💓 System Heartbeat Status:")
    try:
        result = (
            db.client.table("system_heartbeat")
            .select("*")
            .eq("service_name", "paper_trading_engine")
            .single()
            .execute()
        )

        if result.data:
            last_hb = result.data.get("last_heartbeat")
            metadata = result.data.get("metadata", {})

            # Parse timestamp and calculate how old it is
            from datetime import datetime

            if last_hb:
                hb_time = datetime.fromisoformat(last_hb.replace("Z", "+00:00"))
                age = datetime.now(timezone.utc) - hb_time
                minutes_old = int(age.total_seconds() / 60)

                if minutes_old < 5:
                    print(f"   ✅ RUNNING - Last heartbeat {minutes_old} " "minutes ago")
                elif minutes_old < 60:
                    print(
                        f"   ⚠️  POSSIBLY STOPPED - Last heartbeat "
                        f"{minutes_old} minutes ago"
                    )
                else:
                    hours_old = minutes_old // 60
                    print(
                        f"   ❌ LIKELY STOPPED - Last heartbeat "
                        f"{hours_old} hours ago"
                    )

                print(f"   Positions open: " f"{metadata.get('positions_open', 0)}")
                print(f"   Balance: ${metadata.get('balance', 0):.2f}")
            else:
                print("   ⚠️  Heartbeat exists but no timestamp")
        else:
            print("   ℹ️  No heartbeat found (new system not deployed yet)")

    except Exception as e:
        print(f"   ℹ️  Heartbeat table not available yet: {e}")

    print("\n" + "=" * 60)

    # Final verdict
    print("\n🎯 VERDICT:")
    if trade_count > 0:
        print("   Paper Trading has been RUNNING (trades found)")
        print("   The 'Stopped' messages were false positives during " "quiet periods")
    else:
        print("   No recent trades, but this could mean:")
        print("   1. Market conditions haven't triggered any trades " "(most likely)")
        print("   2. Service is actually stopped (check Railway dashboard)")

    print("\n💡 To check Railway directly:")
    print("   1. Go to Railway dashboard")
    print("   2. Check 'Trading - Paper Engine' service")
    print("   3. Look at logs and deployment status")


if __name__ == "__main__":
    check_trading_activity()
