#!/usr/bin/env python3
"""
Monitor for first trades after deploying simplified strategy
"""

import os
import sys
import time
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from supabase import create_client, Client
import pandas as pd

load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

def check_scan_decisions():
    """Check recent scan decisions to see if they're more accurate now"""
    print("\n📊 RECENT SCAN DECISIONS (Last 10 minutes)")
    print("="*50)
    
    since = datetime.now(timezone.utc) - timedelta(minutes=10)
    
    response = supabase.table('scan_history').select('*').gte(
        'timestamp', since.isoformat()
    ).order('timestamp', desc=True).limit(100).execute()
    
    if response.data:
        df = pd.DataFrame(response.data)
        
        # Count decisions
        decision_counts = df['decision'].value_counts()
        print(f"\nDecision breakdown:")
        for decision, count in decision_counts.items():
            print(f"  {decision}: {count}")
        
        # Sample some TAKE decisions to check if they're valid
        takes = df[df['decision'] == 'TAKE'].head(5)
        if not takes.empty:
            print(f"\n✅ Sample TAKE decisions (should have channel < 0.70):")
            for _, row in takes.iterrows():
                features = row.get('features', {})
                if isinstance(features, dict):
                    channel = features.get('channel_position', 0)
                    rsi = features.get('rsi', 0)
                    print(f"  {row['symbol']}: Channel={channel:.3f}, RSI={rsi:.1f}")
        
        # Sample some SKIP decisions
        skips = df[df['decision'] == 'SKIP'].head(5)
        if not skips.empty:
            print(f"\n❌ Sample SKIP decisions (should have channel > 0.70):")
            for _, row in skips.iterrows():
                features = row.get('features', {})
                if isinstance(features, dict):
                    channel = features.get('channel_position', 0)
                    rsi = features.get('rsi', 0)
                    print(f"  {row['symbol']}: Channel={channel:.3f}, RSI={rsi:.1f}")
    else:
        print("No scan data in last 10 minutes")

def check_new_trades():
    """Check if any trades have been executed"""
    print("\n💰 CHECKING FOR NEW TRADES")
    print("="*50)
    
    # Check last hour
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    
    # Check freqtrade_trades table
    response = supabase.table('freqtrade_trades').select('*').gte(
        'open_date', since.isoformat()
    ).order('open_date', desc=True).execute()
    
    if response.data:
        print(f"\n🎉 FOUND {len(response.data)} NEW TRADES!")
        for trade in response.data[:5]:  # Show first 5
            print(f"\n  Trade #{trade.get('trade_id', 'N/A')}:")
            print(f"    Pair: {trade.get('pair', 'N/A')}")
            print(f"    Amount: ${trade.get('amount', 0):.2f}")
            print(f"    Open Rate: ${trade.get('open_rate', 0):.4f}")
            print(f"    Open Date: {trade.get('open_date', 'N/A')}")
            print(f"    Strategy: {trade.get('strategy', 'N/A')}")
            if trade.get('is_open'):
                print(f"    Status: 🟢 OPEN")
            else:
                print(f"    Status: 🔴 CLOSED")
                print(f"    Close Rate: ${trade.get('close_rate', 0):.4f}")
                print(f"    Profit: ${trade.get('close_profit_abs', 0):.2f}")
        return True
    else:
        print("❌ No trades executed yet")
        
        # Check scan history to see if we're getting signals
        response = supabase.table('scan_history').select('decision').gte(
            'timestamp', since.isoformat()
        ).execute()
        
        if response.data:
            df = pd.DataFrame(response.data)
            take_count = (df['decision'] == 'TAKE').sum()
            print(f"\n📊 But found {take_count} TAKE signals in scan history")
            print("   Trades should start soon if Railway deployment is complete")
        
        return False

def check_deployment_status():
    """Give tips on checking Railway deployment"""
    print("\n🚂 RAILWAY DEPLOYMENT STATUS")
    print("="*50)
    print("""
To check if deployment is complete:

1. Go to Railway dashboard
2. Check "Freqtrade - Trading Engine" service
3. Look for these in logs:
   - "SimpleChannelStrategy initialized with loosened thresholds"
   - "Entry threshold: 0.7"
   - "Scan logger initialized" (or warning if not)
   
4. If you see errors about:
   - "No module named 'scan_logger'" - that's OK, strategy still works
   - Database connection - check DATABASE_URL env var
   - Missing pairs - some memecoins might not be on Kraken
   
5. Deployment typically takes 2-3 minutes after push
""")

def main():
    print("\n🔍 MONITORING FOR FIRST TRADES")
    print("="*60)
    print("Strategy: SimpleChannelStrategy")
    print("Entry Threshold: 70% of channel (very loose)")
    print("RSI Range: 20-80")
    print("Expected: Should see trades within 5-10 minutes")
    
    iteration = 0
    trades_found = False
    
    while not trades_found and iteration < 20:  # Monitor for 10 minutes
        iteration += 1
        print(f"\n{'='*60}")
        print(f"Check #{iteration} at {datetime.now().strftime('%H:%M:%S')}")
        
        # Check scans first
        check_scan_decisions()
        
        # Check for trades
        trades_found = check_new_trades()
        
        if not trades_found:
            if iteration == 1:
                check_deployment_status()
            
            print(f"\n⏳ Waiting 30 seconds before next check...")
            time.sleep(30)
        else:
            print("\n🎉 SUCCESS! Trades are executing!")
            print("\nNext steps:")
            print("1. Monitor performance for 30 minutes")
            print("2. If too many trades, tighten thresholds slightly")
            print("3. If good balance, let it run for a few hours")
            print("4. Gradually optimize thresholds based on results")
            break
    
    if not trades_found:
        print("\n⚠️ No trades after 10 minutes of monitoring")
        print("\nTroubleshooting steps:")
        print("1. Check Railway logs for errors")
        print("2. Verify DATABASE_URL is set in Railway")
        print("3. Check if service is actually running")
        print("4. Try UltraSimpleRSI strategy (even looser)")
        print("5. Check Freqtrade webserver if enabled")

if __name__ == "__main__":
    main()
