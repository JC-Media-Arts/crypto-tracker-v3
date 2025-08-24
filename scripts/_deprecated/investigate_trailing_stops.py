#!/usr/bin/env python3
"""
Investigate why trailing stops are resulting in losses
"""

from src.data.supabase_client import SupabaseClient


def main():
    db = SupabaseClient()

    print("=== INVESTIGATING TRAILING STOP LOSSES ===\n")

    # Get CHANNEL trades that exited via trailing_stop
    trades = (
        db.client.table("paper_trades")
        .select("*")
        .eq("strategy_name", "CHANNEL")
        .eq("side", "SELL")
        .eq("exit_reason", "trailing_stop")
        .execute()
    )

    if trades.data:
        print(f"Found {len(trades.data)} CHANNEL trades with trailing_stop exits\n")

        # Separate wins and losses
        losses = [t for t in trades.data if t.get("pnl", 0) < 0]
        wins = [t for t in trades.data if t.get("pnl", 0) > 0]

        print(f"Results:")
        print(f"  - LOSSES: {len(losses)} trades")
        print(f"  - WINS: {len(wins)} trades")
        print(f"  - Loss Rate: {(len(losses)/len(trades.data))*100:.1f}%\n")

        if losses:
            print('Sample LOSING trades with "trailing_stop" exit (first 5):')
            print("-" * 80)
            for i, trade in enumerate(losses[:5], 1):
                print(f"\nTrade {i}:")
                print(f'  Symbol: {trade.get("symbol")}')
                print(f'  Entry Price: ${trade.get("price", 0):.6f}')

                # Try to find exit price
                exit_price = trade.get("exit_price", 0)
                if (
                    not exit_price
                    and trade.get("price")
                    and trade.get("pnl")
                    and trade.get("amount")
                ):
                    # Calculate exit price from PnL
                    exit_price = trade["price"] + (trade["pnl"] / trade["amount"])

                if exit_price:
                    print(f"  Exit Price: ${exit_price:.6f}")
                    price_change = (
                        (exit_price - trade.get("price", 0)) / trade.get("price", 1)
                    ) * 100
                    print(f"  Price Change: {price_change:.2f}%")

                print(f'  PnL: ${trade.get("pnl", 0):.2f}')
                print(f'  Amount: {trade.get("amount", 0):.4f}')
                print(f'  Created: {trade.get("created_at", "")[:19]}')
                print(f'  Filled: {trade.get("filled_at", "")[:19]}')

        print("\n" + "=" * 80)
        print("DIAGNOSIS:")
        print("=" * 80)

        if len(losses) > len(wins):
            print("❌ PROBLEM CONFIRMED: Trailing stops are causing losses!")
            print(
                "\nThis is NOT normal behavior. Trailing stops should only trigger on profitable trades."
            )
            print("\nPOSSIBLE CAUSES:")
            print(
                '1. **Most Likely**: The "trailing_stop" label is incorrectly applied to regular stop losses'
            )
            print(
                "2. Trailing stop is activating immediately at entry (configuration issue)"
            )
            print("3. Fees are so high that profitable exits become losses")
            print("4. Bug in the paper trading engine exit logic")

            print("\nNEXT STEPS:")
            print("1. Check the CHANNEL strategy code to see how stops are configured")
            print("2. Review SimplePaperTraderV2 to see how exit_reason is determined")
            print("3. Look at actual stop/target configuration for CHANNEL strategy")

    # Also check the actual strategy configuration
    print("\n" + "=" * 80)
    print("CHECKING STRATEGY CONFIGURATION:")
    print("=" * 80)

    # Look for CHANNEL strategy parameters
    import json
    import os

    config_file = "configs/paper_trading.json"
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            config = json.load(f)
            if "strategies" in config:
                for strat in config["strategies"]:
                    if strat.get("name") == "CHANNEL":
                        print("\nCHANNEL Strategy Config:")
                        print(f'  Stop Loss: {strat.get("stop_loss_pct", "N/A")}%')
                        print(f'  Take Profit: {strat.get("take_profit_pct", "N/A")}%')
                        print(
                            f'  Trailing Stop: {strat.get("trailing_stop_pct", "N/A")}%'
                        )
                        print(
                            f'  Use Trailing: {strat.get("use_trailing_stop", "N/A")}'
                        )


if __name__ == "__main__":
    main()
