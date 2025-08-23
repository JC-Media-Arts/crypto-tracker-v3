#!/usr/bin/env python3
"""
Simple trading activity monitor for terminal
Shows real-time trading activity, shadow testing status, and performance metrics
"""

import asyncio
import sys
from datetime import datetime, timedelta
from collections import Counter
from src.data.supabase_client import SupabaseClient


def clear_screen():
    """Clear terminal screen"""
    print("\033[2J\033[H")


async def monitor_trading():
    """Monitor trading activity"""
    client = SupabaseClient()

    while True:
        try:
            clear_screen()

            print("=" * 80)
            print(" " * 25 + "📊 CRYPTO TRADING MONITOR")
            print(" " * 20 + f"Last Update: {datetime.now().strftime('%H:%M:%S')}")
            print("=" * 80)

            # 1. Recent Trading Activity
            print("\n🤖 RECENT SCANS (Last 30 minutes)")
            print("-" * 60)

            cutoff = (datetime.utcnow() - timedelta(minutes=30)).isoformat()
            scans = (
                client.client.table("scan_history")
                .select("*")
                .gte("timestamp", cutoff)
                .order("scan_id", desc=True)
                .limit(100)
                .execute()
            )

            if scans.data:
                # Group by decision
                decisions = Counter(s.get("decision", "unknown") for s in scans.data)
                total_scans = len(scans.data)

                print(f"Total Scans: {total_scans}")
                print("\nDecisions:")
                for decision, count in sorted(decisions.items()):
                    pct = (count / total_scans) * 100
                    print(f"  {decision:20s}: {count:3d} ({pct:5.1f}%)")

                # Show latest scans
                print("\nLatest 5 Scans:")
                for scan in scans.data[:5]:
                    time_str = scan["timestamp"][:19] if scan.get("timestamp") else "unknown"
                    symbol = scan.get("symbol", "???")
                    strategy = scan.get("strategy_name", "???")
                    decision = scan.get("decision", "???")
                    confidence = scan.get("ml_confidence")
                    conf_str = f"{confidence:.2f}" if confidence is not None else "N/A"

                    print(f"  {time_str} | {symbol:6s} | {strategy:8s} | {decision:15s} | Conf: {conf_str}")
            else:
                print("No recent scans found")

            # 2. Shadow Testing Status
            print("\n🔬 SHADOW TESTING STATUS")
            print("-" * 60)

            # Total shadows
            total_shadows = client.client.table("shadow_variations").select("count", count="exact").execute()
            print(f"Total Shadow Variations: {total_shadows.count:,}")

            # Recent shadows (last 5 minutes)
            recent_cutoff = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
            recent_shadows = (
                client.client.table("shadow_variations")
                .select("count", count="exact")
                .gte("created_at", recent_cutoff)
                .execute()
            )
            print(f"Shadows in last 5 min: {recent_shadows.count}")

            # Shadows that would take trades
            would_take = (
                client.client.table("shadow_variations")
                .select("count", count="exact")
                .eq("would_take_trade", True)
                .execute()
            )
            print(f"Would Take Trade: {would_take.count}")

            # Shadow outcomes
            outcomes = client.client.table("shadow_outcomes").select("count", count="exact").execute()
            print(f"Evaluated Outcomes: {outcomes.count}")

            # Get recent outcomes
            if outcomes.count > 0:
                recent_outcomes = (
                    client.client.table("shadow_outcomes")
                    .select("*")
                    .order("evaluated_at", desc=True)
                    .limit(10)
                    .execute()
                )

                if recent_outcomes.data:
                    outcome_counts = Counter(o["outcome_status"] for o in recent_outcomes.data)
                    print("\nRecent Outcome Status:")
                    for status, count in outcome_counts.items():
                        print(f"  {status}: {count}")

            # 3. Shadow Variations Distribution
            print("\n📈 SHADOW VARIATIONS (Last Hour)")
            print("-" * 60)

            hour_cutoff = (datetime.utcnow() - timedelta(hours=1)).isoformat()
            hour_shadows = (
                client.client.table("shadow_variations")
                .select("variation_name")
                .gte("created_at", hour_cutoff)
                .execute()
            )

            if hour_shadows.data:
                variations = Counter(s["variation_name"] for s in hour_shadows.data)
                total = sum(variations.values())

                for name, count in sorted(variations.items()):
                    pct = (count / total) * 100
                    bar = "█" * int(pct / 2)  # Simple bar chart
                    print(f"  {name:20s}: {count:4d} ({pct:4.1f}%) {bar}")

            # 4. Performance Metrics (if available)
            print("\n🏆 PERFORMANCE METRICS")
            print("-" * 60)

            perf = (
                client.client.table("shadow_performance")
                .select("*")
                .order("last_updated", desc=True)
                .limit(5)
                .execute()
            )

            if perf.data:
                for p in perf.data:
                    print(f"\n{p['variation_name']} ({p['timeframe']}):")
                    win_rate = p.get("win_rate")
                    win_rate_str = f"{win_rate:.1f}%" if win_rate is not None else "N/A"
                    print(f"  Win Rate: {win_rate_str}")
                    print(f"  Total Trades: {p.get('total_trades', 0)}")
                    avg_pnl = p.get("avg_pnl")
                    avg_pnl_str = f"{avg_pnl:.2f}%" if avg_pnl is not None else "N/A"
                    print(f"  Avg P&L: {avg_pnl_str}")
            else:
                print("No performance data yet (needs completed outcomes)")

            print("\n" + "=" * 80)
            print("Press Ctrl+C to exit | Updates every 10 seconds")

        except KeyboardInterrupt:
            print("\n\nExiting monitor...")
            break
        except Exception as e:
            print(f"\nError: {e}")

        await asyncio.sleep(10)


if __name__ == "__main__":
    print("Starting Trading Monitor...")
    print("Loading data...")

    try:
        asyncio.run(monitor_trading())
    except KeyboardInterrupt:
        print("\nMonitor stopped.")
        sys.exit(0)
