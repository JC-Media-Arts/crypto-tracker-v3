#!/usr/bin/env python3
"""
Check if local Freqtrade is generating trades
"""

import sqlite3
import os
import time
from datetime import datetime

db_path = "freqtrade/tradesv3.dryrun.sqlite"

print("🔍 CHECKING LOCAL FREQTRADE TRADES")
print("="*50)

if not os.path.exists(db_path):
    print(f"❌ Database not found: {db_path}")
    print("   Make sure Freqtrade is running!")
    exit(1)

# Connect to SQLite database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check for trades
cursor.execute("SELECT COUNT(*) FROM trades")
total_trades = cursor.fetchone()[0]
print(f"Total trades in database: {total_trades}")

# Get recent trades
cursor.execute("""
    SELECT pair, amount, stake_amount, open_rate, 
           open_date, close_date, close_rate, close_profit_abs,
           is_open, strategy
    FROM trades 
    ORDER BY open_date DESC 
    LIMIT 10
""")

trades = cursor.fetchall()

if trades:
    print(f"\n✅ FOUND {len(trades)} RECENT TRADES!")
    print("-"*50)
    for trade in trades:
        pair, amount, stake, open_rate, open_date, close_date, close_rate, profit, is_open, strategy = trade
        status = "🟢 OPEN" if is_open else "🔴 CLOSED"
        print(f"\n{pair} - {status}")
        print(f"  Strategy: {strategy}")
        print(f"  Amount: {amount:.4f}")
        print(f"  Stake: ${stake:.2f}")
        print(f"  Open: ${open_rate:.4f} at {open_date}")
        if not is_open:
            print(f"  Close: ${close_rate:.4f} at {close_date}")
            print(f"  Profit: ${profit:.2f}")
else:
    print("\n❌ No trades found yet")
    print("\nPossible reasons:")
    print("1. Strategy thresholds still too strict")
    print("2. Not enough time has passed (wait 2-3 minutes)")
    print("3. No data being received from exchange")
    
    # Check orders table
    cursor.execute("SELECT COUNT(*) FROM orders")
    order_count = cursor.fetchone()[0]
    print(f"\nOrders in database: {order_count}")

conn.close()

print("\n" + "="*50)
print("NEXT STEPS:")
print("="*50)

if total_trades > 0:
    print("✅ Trades are executing! Ready to deploy to Railway.")
    print("\nCommands to deploy:")
    print("  git add -A")
    print("  git commit -m 'Fix: Use SimpleChannelStrategy in start.sh'")
    print("  git push origin main")
else:
    print("⚠️  No trades yet. Options:")
    print("1. Wait another 2-3 minutes")
    print("2. Loosen thresholds even more (set to 0.80 or 0.90)")
    print("3. Try UltraSimpleRSI strategy (RSI < 40)")
    print("\nTo check Freqtrade status:")
    print("  ps aux | grep freqtrade")
    print("\nTo see logs:")
    print("  tail -f freqtrade/user_data/logs/freqtrade.log")
