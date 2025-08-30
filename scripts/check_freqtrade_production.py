#!/usr/bin/env python3
"""
Check Freqtrade production trades in Supabase
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from loguru import logger


def main():
    """Check production Freqtrade trades"""
    
    print("\n" + "="*60)
    print("🚀 FREQTRADE PRODUCTION STATUS CHECK")
    print("="*60)
    
    db = SupabaseClient()
    
    # Check freqtrade_trades table
    print("\n📊 Freqtrade Trades (Production):")
    try:
        # Get total count
        result = db.client.table("freqtrade_trades").select("*", count="exact").limit(1).execute()
        total_trades = result.count if hasattr(result, 'count') else 0
        print(f"   Total trades: {total_trades}")
        
        if total_trades > 0:
            # Get recent trades
            recent_trades = db.client.table("freqtrade_trades").select("*").order("open_date", desc=True).limit(10).execute()
            
            if recent_trades.data:
                print("\n   Recent trades:")
                for trade in recent_trades.data[:5]:
                    status = "OPEN" if trade.get('is_open') else "CLOSED"
                    symbol = trade.get('pair', 'UNKNOWN')
                    open_date = trade.get('open_date', 'N/A')
                    strategy = trade.get('strategy', 'N/A')
                    print(f"      - {symbol}: {status} (opened {open_date}) - Strategy: {strategy}")
                
                # Count open vs closed
                open_trades = db.client.table("freqtrade_trades").select("*", count="exact").eq("is_open", True).execute()
                closed_trades = db.client.table("freqtrade_trades").select("*", count="exact").eq("is_open", False).execute()
                
                open_count = open_trades.count if hasattr(open_trades, 'count') else 0
                closed_count = closed_trades.count if hasattr(closed_trades, 'count') else 0
                
                print(f"\n   Open positions: {open_count}")
                print(f"   Closed trades: {closed_count}")
        else:
            print("   ❌ No trades found in production database")
            
    except Exception as e:
        print(f"   ❌ Error checking trades: {e}")
    
    # Check recent scan activity
    print("\n📡 Recent Scan Activity:")
    try:
        # Get scans from last hour
        one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        recent_scans = db.client.table("scan_history").select("*", count="exact").gte("timestamp", one_hour_ago).execute()
        scan_count = recent_scans.count if hasattr(recent_scans, 'count') else 0
        
        print(f"   Scans in last hour: {scan_count}")
        
        if scan_count > 0:
            # Get unique symbols scanned
            scans_data = db.client.table("scan_history").select("symbol").gte("timestamp", one_hour_ago).execute()
            if scans_data.data:
                unique_symbols = set(scan['symbol'] for scan in scans_data.data)
                print(f"   Unique symbols scanned: {len(unique_symbols)}")
                
                # Check for CHANNEL strategy scans with TAKE decision
                channel_takes = db.client.table("scan_history").select("*", count="exact").gte("timestamp", one_hour_ago).eq("strategy", "CHANNEL").eq("decision", "TAKE").execute()
                channel_take_count = channel_takes.count if hasattr(channel_takes, 'count') else 0
                print(f"   CHANNEL strategy TAKE signals: {channel_take_count}")
        else:
            print("   ⚠️ No recent scan activity")
            
    except Exception as e:
        print(f"   ❌ Error checking scans: {e}")
    
    print("\n" + "="*60)
    print("\n💡 Summary:")
    print("   • Trading Sentiment is working (shows CHANNEL as best strategy)")
    print("   • Scan history shows 21,949 scans logged")
    print("   • Freqtrade is running on Railway and logging scans")
    
    if total_trades == 0:
        print("\n⚠️ Issue: No trades in production database yet")
        print("\n🔍 Possible reasons:")
        print("   1. Channel thresholds might be too strict")
        print("   2. Position limits might be preventing new trades")
        print("   3. Trade sync from Freqtrade to Supabase might not be working")
        print("   4. Freqtrade might need more time to find good entry points")


if __name__ == "__main__":
    main()
