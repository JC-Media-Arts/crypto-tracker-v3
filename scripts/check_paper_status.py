#!/usr/bin/env python3
"""Check paper trading status"""

import json
from pathlib import Path
from datetime import datetime

# Check state file
state_file = Path("data/paper_trading_state.json")
trades_file = Path("data/paper_trading_trades.json")

print("=" * 60)
print("📊 PAPER TRADING STATUS CHECK")
print("=" * 60)

if state_file.exists():
    with open(state_file) as f:
        state = json.load(f)

    print(f"\n💰 Account Status:")
    print(f"   Balance: ${state['balance']:.2f}")
    print(f"   Initial: ${state['initial_balance']:.2f}")
    print(f"   P&L: ${state['balance'] - state['initial_balance']:.2f}")

    print(f"\n📈 Open Positions: {len(state['positions'])}")
    for symbol, pos in state["positions"].items():
        print(f"   {symbol}: ${pos['usd_value']:.2f} @ ${pos['entry_price']:.4f}")

    stats = state.get("stats", {})
    print(f"\n📊 Trading Stats:")
    print(f"   Total Trades: {stats.get('total_trades', 0)}")
    print(f"   Winning Trades: {stats.get('winning_trades', 0)}")
    print(f"   Total Fees: ${stats.get('total_fees', 0):.2f}")
    print(f"   Total Slippage: ${stats.get('total_slippage', 0):.2f}")
else:
    print("❌ No state file found - paper trading may not have started yet")

if trades_file.exists():
    with open(trades_file) as f:
        trades = json.load(f)

    if trades:
        print(f"\n📜 Recent Trades: {len(trades)} total")
        for trade in trades[-3:]:  # Last 3 trades
            emoji = "🟢" if trade["pnl_usd"] > 0 else "🔴"
            print(f"   {emoji} {trade['symbol']}: ${trade['pnl_usd']:.2f} ({trade['pnl_percent']:.2f}%)")

print("\n" + "=" * 60)
