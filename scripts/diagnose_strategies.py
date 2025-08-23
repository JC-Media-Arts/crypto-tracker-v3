#!/usr/bin/env python3
"""
Diagnose why SWING and CHANNEL strategies aren't scanning
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))


def diagnose_strategies():
    """Find why SWING and CHANNEL aren't scanning"""

    print("=" * 60)
    print("🔍 STRATEGY DIAGNOSIS")
    print("=" * 60)

    # Check strategy configurations
    from src.config.settings import get_settings

    settings = get_settings()

    print("\n1. Checking Strategy Settings:")
    print("-" * 40)

    # Check DCA settings (working reference)
    print(f"   DCA min_volume: {getattr(settings, 'dca_min_volume', 'Not set')}")
    print(f"   DCA enabled: {getattr(settings, 'enable_dca_strategy', True)}")

    # Check SWING settings
    print(f"\n   SWING min_volume: {getattr(settings, 'swing_min_volume', 'Not set')}")
    print(f"   SWING enabled: {getattr(settings, 'enable_swing_strategy', True)}")
    print(
        f"   SWING min_breakout: {getattr(settings, 'swing_min_breakout_strength', 'Not set')}"
    )

    # Check CHANNEL settings
    print(
        f"\n   CHANNEL min_volume: {getattr(settings, 'channel_min_volume', 'Not set')}"
    )
    print(f"   CHANNEL enabled: {getattr(settings, 'enable_channel_strategy', True)}")
    print(
        f"   CHANNEL min_touches: {getattr(settings, 'channel_min_touches', 'Not set')}"
    )

    # Check if detector classes exist and can be imported
    print("\n2. Checking Strategy Modules:")
    print("-" * 40)

    try:
        from src.strategies.swing.detector import SwingDetector

        print("   ✅ SwingDetector imported successfully")

        # Check if it has the detect method
        swing = SwingDetector()
        if hasattr(swing, "detect"):
            print("   ✅ SwingDetector has detect method")
        else:
            print("   ❌ SwingDetector missing detect method")

    except ImportError as e:
        print(f"   ❌ Failed to import SwingDetector: {e}")
    except Exception as e:
        print(f"   ❌ Error initializing SwingDetector: {e}")

    try:
        from src.strategies.channel.detector import ChannelDetector

        print("   ✅ ChannelDetector imported successfully")

        # Check if it has the detect method
        channel = ChannelDetector()
        if hasattr(channel, "detect"):
            print("   ✅ ChannelDetector has detect method")
        else:
            print("   ❌ ChannelDetector missing detect method")

    except ImportError as e:
        print(f"   ❌ Failed to import ChannelDetector: {e}")
    except Exception as e:
        print(f"   ❌ Error initializing ChannelDetector: {e}")

    # Test strategy detection on actual data
    print("\n3. Testing Detection on BTC:")
    print("-" * 40)

    from src.data.supabase_client import SupabaseClient

    supabase = SupabaseClient()

    # Get recent BTC data
    try:
        # Get last 100 data points for BTC
        one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        result = (
            supabase.client.table("ohlc_data")
            .select("*")
            .eq("symbol", "BTC")
            .eq("timeframe", "15m")
            .gte("timestamp", one_hour_ago)
            .order("timestamp", desc=True)
            .limit(100)
            .execute()
        )

        if result.data:
            print(f"   Found {len(result.data)} BTC data points")

            # Try SWING detection
            try:
                from src.strategies.swing.detector import SwingDetector

                swing = SwingDetector()

                # Check what parameters the detect method needs
                import inspect

                sig = inspect.signature(swing.detect)
                print(f"   SwingDetector.detect signature: {sig}")

                # Try to call detect with appropriate parameters
                swing_result = swing.detect("BTC", "15m")
                print(f"   SWING detection result: {swing_result}")

            except Exception as e:
                print(f"   ❌ SWING detection error: {e}")

            # Try CHANNEL detection
            try:
                from src.strategies.channel.detector import ChannelDetector

                channel = ChannelDetector()

                # Check what parameters the detect method needs
                sig = inspect.signature(channel.detect)
                print(f"   ChannelDetector.detect signature: {sig}")

                # Try to call detect with appropriate parameters
                channel_result = channel.detect("BTC", "15m")
                print(f"   CHANNEL detection result: {channel_result}")

            except Exception as e:
                print(f"   ❌ CHANNEL detection error: {e}")
        else:
            print("   ❌ No BTC data found")

    except Exception as e:
        print(f"   ❌ Error fetching BTC data: {e}")

    # Check scan history to see if strategies ever worked
    print("\n4. Checking Scan History:")
    print("-" * 40)

    try:
        # Check last time each strategy scanned
        for strategy in ["DCA", "SWING", "CHANNEL"]:
            result = (
                supabase.client.table("scan_history")
                .select("timestamp")
                .eq("strategy_name", strategy)
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )

            if result.data and len(result.data) > 0:
                last_scan = result.data[0]["timestamp"]
                last_scan_dt = datetime.fromisoformat(last_scan.replace("Z", "+00:00"))
                time_ago = datetime.now(timezone.utc) - last_scan_dt
                hours_ago = time_ago.total_seconds() / 3600

                if hours_ago < 1:
                    print(f"   {strategy}: Last scan {hours_ago:.1f} hours ago ✅")
                elif hours_ago < 24:
                    print(f"   {strategy}: Last scan {hours_ago:.1f} hours ago ⚠️")
                else:
                    print(f"   {strategy}: Last scan {hours_ago:.1f} hours ago ❌")
            else:
                print(f"   {strategy}: Never scanned ❌")

    except Exception as e:
        print(f"   Error checking scan history: {e}")

    # Check if there are any runner scripts for strategies
    print("\n5. Checking Runner Scripts:")
    print("-" * 40)

    scripts_dir = Path(__file__).parent
    strategy_scripts = [
        "run_strategy_manager.py",
        "run_signal_generator.py",
        "run_swing_scanner.py",
        "run_channel_scanner.py",
        "run_dca_scanner.py",
    ]

    for script in strategy_scripts:
        script_path = scripts_dir / script
        if script_path.exists():
            print(f"   ✅ {script} exists")
        else:
            print(f"   ❌ {script} not found")

    # Provide recommendations
    print("\n" + "=" * 60)
    print("📝 RECOMMENDATIONS:")
    print("=" * 60)

    print("\n1. Add these to your .env file if not present:")
    print("-" * 40)
    print(
        """
# SWING Strategy Settings
SWING_ENABLED=true
SWING_MIN_VOLUME=100000
SWING_MIN_BREAKOUT_STRENGTH=1.5
SWING_VOLUME_SURGE_THRESHOLD=1.5
SWING_MIN_TOUCHES=2
SWING_LOOKBACK_PERIODS=20

# CHANNEL Strategy Settings
CHANNEL_ENABLED=true
CHANNEL_MIN_VOLUME=100000
CHANNEL_MIN_TOUCHES=2
CHANNEL_BREAKOUT_THRESHOLD=0.02
CHANNEL_WIDTH_MIN=0.02
CHANNEL_WIDTH_MAX=0.15
CHANNEL_LOOKBACK_PERIODS=20
"""
    )

    print("\n2. If strategies aren't running, start them with:")
    print("-" * 40)
    print("   python3 scripts/run_signal_generator.py")
    print("   # OR")
    print("   python3 -m src.strategies.signal_generator")

    print("\n✅ Diagnosis complete!")


if __name__ == "__main__":
    diagnose_strategies()
