#!/usr/bin/env python3
"""
Shadow Testing Dashboard
Displays current shadow performance and recommendations
"""

import sys
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from loguru import logger
import pandas as pd

sys.path.append(".")

from src.data.supabase_client import SupabaseClient
from src.analysis.shadow_analyzer import ShadowAnalyzer
from src.config.shadow_config import ShadowConfig


class ShadowDashboard:
    """Interactive dashboard for shadow testing monitoring"""

    def __init__(self):
        self.console = Console()
        self.supabase = SupabaseClient()
        self.analyzer = ShadowAnalyzer(self.supabase.client)

    async def display_dashboard(self, refresh_interval: int = 60):
        """
        Display live updating dashboard

        Args:
            refresh_interval: Seconds between updates
        """
        with Live(self.generate_layout(), refresh=True, console=self.console) as live:
            while True:
                try:
                    layout = await self.generate_layout()
                    live.update(layout)
                    await asyncio.sleep(refresh_interval)
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    logger.error(f"Dashboard error: {e}")
                    await asyncio.sleep(10)

    async def generate_layout(self) -> Layout:
        """Generate the dashboard layout"""
        layout = Layout()

        # Create sections
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3),
        )

        # Split main into columns
        layout["main"].split_row(Layout(name="performance", ratio=2), Layout(name="recommendations", ratio=1))

        # Split performance into rows
        layout["performance"].split_column(Layout(name="champion_vs_challengers"), Layout(name="recent_outcomes"))

        # Populate sections
        layout["header"].update(self._create_header())
        layout["champion_vs_challengers"].update(await self._create_performance_table())
        layout["recent_outcomes"].update(await self._create_outcomes_table())
        layout["recommendations"].update(await self._create_recommendations_panel())
        layout["footer"].update(self._create_footer())

        return layout

    def _create_header(self) -> Panel:
        """Create header panel"""
        header_text = Text()
        header_text.append("🔬 Shadow Testing Dashboard\n", style="bold cyan")
        header_text.append(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", style="dim")

        return Panel(header_text, style="bold blue")

    async def _create_performance_table(self) -> Panel:
        """Create performance comparison table"""
        table = Table(
            title="Champion vs Challengers (7-day)",
            show_header=True,
            header_style="bold magenta",
        )

        # Add columns
        table.add_column("Variation", style="cyan", no_wrap=True)
        table.add_column("Strategy", style="white")
        table.add_column("Trades", justify="right", style="white")
        table.add_column("Win Rate", justify="right")
        table.add_column("Avg P&L", justify="right")
        table.add_column("vs Champion", justify="right")
        table.add_column("Confidence", justify="center")

        try:
            # Get performance data
            result = (
                self.supabase.client.table("shadow_performance")
                .select("*")
                .eq("timeframe", "7d")
                .order("outperformance_vs_champion", desc=True)
                .limit(10)
                .execute()
            )

            if result.data:
                for row in result.data:
                    # Color code based on performance
                    win_rate_color = "green" if row["win_rate"] > 0.5 else "red"
                    pnl_color = "green" if row["avg_pnl_percentage"] > 0 else "red"

                    # Outperformance color
                    outperf = row["outperformance_vs_champion"]
                    if outperf > 0.05:
                        outperf_color = "bold green"
                    elif outperf > 0:
                        outperf_color = "green"
                    elif outperf > -0.05:
                        outperf_color = "yellow"
                    else:
                        outperf_color = "red"

                    # Confidence color
                    conf_colors = {
                        "HIGH": "bold green",
                        "MEDIUM": "yellow",
                        "LOW": "dim white",
                    }
                    conf_color = conf_colors.get(row["confidence_level"], "white")

                    table.add_row(
                        row["variation_name"],
                        row["strategy_name"],
                        str(row["trades_completed"]),
                        f"[{win_rate_color}]{row['win_rate']:.1%}[/{win_rate_color}]",
                        f"[{pnl_color}]{row['avg_pnl_percentage']:.2f}%[/{pnl_color}]",
                        f"[{outperf_color}]{outperf:+.1%}[/{outperf_color}]",
                        f"[{conf_color}]{row['confidence_level']}[/{conf_color}]",
                    )
            else:
                table.add_row("No data", "-", "-", "-", "-", "-", "-")

        except Exception as e:
            logger.error(f"Error creating performance table: {e}")
            table.add_row("Error loading data", "-", "-", "-", "-", "-", "-")

        return Panel(table, title="Performance Comparison", border_style="blue")

    async def _create_outcomes_table(self) -> Panel:
        """Create recent outcomes table"""
        table = Table(
            title="Recent Shadow Outcomes (Last 24h)",
            show_header=True,
            header_style="bold magenta",
        )

        # Add columns
        table.add_column("Time", style="dim")
        table.add_column("Variation", style="cyan")
        table.add_column("Symbol", style="white")
        table.add_column("Strategy", style="white")
        table.add_column("Result", justify="center")
        table.add_column("P&L", justify="right")
        table.add_column("Hold Time", justify="right")

        try:
            # Get recent outcomes
            cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()

            result = (
                self.supabase.client.table("shadow_outcomes")
                .select("*, shadow_variations!inner(variation_name, scan_history!inner(symbol, strategy_name))")
                .gte("evaluated_at", cutoff)
                .order("evaluated_at", desc=True)
                .limit(15)
                .execute()
            )

            if result.data:
                for row in result.data:
                    # Parse nested data
                    variation = row["shadow_variations"]["variation_name"]
                    symbol = row["shadow_variations"]["scan_history"]["symbol"]
                    strategy = row["shadow_variations"]["scan_history"]["strategy_name"]

                    # Format time
                    eval_time = datetime.fromisoformat(row["evaluated_at"].replace("Z", "+00:00"))
                    time_str = eval_time.strftime("%H:%M")

                    # Color code result
                    if row["outcome_status"] == "WIN":
                        result_str = "[bold green]WIN[/bold green]"
                    elif row["outcome_status"] == "LOSS":
                        result_str = "[bold red]LOSS[/bold red]"
                    else:
                        result_str = f"[yellow]{row['outcome_status']}[/yellow]"

                    # Color code P&L
                    pnl = row["pnl_percentage"]
                    if pnl > 0:
                        pnl_str = f"[green]+{pnl:.1f}%[/green]"
                    else:
                        pnl_str = f"[red]{pnl:.1f}%[/red]"

                    table.add_row(
                        time_str,
                        variation,
                        symbol,
                        strategy,
                        result_str,
                        pnl_str,
                        f"{row['actual_hold_hours']:.1f}h",
                    )
            else:
                table.add_row("No recent outcomes", "-", "-", "-", "-", "-", "-")

        except Exception as e:
            logger.error(f"Error creating outcomes table: {e}")
            table.add_row("Error loading data", "-", "-", "-", "-", "-", "-")

        return Panel(table, title="Recent Outcomes", border_style="blue")

    async def _create_recommendations_panel(self) -> Panel:
        """Create recommendations panel"""
        try:
            # Get recommendations
            recommendations = await self.analyzer.generate_recommendations()

            if recommendations:
                text = Text()
                text.append("📊 Adjustment Recommendations\n\n", style="bold yellow")

                for i, rec in enumerate(recommendations[:3], 1):
                    # Confidence emoji
                    conf_emoji = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "⚪"}.get(rec.confidence_level, "⚪")

                    text.append(
                        f"{i}. {rec.strategy_name} - {rec.parameter_name}\n",
                        style="bold cyan",
                    )
                    text.append(
                        f"   {conf_emoji} Confidence: {rec.confidence_level}\n",
                        style="white",
                    )
                    text.append(f"   Current: {rec.current_value:.2f}\n", style="dim")
                    text.append(
                        f"   Recommended: {rec.recommended_value:.2f}\n",
                        style="bold green",
                    )
                    text.append(f"   Evidence: {rec.evidence_trades} trades\n", style="dim")
                    text.append(f"   Outperformance: {rec.outperformance:+.1%}\n", style="green")
                    text.append(f"   Source: {rec.variation_source}\n", style="dim cyan")
                    text.append(f"   Reason: {rec.reason}\n\n", style="italic")
            else:
                text = Text("No recommendations at this time.\n", style="dim")
                text.append("Gathering more evidence...", style="italic yellow")

            return Panel(text, title="Recommendations", border_style="yellow")

        except Exception as e:
            logger.error(f"Error creating recommendations: {e}")
            return Panel(
                "Error loading recommendations",
                title="Recommendations",
                border_style="red",
            )

    def _create_footer(self) -> Panel:
        """Create footer panel"""
        # Get active variations
        active_vars = ShadowConfig.get_active_variations()

        footer_text = Text()
        footer_text.append(f"Active Variations: {', '.join(active_vars)}\n", style="dim cyan")
        footer_text.append("Press Ctrl+C to exit", style="dim italic")

        return Panel(footer_text, style="dim blue")

    async def print_summary(self):
        """Print a one-time summary (non-interactive)"""
        self.console.print("\n[bold cyan]🔬 Shadow Testing Summary[/bold cyan]\n")

        # Performance summary
        performance_table = await self._create_performance_table()
        self.console.print(performance_table)

        # Recent outcomes
        outcomes_table = await self._create_outcomes_table()
        self.console.print(outcomes_table)

        # Recommendations
        recommendations = await self._create_recommendations_panel()
        self.console.print(recommendations)

        # Statistics
        await self._print_statistics()

    async def _print_statistics(self):
        """Print overall statistics"""
        try:
            # Get champion performance
            result = (
                self.supabase.client.table("shadow_performance")
                .select("*")
                .eq("variation_name", "CHAMPION")
                .eq("strategy_name", "OVERALL")
                .eq("timeframe", "24h")
                .single()
                .execute()
            )

            if result.data:
                champion = result.data

                stats_table = Table(
                    title="24-Hour Statistics",
                    show_header=True,
                    header_style="bold magenta",
                )
                stats_table.add_column("Metric", style="cyan")
                stats_table.add_column("Value", justify="right", style="white")

                stats_table.add_row("Total Opportunities", str(champion["total_opportunities"]))
                stats_table.add_row("Trades Taken", str(champion["trades_taken"]))
                stats_table.add_row("Trades Completed", str(champion["trades_completed"]))
                stats_table.add_row("Win Rate", f"{champion['win_rate']:.1%}")
                stats_table.add_row("Average P&L", f"{champion['avg_pnl_percentage']:.2f}%")
                stats_table.add_row("Sharpe Ratio", f"{champion['sharpe_ratio']:.2f}")
                stats_table.add_row("Max Drawdown", f"{champion['max_drawdown']:.2f}%")

                self.console.print(stats_table)

        except Exception as e:
            logger.error(f"Error printing statistics: {e}")


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Shadow Testing Dashboard")
    parser.add_argument("--live", action="store_true", help="Run live updating dashboard")
    parser.add_argument("--refresh", type=int, default=60, help="Refresh interval in seconds")

    args = parser.parse_args()

    dashboard = ShadowDashboard()

    if args.live:
        print("Starting live dashboard (Press Ctrl+C to exit)...")
        await dashboard.display_dashboard(refresh_interval=args.refresh)
    else:
        await dashboard.print_summary()


if __name__ == "__main__":
    asyncio.run(main())
