#!/usr/bin/env python3
"""
Save existing paper trading positions and trades to database
"""

import json
from datetime import datetime
from pathlib import Path
from src.data.supabase_client import SupabaseClient
from loguru import logger


def save_trades_to_db():
    """Save existing trades to database"""

    try:
        # Initialize database client
        db = SupabaseClient()

        # Load state file
        state_file = Path("data/paper_trading_state.json")
        if state_file.exists():
            with open(state_file, "r") as f:
                state = json.load(f)

            # Save open positions
            for symbol, position in state.get("positions", {}).items():
                try:
                    # Check if already exists
                    existing = (
                        db.client.table("paper_trades")
                        .select("*")
                        .eq("symbol", symbol)
                        .eq("status", "FILLED")
                        .eq("trading_engine", "simple_paper_trader")
                        .execute()
                    )

                    if not existing.data:
                        # Save open position
                        data = {
                            "trading_engine": "simple_paper_trader",
                            "symbol": symbol,
                            "side": "BUY",
                            "order_type": "MARKET",
                            "price": position["entry_price"],
                            "amount": position["amount"],
                            "status": "FILLED",
                            "created_at": position["entry_time"],
                            "filled_at": position["entry_time"],
                            "strategy_name": position["strategy"],
                            "fees": position.get("fees_paid", 0),
                            "stop_loss": position.get("stop_loss"),
                            "take_profit": position.get("take_profit"),
                        }

                        result = db.client.table("paper_trades").insert(data).execute()
                        logger.info(f"✅ Saved open position to DB: {symbol}")
                    else:
                        logger.info(f"Position already in DB: {symbol}")

                except Exception as e:
                    logger.error(f"Failed to save position {symbol}: {e}")

        # Load completed trades file
        trades_file = Path("data/paper_trading_trades.json")
        if trades_file.exists():
            with open(trades_file, "r") as f:
                trades = json.load(f)

            for trade in trades:
                try:
                    # Check if already exists
                    existing = (
                        db.client.table("paper_trades")
                        .select("*")
                        .eq("symbol", trade["symbol"])
                        .eq("side", "SELL")
                        .eq("trading_engine", "simple_paper_trader")
                        .execute()
                    )

                    if not existing.data:
                        # Save entry (BUY)
                        entry_data = {
                            "trading_engine": "simple_paper_trader",
                            "symbol": trade["symbol"],
                            "side": "BUY",
                            "order_type": "MARKET",
                            "price": trade["entry_price"],
                            "amount": trade["amount"],
                            "status": "FILLED",
                            "created_at": trade["entry_time"],
                            "filled_at": trade["entry_time"],
                            "strategy_name": trade["strategy"],
                            "fees": trade["fees_paid"] / 2,  # Split fees between entry and exit
                        }

                        db.client.table("paper_trades").insert(entry_data).execute()

                        # Save exit (SELL)
                        exit_data = {
                            "trading_engine": "simple_paper_trader",
                            "symbol": trade["symbol"],
                            "side": "SELL",
                            "order_type": "MARKET",
                            "price": trade["exit_price"],
                            "amount": trade["amount"],
                            "status": "CLOSED",
                            "created_at": trade["entry_time"],
                            "filled_at": trade["exit_time"],
                            "strategy_name": trade["strategy"],
                            "fees": trade["fees_paid"] / 2,
                            "pnl": trade["pnl_usd"]
                            # Note: exit_reason column might not exist yet
                        }

                        # Try to add exit_reason if column exists
                        try:
                            exit_data["exit_reason"] = trade.get("exit_reason", "unknown")
                        except:
                            pass

                        db.client.table("paper_trades").insert(exit_data).execute()
                        logger.info(f"✅ Saved completed trade to DB: {trade['symbol']} (P&L: ${trade['pnl_usd']:.2f})")
                    else:
                        logger.info(f"Trade already in DB: {trade['symbol']}")

                except Exception as e:
                    logger.error(f"Failed to save trade {trade['symbol']}: {e}")

        # Update daily performance
        try:
            # Get today's date
            today = datetime.now().date().isoformat()

            # Calculate totals from state
            total_trades = state.get("stats", {}).get("total_trades", 0)
            winning_trades = state.get("stats", {}).get("winning_trades", 0)

            # Calculate P&L
            initial_balance = state.get("initial_balance", 1000)
            current_balance = state.get("balance", 1000)
            positions_value = sum(p["usd_value"] for p in state.get("positions", {}).values())
            total_pnl = (current_balance + positions_value) - initial_balance

            # Check if record exists
            existing = (
                db.client.table("paper_performance")
                .select("*")
                .eq("date", today)
                .eq("trading_engine", "simple_paper_trader")
                .execute()
            )

            if not existing.data:
                # Create new record
                perf_data = {
                    "date": today,
                    "strategy_name": "MIXED",  # Multiple strategies
                    "trading_engine": "simple_paper_trader",
                    "trades_count": total_trades,
                    "wins": winning_trades,
                    "losses": total_trades - winning_trades,
                    "net_pnl": total_pnl,
                    "setups_detected": 0,  # Will be updated by strategy scanner
                    "setups_taken": total_trades,
                    "ml_accuracy": 0.0,  # Not using ML
                }

                db.client.table("paper_performance").insert(perf_data).execute()
                logger.info(f"✅ Saved daily performance to DB: P&L ${total_pnl:.2f}")
            else:
                # Update existing
                perf_data = {
                    "trades_count": total_trades,
                    "wins": winning_trades,
                    "losses": total_trades - winning_trades,
                    "net_pnl": total_pnl,
                    "setups_taken": total_trades,
                }

                db.client.table("paper_performance").update(perf_data).eq("date", today).eq(
                    "trading_engine", "simple_paper_trader"
                ).execute()
                logger.info(f"✅ Updated daily performance in DB: P&L ${total_pnl:.2f}")

        except Exception as e:
            logger.error(f"Failed to update daily performance: {e}")

        logger.info("✅ Database sync complete!")

    except Exception as e:
        logger.error(f"Database sync failed: {e}")


if __name__ == "__main__":
    save_trades_to_db()
