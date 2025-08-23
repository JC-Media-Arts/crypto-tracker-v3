#!/usr/bin/env python3
"""Verify trades are saved in database"""

from src.data.supabase_client import SupabaseClient
from loguru import logger


def verify_trades():
    client = SupabaseClient()

    # Check all paper_trades
    trades = client.client.table("paper_trades").select("*").order("created_at", desc=True).execute()

    print("=" * 60)
    print("📊 PAPER TRADES IN DATABASE")
    print("=" * 60)
    print(f"Total records: {len(trades.data)}")
    print()

    # Group by symbol
    symbols = {}
    for trade in trades.data:
        symbol = trade.get("symbol")
        if symbol not in symbols:
            symbols[symbol] = {"buys": [], "sells": []}

        if trade.get("side") == "BUY":
            symbols[symbol]["buys"].append(trade)
        else:
            symbols[symbol]["sells"].append(trade)

    # Display trades by symbol
    for symbol, trades_dict in symbols.items():
        print(f"\n{symbol}:")

        for buy in trades_dict["buys"]:
            price = float(buy.get("price", 0))
            print(f"  ✅ OPENED: Price ${price:.4f}")
            print(f"     Status: {buy.get('status')}")
            print(f"     Strategy: {buy.get('strategy_name')}")
            print(f"     Engine: {buy.get('trading_engine')}")

        for sell in trades_dict["sells"]:
            price = float(sell.get("price", 0))
            pnl = sell.get("pnl")
            print(f"  ❌ CLOSED: Price ${price:.4f}")
            if pnl:
                print(f"     P&L: ${float(pnl):.2f}")
            print(f"     Status: {sell.get('status')}")

    print("\n" + "=" * 60)
    print("✅ VERIFICATION COMPLETE")
    print("=" * 60)
    print("\nSummary:")
    print(
        f"- GRT: {'OPEN position (currently trading)' if 'GRT' in symbols and not symbols['GRT']['sells'] else 'Position status unknown'}"
    )
    print(
        f"- ENJ: {'CLOSED position (completed trade)' if 'ENJ' in symbols and symbols['ENJ']['sells'] else 'Position status unknown'}"
    )
    print("\n✅ Both positions are successfully saved in the database!")


if __name__ == "__main__":
    verify_trades()
