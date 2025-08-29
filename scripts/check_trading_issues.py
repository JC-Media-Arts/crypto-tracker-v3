#!/usr/bin/env python3
"""Investigate why no new trades are being opened."""

import os
from datetime import datetime, timezone, timedelta
from supabase import create_client
from dotenv import load_dotenv
import json

load_dotenv()
client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

print("=" * 60)
print("TRADING SYSTEM INVESTIGATION")
print("=" * 60)

# 1. Check recent scan history
recent_time = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
response = client.table('scan_history').select('*').gte('timestamp', recent_time).order('timestamp', desc=True).execute()
scans = response.data

# Count decisions
decisions = {}
strategies = {}
for scan in scans:
    decision = scan.get('decision', 'UNKNOWN')
    strategy = scan.get('strategy_name', 'UNKNOWN')
    
    if decision not in decisions:
        decisions[decision] = 0
    decisions[decision] += 1
    
    if strategy not in strategies:
        strategies[strategy] = {'TAKE': 0, 'SKIP': 0, 'NEAR_MISS': 0}
    if decision in strategies[strategy]:
        strategies[strategy][decision] += 1

print(f'\n1. RECENT SCAN ACTIVITY (last 6 hours):')
print(f'   Total scans: {len(scans)}')
print(f'   Decisions breakdown:')
for decision, count in sorted(decisions.items()):
    print(f'     {decision}: {count}')

print(f'\n   By Strategy:')
for strategy, counts in sorted(strategies.items()):
    print(f'     {strategy}: TAKE={counts["TAKE"]}, SKIP={counts["SKIP"]}, NEAR_MISS={counts["NEAR_MISS"]}')

# Check for any TAKE decisions
take_scans = [s for s in scans if s.get('decision') == 'TAKE']
if take_scans:
    print(f'\n   ⚠️ Found {len(take_scans)} TAKE decisions but no trades opened!')
    for i, scan in enumerate(take_scans[:5]):  # Show first 5
        print(f'      {i+1}. {scan["timestamp"]}: {scan["symbol"]} ({scan["strategy_name"]}) - Confidence: {scan.get("confidence", "N/A")}')

# 2. Check current balance and position limits
response = client.table('paper_trades').select('*').execute()
all_trades = response.data

# Calculate P&L
total_pnl = 0
for trade in all_trades:
    if trade['side'] == 'SELL' and trade['pnl'] is not None:
        total_pnl += float(trade['pnl'])

# Count open positions
groups_with_sells = set()
buy_trades = []
for trade in all_trades:
    if trade['side'] == 'SELL' and trade['trade_group_id']:
        groups_with_sells.add(trade['trade_group_id'])
    elif trade['side'] == 'BUY':
        buy_trades.append(trade)

open_positions = []
strategies_open = {}
for trade in buy_trades:
    if trade.get('trade_group_id') and trade['trade_group_id'] not in groups_with_sells:
        open_positions.append(trade)
        strategy = trade.get('strategy_name', 'UNKNOWN')
        if strategy not in strategies_open:
            strategies_open[strategy] = 0
        strategies_open[strategy] += 1

# Load config to check limits
config_path = '/Users/justincoit/crypto-tracker-v3/configs/paper_trading_config_unified.json'
with open(config_path, 'r') as f:
    config = json.load(f)

initial_balance = config['global_settings']['initial_balance']
max_total = config['position_management']['max_positions_total']
max_per_strategy = config['position_management']['max_positions_per_strategy']
position_size = config['position_management']['position_sizing']['base_position_size_usd']

current_balance = initial_balance + total_pnl
used_capital = len(open_positions) * position_size
available_balance = current_balance - used_capital

print(f'\n2. BALANCE & POSITION STATUS:')
print(f'   Initial balance: ${initial_balance:,.2f}')
print(f'   Total P&L: ${total_pnl:,.2f}')
print(f'   Current balance: ${current_balance:,.2f}')
print(f'   Used capital: ${used_capital:,.2f} ({len(open_positions)} positions × ${position_size})')
print(f'   Available balance: ${available_balance:,.2f}')

print(f'\n3. POSITION LIMITS:')
print(f'   Max total positions: {max_total}')
print(f'   Max per strategy: {max_per_strategy}')
print(f'   Current open positions: {len(open_positions)} / {max_total}')
print(f'   By strategy:')
for strategy in ['DCA', 'SWING', 'CHANNEL']:
    count = strategies_open.get(strategy, 0)
    status = "✅" if count < max_per_strategy else "❌ AT LIMIT"
    print(f'     {strategy}: {count} / {max_per_strategy} {status}')

# 4. Check if trading is enabled
trading_enabled = config['global_settings'].get('trading_enabled', False)
print(f'\n4. TRADING STATUS:')
print(f'   Trading enabled: {"✅ YES" if trading_enabled else "❌ NO"}')

# 5. Check confidence thresholds
ml_threshold = config['ml_confidence']['ml_confidence_threshold']
min_signal = config['ml_confidence']['min_signal_strength']

print(f'\n5. CONFIDENCE THRESHOLDS:')
print(f'   ML confidence threshold: {ml_threshold}')
print(f'   Min signal strength: {min_signal}')
print(f'   Strategy min confidence:')
for strategy in ['DCA', 'SWING', 'CHANNEL']:
    min_conf = config['strategies'][strategy]['min_confidence']
    print(f'     {strategy}: {min_conf}')

# 6. Diagnose the issue
print(f'\n6. DIAGNOSIS:')
issues = []

if not trading_enabled:
    issues.append("❌ Trading is DISABLED in config!")

if available_balance < position_size:
    issues.append(f"❌ Insufficient balance! Need ${position_size} but only have ${available_balance:.2f} available")

if len(open_positions) >= max_total:
    issues.append(f"❌ At total position limit ({max_total})")

for strategy in ['DCA', 'SWING', 'CHANNEL']:
    count = strategies_open.get(strategy, 0)
    if count >= max_per_strategy:
        issues.append(f"❌ {strategy} at position limit ({max_per_strategy})")

# Check if CHANNEL is dominating
if strategies_open.get('CHANNEL', 0) == len(open_positions) and len(open_positions) > 0:
    issues.append("⚠️ CHANNEL strategy has ALL positions - may be too aggressive")

# Check if confidence thresholds are too high
if ml_threshold > 0.6:
    issues.append(f"⚠️ ML confidence threshold might be too high ({ml_threshold})")

# Check strategy-specific thresholds
channel_threshold = config['strategies']['CHANNEL']['detection_thresholds']['channel_strength_min']
if channel_threshold > 0.85:
    issues.append(f"⚠️ CHANNEL strength requirement very high ({channel_threshold})")

if issues:
    for issue in issues:
        print(f"   {issue}")
else:
    print("   ✅ No obvious issues found - may need to check strategy detection thresholds")

# 7. Check recent errors in scan_history
error_scans = [s for s in scans if 'error' in str(s.get('metadata', '')).lower()]
if error_scans:
    print(f'\n7. RECENT ERRORS:')
    print(f'   Found {len(error_scans)} scans with errors')

print("\n" + "=" * 60)
