#!/usr/bin/env python3
"""
Real-time Paper Trading Monitor
Shows current positions, recent trades, and performance metrics
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich import box
from loguru import logger

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.trading.simple_paper_trader_v2 import SimplePaperTraderV2
from src.data.supabase_client import SupabaseClient

console = Console()


class PaperTradingMonitor:
    """Monitor paper trading performance in real-time"""

    def __init__(self):
        # Initialize paper trader to load state
        self.paper_trader = SimplePaperTraderV2(
            initial_balance=1000.0, max_positions=30
        )

        # Database client
        self.db_client = None
        try:
            self.db_client = SupabaseClient()
        except:
            logger.warning("Could not connect to database")

    def create_layout(self) -> Layout:
        """Create the dashboard layout"""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="stats", size=8),
            Layout(name="main"),
            Layout(name="footer", size=3),
        )

        layout["main"].split_row(Layout(name="positions"), Layout(name="trades"))

        return layout

    def get_header(self) -> Panel:
        """Create header panel"""
        return Panel(
            Text("📊 PAPER TRADING MONITOR", justify="center", style="bold cyan"),
            border_style="cyan",
        )

    def get_footer(self) -> Panel:
        """Create footer panel"""
        return Panel(
            Text(
                f"Last updated: {datetime.now().strftime('%H:%M:%S')} | Press Ctrl+C to exit",
                justify="center",
                style="dim",
            ),
            border_style="dim",
        )

    def get_stats_panel(self) -> Panel:
        """Create statistics panel"""
        stats = self.paper_trader.get_portfolio_stats()

        # Determine colors
        pnl_color = "green" if stats["total_pnl"] >= 0 else "red"
        win_rate_color = (
            "green"
            if stats["win_rate"] >= 50
            else "yellow"
            if stats["win_rate"] >= 40
            else "red"
        )

        # Create stats table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")

        # Row 1
        table.add_row(
            "💰 Balance",
            f"${stats['balance']:.2f}",
            "📈 Total Value",
            f"${stats['total_value']:.2f}",
        )

        # Row 2
        table.add_row(
            "📊 Positions",
            f"{stats['positions']}/{stats['max_positions']}",
            "💵 Position Value",
            f"${stats['positions_value']:.2f}",
        )

        # Row 3
        table.add_row(
            "💹 Total P&L",
            Text(
                f"${stats['total_pnl']:+.2f} ({stats['total_pnl_pct']:+.2f}%)",
                style=pnl_color,
            ),
            "🎯 Win Rate",
            Text(f"{stats['win_rate']:.1f}%", style=win_rate_color),
        )

        # Row 4
        table.add_row(
            "🔄 Total Trades",
            str(stats["total_trades"]),
            "✅ Winning Trades",
            str(stats["winning_trades"]),
        )

        # Row 5
        table.add_row(
            "💸 Fees Paid",
            f"${stats['total_fees']:.2f}",
            "📉 Slippage",
            f"${stats['total_slippage']:.2f}",
        )

        return Panel(table, title="📊 Portfolio Statistics", border_style="blue")

    def get_positions_table(self) -> Panel:
        """Create open positions table"""
        table = Table(
            title="🔓 Open Positions",
            show_header=True,
            header_style="bold magenta",
            box=box.SIMPLE,
        )

        table.add_column("Symbol", style="yellow", width=8)
        table.add_column("Entry", justify="right", width=10)
        table.add_column("Current", justify="right", width=10)
        table.add_column("P&L %", justify="right", width=8)
        table.add_column("Value", justify="right", width=10)
        table.add_column("Strategy", width=8)
        table.add_column("Duration", width=8)

        if self.paper_trader.positions:
            # Sort by P&L
            sorted_positions = sorted(
                self.paper_trader.positions.items(),
                key=lambda x: x[1].entry_price,
                reverse=True,
            )

            for symbol, position in sorted_positions:
                # Calculate current P&L (estimate)
                current_price = position.entry_price  # Would need real price
                pnl_pct = 0.0  # Placeholder

                # Duration
                duration = datetime.now() - position.entry_time
                hours = duration.total_seconds() / 3600
                duration_str = f"{hours:.1f}h"

                # P&L color
                pnl_style = (
                    "green" if pnl_pct > 0 else "red" if pnl_pct < 0 else "white"
                )

                table.add_row(
                    symbol,
                    f"${position.entry_price:.4f}",
                    f"${current_price:.4f}",
                    Text(f"{pnl_pct:+.2f}%", style=pnl_style),
                    f"${position.usd_value:.2f}",
                    position.strategy.upper(),
                    duration_str,
                )
        else:
            table.add_row("No open positions", "", "", "", "", "", "")

        return Panel(table, border_style="green")

    def get_trades_table(self) -> Panel:
        """Create recent trades table"""
        table = Table(
            title="📜 Recent Trades",
            show_header=True,
            header_style="bold cyan",
            box=box.SIMPLE,
        )

        table.add_column("Time", width=8)
        table.add_column("Symbol", style="yellow", width=8)
        table.add_column("P&L", justify="right", width=10)
        table.add_column("P&L %", justify="right", width=8)
        table.add_column("Strategy", width=8)
        table.add_column("Exit", width=12)

        # Load trades from file
        trades_file = Path("data/paper_trading_trades.json")
        if trades_file.exists():
            try:
                with open(trades_file, "r") as f:
                    trades_data = json.load(f)

                # Show last 10 trades
                for trade in trades_data[-10:]:
                    exit_time = datetime.fromisoformat(trade["exit_time"])
                    time_str = exit_time.strftime("%H:%M")

                    # P&L color
                    pnl = trade["pnl_usd"]
                    pnl_pct = trade["pnl_percent"]
                    pnl_style = "green" if pnl > 0 else "red"

                    # Exit reason formatting
                    exit_map = {
                        "stop_loss": "🛑 Stop",
                        "take_profit": "🎯 Target",
                        "trailing_stop": "📉 Trail",
                        "time_exit": "⏰ Timeout",
                        "manual": "👤 Manual",
                    }
                    exit_display = exit_map.get(
                        trade["exit_reason"], trade["exit_reason"]
                    )

                    table.add_row(
                        time_str,
                        trade["symbol"],
                        Text(f"${pnl:+.2f}", style=pnl_style),
                        Text(f"{pnl_pct:+.2f}%", style=pnl_style),
                        trade["strategy"].upper(),
                        exit_display,
                    )
            except:
                pass

        if not table.rows:
            table.add_row("No trades yet", "", "", "", "", "")

        return Panel(table, border_style="cyan")

    def get_db_stats(self) -> Dict:
        """Get stats from database if available"""
        if not self.db_client:
            return {}

        try:
            # Get today's trades
            today = datetime.now().date().isoformat()
            result = (
                self.db_client.client.table("paper_trades")
                .select("*")
                .gte("created_at", today)
                .execute()
            )

            if result.data:
                return {
                    "today_trades": len(result.data),
                    "today_buys": sum(1 for t in result.data if t.get("side") == "BUY"),
                    "today_sells": sum(
                        1 for t in result.data if t.get("side") == "SELL"
                    ),
                }
        except:
            pass

        return {}

    async def run(self):
        """Main monitoring loop"""
        layout = self.create_layout()

        with Live(layout, refresh_per_second=0.5, screen=True) as live:
            while True:
                try:
                    # Reload state to get latest data
                    self.paper_trader.load_state()

                    # Update all panels
                    layout["header"].update(self.get_header())
                    layout["stats"].update(self.get_stats_panel())
                    layout["positions"].update(self.get_positions_table())
                    layout["trades"].update(self.get_trades_table())
                    layout["footer"].update(self.get_footer())

                    # Wait before next update
                    await asyncio.sleep(5)

                except KeyboardInterrupt:
                    break
                except Exception as e:
                    console.print(f"[red]Error: {e}[/red]")
                    await asyncio.sleep(5)


async def main():
    """Main entry point"""
    monitor = PaperTradingMonitor()
    await monitor.run()


if __name__ == "__main__":
    console.print("[bold cyan]Starting Paper Trading Monitor...[/bold cyan]")
    console.print("[dim]Press Ctrl+C to exit[/dim]\n")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitor stopped[/yellow]")
        sys.exit(0)
