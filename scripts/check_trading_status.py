#!/usr/bin/env python3
"""Check current trading status and open positions."""

import os
import json
from datetime import datetime, timezone, timedelta
from supabase import create_client

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
client = create_client(supabase_url, supabase_key)

# Get all trades
response = client.table('paper_trades').select('*').execute()
all_trades = response.data

# Find trade groups with sells
groups_with_sells = set()
buy_trades = []
for trade in all_trades:
    if trade['side'] == 'SELL' and trade['trade_group_id']:
        groups_with_sells.add(trade['trade_group_id'])
    elif trade['side'] == 'BUY':
        buy_trades.append(trade)

# Count truly open positions
open_positions = []
for trade in buy_trades:
    if trade.get('trade_group_id') and trade['trade_group_id'] not in groups_with_sells:
        open_positions.append(trade)

print(f"Total open positions: {len(open_positions)}")

# Group by strategy
strategies = {}
for pos in open_positions:
    strategy = pos.get('strategy_name', 'UNKNOWN')
    if strategy not in strategies:
        strategies[strategy] = []
    strategies[strategy].append(pos)

print("\nOpen positions by strategy:")
for strategy, positions in strategies.items():
    print(f"  {strategy}: {len(positions)}")

# Check recent trades
response = client.table('paper_trades').select('*').order('created_at', desc=True).limit(20).execute()
recent = response.data

if recent:
    print(f"\nMost recent trade: {recent[0]['created_at']} - {recent[0]['side']} {recent[0]['symbol']}")
    
    # Find last BUY trade
    for trade in recent:
        if trade['side'] == 'BUY':
            print(f"Last BUY trade: {trade['created_at']} - {trade['symbol']} ({trade.get('strategy_name', 'N/A')})")
            # Calculate how long ago
            trade_time = datetime.fromisoformat(trade['created_at'].replace('Z', '+00:00'))
            time_ago = datetime.now(timezone.utc) - trade_time
            print(f"  Time since last BUY: {time_ago.days} days, {time_ago.seconds // 3600} hours ago")
            break

# Check recent scan history
print("\n=== Recent Scan Activity ===")
response = client.table('scan_history').select('*').order('timestamp', desc=True).limit(10).execute()
scans = response.data
if scans:
    print(f"Latest scan: {scans[0]['timestamp']}")
    scan_time = datetime.fromisoformat(scans[0]['timestamp'].replace('Z', '+00:00'))
    time_ago = datetime.now(timezone.utc) - scan_time
    print(f"  Time since last scan: {time_ago.total_seconds() / 60:.1f} minutes ago")
    
    # Count decisions
    decisions = {}
    for scan in scans:
        decision = scan.get('decision', 'UNKNOWN')
        if decision not in decisions:
            decisions[decision] = 0
        decisions[decision] += 1
    print(f"  Recent decisions: {decisions}")

# Check balance
print("\n=== Portfolio Status ===")
response = client.table('paper_performance').select('*').order('timestamp', desc=True).limit(1).execute()
if response.data:
    perf = response.data[0]
    print(f"Current balance: ${perf.get('current_balance', 'N/A')}")
    print(f"Total P&L: ${perf.get('total_pnl', 'N/A')}")
