#!/usr/bin/env python3
"""
Compare balance and P&L calculations between dashboard and paper trading engine
"""

import os
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data.supabase_client import SupabaseClient
from loguru import logger

load_dotenv()


def calculate_dashboard_style():
    """Calculate balance the way the dashboard does it"""
    db = SupabaseClient()
    
    STARTING_CAPITAL = 10000.0
    
    # Get all paper trades
    all_trades = (
        db.client.table("paper_trades")
        .select("*")
        .order("created_at", desc=False)
        .execute()
    ).data
    
    if not all_trades:
        return {
            "method": "Dashboard Style",
            "starting_capital": STARTING_CAPITAL,
            "realized_pnl": 0,
            "unrealized_pnl": 0,
            "current_balance": STARTING_CAPITAL,
            "open_positions": 0,
            "closed_positions": 0
        }
    
    # Get current prices
    symbols = list(set(trade["symbol"] for trade in all_trades if trade["symbol"]))
    current_prices = {}
    
    for symbol in symbols:
        try:
            price_result = (
                db.client.table("ohlc_data")
                .select("close")
                .eq("symbol", symbol)
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )
            if price_result.data:
                current_prices[symbol] = float(price_result.data[0]["close"])
        except:
            pass
    
    # Group trades by trade_group_id
    trades_by_group = {}
    for trade in all_trades:
        group_id = trade.get("trade_group_id")
        if group_id:
            if group_id not in trades_by_group:
                trades_by_group[group_id] = {
                    "buys": [],
                    "sells": [],
                    "symbol": trade["symbol"]
                }
            if trade["side"] == "BUY":
                trades_by_group[group_id]["buys"].append(trade)
            else:
                trades_by_group[group_id]["sells"].append(trade)
    
    # Calculate P&L
    realized_pnl = 0
    unrealized_pnl = 0
    open_count = 0
    closed_count = 0
    
    for group_id, group_data in trades_by_group.items():
        if group_data["buys"]:
            # Calculate total cost and amount
            total_cost = 0
            total_amount = 0
            
            for buy in group_data["buys"]:
                price = float(buy.get("price", 0))
                amount = float(buy.get("amount", 0))
                total_cost += price * amount
                total_amount += amount
            
            avg_entry_price = total_cost / total_amount if total_amount > 0 else 0
            
            if group_data["sells"]:
                # Closed position - calculate realized P&L
                exit_trade = group_data["sells"][-1]
                exit_price = float(exit_trade["price"])
                pnl = (exit_price - avg_entry_price) * total_amount
                realized_pnl += pnl
                closed_count += 1
            else:
                # Open position - calculate unrealized P&L
                symbol = group_data["symbol"]
                current_price = current_prices.get(symbol, avg_entry_price)
                unrealized = (current_price - avg_entry_price) * total_amount
                unrealized_pnl += unrealized
                open_count += 1
    
    # Dashboard calculation: balance = starting + realized + unrealized
    current_balance = STARTING_CAPITAL + realized_pnl + unrealized_pnl
    
    return {
        "method": "Dashboard Style",
        "starting_capital": STARTING_CAPITAL,
        "realized_pnl": realized_pnl,
        "unrealized_pnl": unrealized_pnl,
        "current_balance": current_balance,
        "open_positions": open_count,
        "closed_positions": closed_count
    }


def calculate_engine_style():
    """Calculate balance the way the paper trading engine does it"""
    db = SupabaseClient()
    
    INITIAL_BALANCE = 10000.0
    
    # Get all paper trades
    all_trades = (
        db.client.table("paper_trades")
        .select("*")
        .order("created_at", desc=False)
        .execute()
    ).data
    
    if not all_trades:
        return {
            "method": "Engine Style",
            "initial_balance": INITIAL_BALANCE,
            "cash_balance": INITIAL_BALANCE,
            "positions_value": 0,
            "total_value": INITIAL_BALANCE,
            "total_pnl": 0,
            "open_positions": 0
        }
    
    # Group trades
    trades_by_group = {}
    for trade in all_trades:
        group_id = trade.get("trade_group_id")
        if group_id:
            if group_id not in trades_by_group:
                trades_by_group[group_id] = {"buys": [], "sells": []}
            if trade["side"] == "BUY":
                trades_by_group[group_id]["buys"].append(trade)
            else:
                trades_by_group[group_id]["sells"].append(trade)
    
    # Calculate cash balance from closed trades only
    cash_balance = INITIAL_BALANCE
    positions_value = 0
    open_positions = {}
    
    # Get current prices for open positions
    symbols = list(set(
        trade["symbol"] for trade in all_trades 
        if trade["symbol"] and trade.get("trade_group_id") in [
            gid for gid, g in trades_by_group.items() if g["buys"] and not g["sells"]
        ]
    ))
    
    current_prices = {}
    for symbol in symbols:
        try:
            price_result = (
                db.client.table("ohlc_data")
                .select("close")
                .eq("symbol", symbol)
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )
            if price_result.data:
                current_prices[symbol] = float(price_result.data[0]["close"])
        except:
            pass
    
    for group_id, group_data in trades_by_group.items():
        if group_data["buys"]:
            # Calculate entry
            total_cost = 0
            total_amount = 0
            symbol = group_data["buys"][0]["symbol"]
            
            for buy in group_data["buys"]:
                price = float(buy.get("price", 0))
                amount = float(buy.get("amount", 0))
                fees = float(buy.get("fees", 0))
                total_cost += (price * amount) + fees
                total_amount += amount
                cash_balance -= (price * amount) + fees  # Deduct from cash
            
            if group_data["sells"]:
                # Closed position - add exit value back to cash
                for sell in group_data["sells"]:
                    exit_price = float(sell["price"])
                    exit_amount = float(sell["amount"])
                    exit_fees = float(sell.get("fees", 0))
                    cash_balance += (exit_price * exit_amount) - exit_fees
            else:
                # Open position - calculate current value
                current_price = current_prices.get(symbol, 0)
                if current_price > 0:
                    positions_value += current_price * total_amount
                    open_positions[symbol] = {
                        "amount": total_amount,
                        "current_price": current_price,
                        "value": current_price * total_amount
                    }
    
    # Engine calculation: total_value = cash_balance + positions_value
    total_value = cash_balance + positions_value
    total_pnl = total_value - INITIAL_BALANCE
    
    return {
        "method": "Engine Style",
        "initial_balance": INITIAL_BALANCE,
        "cash_balance": cash_balance,
        "positions_value": positions_value,
        "total_value": total_value,
        "total_pnl": total_pnl,
        "open_positions": len(open_positions),
        "position_details": open_positions
    }


def main():
    """Compare the two calculation methods"""
    
    print("\n" + "="*60)
    print("BALANCE CALCULATION COMPARISON")
    print("="*60)
    
    # Dashboard method
    dashboard = calculate_dashboard_style()
    print(f"\n📊 DASHBOARD METHOD:")
    print(f"   Starting Capital: ${dashboard['starting_capital']:,.2f}")
    print(f"   Realized P&L:     ${dashboard['realized_pnl']:,.2f}")
    print(f"   Unrealized P&L:   ${dashboard['unrealized_pnl']:,.2f}")
    print(f"   ➜ Current Balance: ${dashboard['current_balance']:,.2f}")
    print(f"   Open Positions:   {dashboard['open_positions']}")
    print(f"   Closed Positions: {dashboard['closed_positions']}")
    
    # Engine method
    engine = calculate_engine_style()
    print(f"\n⚙️  ENGINE METHOD:")
    print(f"   Initial Balance:  ${engine['initial_balance']:,.2f}")
    print(f"   Cash Balance:     ${engine['cash_balance']:,.2f}")
    print(f"   Positions Value:  ${engine['positions_value']:,.2f}")
    print(f"   ➜ Total Value:    ${engine['total_value']:,.2f}")
    print(f"   Total P&L:        ${engine['total_pnl']:,.2f}")
    print(f"   Open Positions:   {engine['open_positions']}")
    
    # Compare
    print("\n" + "="*60)
    print("COMPARISON:")
    print("="*60)
    
    dashboard_balance = dashboard['current_balance']
    engine_balance = engine['total_value']
    difference = abs(dashboard_balance - engine_balance)
    
    if difference < 0.01:
        print(f"✅ BALANCES MATCH! Both show: ${dashboard_balance:,.2f}")
    else:
        print(f"⚠️  BALANCE MISMATCH:")
        print(f"   Dashboard shows: ${dashboard_balance:,.2f}")
        print(f"   Engine shows:    ${engine_balance:,.2f}")
        print(f"   Difference:      ${difference:,.2f}")
    
    # Check what the engine is currently reporting
    print("\n" + "="*60)
    print("CURRENT ENGINE STATE (from last log):")
    print("="*60)
    print("According to your last log, the engine reported:")
    print("   Balance: $10,907.18")
    print("   Positions: 0")
    print("   P&L: $907.18")
    
    if abs(engine['total_value'] - 10907.18) < 1:
        print("✅ This matches our calculated engine value!")
    else:
        print(f"⚠️  This doesn't match our calculation of ${engine['total_value']:,.2f}")
    
    # Show position details if any
    if engine.get('position_details'):
        print("\n" + "="*60)
        print("OPEN POSITION DETAILS:")
        print("="*60)
        for symbol, details in engine['position_details'].items():
            print(f"   {symbol}: {details['amount']:.4f} @ ${details['current_price']:.4f} = ${details['value']:,.2f}")


if __name__ == "__main__":
    main()
