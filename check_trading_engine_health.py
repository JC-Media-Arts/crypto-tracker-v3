#!/usr/bin/env python3
"""
Comprehensive health check for Freqtrade Trading Engine
Checks: scans, trades, configuration, data sync, and more
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client
import json
from tabulate import tabulate

# Load environment variables
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Error: SUPABASE_URL and SUPABASE_KEY must be set in environment.")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def check_scan_history():
    """Check if scans are being saved to scan_history table"""
    print("\n" + "="*60)
    print("1. SCAN HISTORY CHECK")
    print("="*60)
    
    # Check last 30 minutes
    thirty_min_ago = datetime.now(timezone.utc) - timedelta(minutes=30)
    
    try:
        # Get recent scans
        response = supabase.table("scan_history") \
            .select("*") \
            .gte("timestamp", thirty_min_ago.isoformat()) \
            .order("timestamp", desc=True) \
            .limit(100) \
            .execute()
        
        if response.data:
            df = pd.DataFrame(response.data)
            print(f"✅ Found {len(response.data)} scans in last 30 minutes")
            
            # Group by decision
            decision_counts = df['decision'].value_counts()
            print("\nDecision breakdown:")
            for decision, count in decision_counts.items():
                print(f"  {decision}: {count}")
            
            # Group by strategy
            if 'strategy_name' in df.columns:
                strategy_counts = df['strategy_name'].value_counts()
                print("\nStrategy breakdown:")
                for strategy, count in strategy_counts.items():
                    print(f"  {strategy}: {count}")
            
            # Show recent TAKE decisions
            take_decisions = df[df['decision'] == 'TAKE']
            if not take_decisions.empty:
                print(f"\n✅ {len(take_decisions)} TAKE decisions (potential trades):")
                for _, row in take_decisions.head(5).iterrows():
                    print(f"  - {row['symbol']} at {row['timestamp']} (confidence: {row.get('ml_confidence', 'N/A')})")
            else:
                print("\n⚠️ No TAKE decisions in last 30 minutes")
                
            # Check for errors
            error_decisions = df[df['decision'] == 'ERROR']
            if not error_decisions.empty:
                print(f"\n⚠️ {len(error_decisions)} ERROR decisions found")
                
        else:
            print("❌ No scans found in last 30 minutes - scan_logger may not be working")
            
    except Exception as e:
        print(f"❌ Error checking scan history: {e}")
    
    return len(response.data) if response.data else 0

def check_freqtrade_trades():
    """Check if trades are being executed and saved"""
    print("\n" + "="*60)
    print("2. FREQTRADE TRADES CHECK")
    print("="*60)
    
    try:
        # Check for any trades in last hour
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        
        response = supabase.table("freqtrade_trades") \
            .select("*") \
            .gte("open_date", one_hour_ago.isoformat()) \
            .order("open_date", desc=True) \
            .execute()
        
        if response.data:
            print(f"✅ Found {len(response.data)} trades opened in last hour")
            
            df = pd.DataFrame(response.data)
            
            # Show trade summary
            open_trades = df[df['is_open'] == True]
            closed_trades = df[df['is_open'] == False]
            
            print(f"\nTrade Status:")
            print(f"  Open trades: {len(open_trades)}")
            print(f"  Closed trades: {len(closed_trades)}")
            
            if not df.empty:
                print(f"\nRecent trades:")
                for _, trade in df.head(5).iterrows():
                    status = "OPEN" if trade['is_open'] else "CLOSED"
                    print(f"  - {trade['pair']}: {status} (opened: {trade['open_date']})")
                    
        else:
            print("⚠️ No trades found in last hour")
            print("  This could mean:")
            print("  - No good entry signals found")
            print("  - Strategy thresholds too strict")
            print("  - Not enough capital")
            print("  - PostgreSQL connection not working")
            
        # Check all-time trades
        all_trades = supabase.table("freqtrade_trades") \
            .select("id") \
            .execute()
        
        print(f"\nTotal trades in database: {len(all_trades.data) if all_trades.data else 0}")
        
    except Exception as e:
        print(f"❌ Error checking trades: {e}")
        print("  PostgreSQL connection may not be configured correctly")
    
    return len(response.data) if response.data else 0

def check_ohlc_data_coverage():
    """Check which pairs have recent OHLC data"""
    print("\n" + "="*60)
    print("3. OHLC DATA COVERAGE CHECK")
    print("="*60)
    
    try:
        # Check data from last 24 hours
        one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
        
        # Get distinct symbols with recent data
        response = supabase.table("ohlc_data") \
            .select("symbol") \
            .gte("timestamp", one_day_ago.isoformat()) \
            .execute()
        
        if response.data:
            symbols = set(row['symbol'] for row in response.data)
            print(f"✅ {len(symbols)} symbols have data from last 24 hours")
            
            # Check against our whitelist
            with open('freqtrade/config/config.json', 'r') as f:
                config = json.load(f)
            
            whitelist = config['exchange']['pair_whitelist']
            whitelist_symbols = [pair.replace('/USD', '') for pair in whitelist]
            
            missing_data = []
            for symbol in whitelist_symbols:
                if symbol not in symbols:
                    missing_data.append(symbol)
            
            if missing_data:
                print(f"\n⚠️ {len(missing_data)} pairs in whitelist missing recent data:")
                for symbol in missing_data[:10]:  # Show first 10
                    print(f"  - {symbol}")
            else:
                print("✅ All whitelisted pairs have recent data")
                
        else:
            print("❌ No OHLC data found from last 24 hours")
            
    except Exception as e:
        print(f"❌ Error checking OHLC data: {e}")
    
    return len(symbols) if response.data else 0

def check_trading_config():
    """Check current trading configuration from Supabase"""
    print("\n" + "="*60)
    print("4. TRADING CONFIGURATION CHECK")
    print("="*60)
    
    try:
        response = supabase.table("trading_config") \
            .select("*") \
            .order("updated_at", desc=True) \
            .limit(1) \
            .execute()
        
        if response.data:
            config = response.data[0]['config']
            
            print(f"✅ Config loaded (version {config.get('version', 'unknown')})")
            
            # Check key settings
            position_mgmt = config.get('position_management', {})
            print(f"\nPosition Management:")
            print(f"  Max positions total: {position_mgmt.get('max_positions_total', 'N/A')}")
            print(f"  Max per strategy: {position_mgmt.get('max_positions_per_strategy', 'N/A')}")
            print(f"  Position size: ${position_mgmt.get('position_sizing', {}).get('base_position_size_usd', 'N/A')}")
            
            # Check CHANNEL strategy thresholds
            channel = config.get('strategies', {}).get('CHANNEL', {})
            if channel:
                thresholds = channel.get('detection_thresholds', {})
                print(f"\nCHANNEL Strategy Thresholds:")
                print(f"  Entry threshold: {thresholds.get('channel_entry_threshold', 'N/A')}")
                print(f"  RSI range: {thresholds.get('rsi_min', 'N/A')} - {thresholds.get('rsi_max', 'N/A')}")
                print(f"  Volume ratio min: {thresholds.get('volume_ratio_min', 'N/A')}")
                
        else:
            print("❌ No trading config found in database")
            
    except Exception as e:
        print(f"❌ Error checking config: {e}")

def check_recent_performance():
    """Check recent trading performance"""
    print("\n" + "="*60)
    print("5. RECENT PERFORMANCE CHECK")
    print("="*60)
    
    try:
        # Get trades from last 24 hours
        one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
        
        response = supabase.table("freqtrade_trades") \
            .select("*") \
            .gte("open_date", one_day_ago.isoformat()) \
            .execute()
        
        if response.data:
            df = pd.DataFrame(response.data)
            
            # Calculate metrics
            closed_trades = df[df['is_open'] == False]
            if not closed_trades.empty:
                total_profit = closed_trades['close_profit_abs'].sum() if 'close_profit_abs' in closed_trades.columns else 0
                avg_profit_pct = closed_trades['close_profit'].mean() * 100 if 'close_profit' in closed_trades.columns else 0
                win_rate = (closed_trades['close_profit'] > 0).mean() * 100 if 'close_profit' in closed_trades.columns else 0
                
                print(f"Last 24h closed trades: {len(closed_trades)}")
                print(f"  Total profit: ${total_profit:.2f}")
                print(f"  Avg profit: {avg_profit_pct:.2f}%")
                print(f"  Win rate: {win_rate:.1f}%")
            else:
                print("No closed trades in last 24 hours")
                
            # Show open positions
            open_trades = df[df['is_open'] == True]
            if not open_trades.empty:
                print(f"\nCurrently open: {len(open_trades)} positions")
                total_stake = open_trades['stake_amount'].sum() if 'stake_amount' in open_trades.columns else 0
                print(f"  Total capital deployed: ${total_stake:.2f}")
                
        else:
            print("No trades in last 24 hours")
            
    except Exception as e:
        print(f"❌ Error checking performance: {e}")

def check_system_health():
    """Overall system health summary"""
    print("\n" + "="*60)
    print("SYSTEM HEALTH SUMMARY")
    print("="*60)
    
    health_scores = {
        "Scan Logger": "❌ Not Working",
        "Trade Execution": "❌ Not Working",
        "Data Coverage": "❌ Poor",
        "Configuration": "❌ Missing",
        "Overall": "❌ Critical"
    }
    
    # Check each component
    scans = check_scan_history()
    trades = check_freqtrade_trades()
    data = check_ohlc_data_coverage()
    check_trading_config()
    check_recent_performance()
    
    # Update health scores
    if scans > 0:
        health_scores["Scan Logger"] = "✅ Working" if scans > 100 else "⚠️ Low Activity"
    
    if trades > 0:
        health_scores["Trade Execution"] = "✅ Working"
    elif scans > 0:
        health_scores["Trade Execution"] = "⚠️ No Trades (but scans working)"
    
    if data > 70:
        health_scores["Data Coverage"] = "✅ Good"
    elif data > 40:
        health_scores["Data Coverage"] = "⚠️ Partial"
    
    # Overall assessment
    if "✅" in health_scores["Scan Logger"] and trades > 0:
        health_scores["Overall"] = "✅ Healthy"
    elif "✅" in health_scores["Scan Logger"]:
        health_scores["Overall"] = "⚠️ Partially Working"
    else:
        health_scores["Overall"] = "❌ Critical Issues"
    
    print("\n" + "="*60)
    print("HEALTH STATUS:")
    print("="*60)
    for component, status in health_scores.items():
        print(f"{component}: {status}")
    
    print("\n" + "="*60)
    print("RECOMMENDATIONS:")
    print("="*60)
    
    if trades == 0:
        print("⚠️ No trades being executed. Check:")
        print("  1. Are strategy thresholds too strict?")
        print("  2. Is PostgreSQL connection working?")
        print("  3. Is there enough dry_run_wallet balance?")
        print("  4. Check Railway logs for errors")
    
    if scans == 0:
        print("⚠️ No scans being logged. Check:")
        print("  1. Is scan_logger initialized in strategy?")
        print("  2. Check Railway logs for scan_logger errors")
        print("  3. Verify Supabase connection")
    
    if data < 70:
        print("⚠️ Data coverage issues. Check:")
        print("  1. Is data scheduler running?")
        print("  2. Are Polygon.io API limits being hit?")
        print("  3. Check data scheduler logs")

if __name__ == "__main__":
    print("🔍 FREQTRADE TRADING ENGINE HEALTH CHECK")
    print("="*60)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    check_system_health()
