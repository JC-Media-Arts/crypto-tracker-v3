#!/usr/bin/env python3
"""
Check Channel strategy activity and diagnose why trades aren't triggering
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "freqtrade" / "user_data"))

from src.data.supabase_client import SupabaseClient
from config_bridge import ConfigBridge
from loguru import logger


def main():
    """Check Channel strategy activity"""
    
    print("\n" + "="*60)
    print("🔍 CHANNEL STRATEGY DIAGNOSTIC CHECK")
    print("="*60)
    
    db = SupabaseClient()
    bridge = ConfigBridge()
    
    # 1. Check current configuration
    print("\n📊 Current Channel Configuration:")
    thresholds = bridge.get_channel_thresholds()
    print(f"   Entry Threshold (buy_zone): {thresholds['entry_threshold']:.3f}")
    print(f"   Exit Threshold (sell_zone): {thresholds['exit_threshold']:.3f}")
    print(f"   RSI Range: {thresholds['rsi_min']}-{thresholds['rsi_max']}")
    print(f"   Channel Strength Min: {thresholds['channel_strength_min']}")
    
    # Check tier-specific thresholds
    config = bridge.load_unified_config()
    channel_config = config.get('strategies', {}).get('CHANNEL', {})
    tier_thresholds = channel_config.get('detection_thresholds_by_tier', {})
    
    if tier_thresholds:
        print("\n   Tier-Specific Buy Zones:")
        for tier, settings in tier_thresholds.items():
            buy_zone = settings.get('buy_zone', 'N/A')
            print(f"      {tier}: {buy_zone}")
    
    # 2. Check recent scan activity
    print("\n📡 Recent Scan Activity (Last Hour):")
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    
    try:
        # Get total scans in last hour
        all_scans = db.client.table("scan_history").select("*", count="exact").gte("timestamp", one_hour_ago).execute()
        total_scans = all_scans.count if hasattr(all_scans, 'count') else 0
        print(f"   Total scans: {total_scans}")
        
        # Get CHANNEL strategy scans
        channel_scans = db.client.table("scan_history").select("*", count="exact").gte("timestamp", one_hour_ago).eq("strategy", "CHANNEL").execute()
        channel_count = channel_scans.count if hasattr(channel_scans, 'count') else 0
        print(f"   CHANNEL scans: {channel_count}")
        
        # Get TAKE decisions
        take_scans = db.client.table("scan_history").select("*").gte("timestamp", one_hour_ago).eq("strategy", "CHANNEL").eq("decision", "TAKE").execute()
        take_count = len(take_scans.data) if take_scans.data else 0
        print(f"   CHANNEL TAKE signals: {take_count}")
        
        if take_scans.data and take_count > 0:
            print("\n   Recent TAKE signals:")
            for scan in take_scans.data[:5]:  # Show first 5
                print(f"      - {scan.get('symbol', 'N/A')} at {scan.get('timestamp', 'N/A')}")
        
        # Get SKIP decisions
        skip_scans = db.client.table("scan_history").select("*").gte("timestamp", one_hour_ago).eq("strategy", "CHANNEL").eq("decision", "SKIP").execute()
        skip_count = len(skip_scans.data) if skip_scans.data else 0
        print(f"   CHANNEL SKIP signals: {skip_count}")
        
    except Exception as e:
        print(f"   ❌ Error checking scans: {e}")
    
    # 3. Check current market conditions
    print("\n📈 Current Market Conditions:")
    
    # Get a few symbols to check their current channel positions
    symbols_to_check = ['BTC', 'ETH', 'SOL', 'MATIC', 'AVAX']
    
    for symbol in symbols_to_check:
        try:
            # Get recent OHLC data
            result = db.client.table("ohlc_data").select("close").eq("symbol", symbol).eq("timeframe", "1h").order("timestamp", desc=True).limit(30).execute()
            
            if result.data and len(result.data) >= 20:
                # Simple channel position calculation (simplified, not exact BB)
                closes = [float(d['close']) for d in result.data]
                closes.reverse()  # Oldest first
                
                current_price = closes[-1]
                sma_20 = sum(closes[-20:]) / 20
                std_20 = (sum((x - sma_20) ** 2 for x in closes[-20:]) / 20) ** 0.5
                
                bb_upper = sma_20 + (2 * std_20)
                bb_lower = sma_20 - (2 * std_20)
                
                if bb_upper > bb_lower:
                    channel_position = (current_price - bb_lower) / (bb_upper - bb_lower)
                    
                    status = "✅ BUY ZONE" if channel_position <= thresholds['entry_threshold'] else ""
                    print(f"   {symbol}: Channel Position = {channel_position:.3f} {status}")
                
        except Exception as e:
            print(f"   {symbol}: Error - {e}")
    
    # 4. Check Freqtrade trades
    print("\n💼 Freqtrade Trades:")
    try:
        # Check total trades
        all_trades = db.client.table("freqtrade_trades").select("*", count="exact").execute()
        total_trades = all_trades.count if hasattr(all_trades, 'count') else 0
        print(f"   Total trades in database: {total_trades}")
        
        if total_trades > 0:
            # Get recent trades
            recent_trades = db.client.table("freqtrade_trades").select("*").order("open_date", desc=True).limit(5).execute()
            if recent_trades.data:
                print("\n   Recent trades:")
                for trade in recent_trades.data:
                    print(f"      - {trade.get('pair', 'N/A')} opened at {trade.get('open_date', 'N/A')}")
        
    except Exception as e:
        print(f"   ❌ Error checking trades: {e}")
    
    # 5. Diagnosis
    print("\n🔍 Diagnosis:")
    
    if total_scans == 0:
        print("   ❌ No scans detected - Freqtrade might not be running")
    elif channel_count == 0:
        print("   ❌ No CHANNEL scans - Strategy might not be active")
    elif take_count == 0:
        print("   ⚠️ CHANNEL is scanning but not finding opportunities")
        print("   Possible reasons:")
        print("   - Buy zones might still be too restrictive")
        print("   - Market conditions not favorable (no coins oversold)")
        print("   - Other conditions not met (RSI, volume, volatility)")
    else:
        print(f"   ✅ CHANNEL found {take_count} opportunities")
        if total_trades == 0:
            print("   ❌ But no trades executed - Check position limits or trade sync")
        else:
            print("   ✅ Trades are being executed")
    
    print("\n💡 Next Steps:")
    print("   1. Check Railway logs for Freqtrade container")
    print("   2. Verify Freqtrade is running: 'docker ps' on Railway")
    print("   3. Check if trade sync is working")
    print("   4. Consider loosening buy_zone if no opportunities found")


if __name__ == "__main__":
    main()
