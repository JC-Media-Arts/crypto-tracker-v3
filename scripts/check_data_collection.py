#!/usr/bin/env python3
"""
Check data collection status - see what coins we're receiving data for.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from rich.console import Console
from rich.table import Table


# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import get_settings  # noqa: E402
from supabase import create_client  # noqa: E402

console = Console()


def check_data_collection():
    """Check what data we're collecting."""
    console.print(
        "\n[bold cyan]Crypto Tracker v3 - Data Collection Status[/bold cyan]\n"
    )

    # Get settings and connect to Supabase
    try:
        settings = get_settings()
        client = create_client(settings.supabase_url, settings.supabase_key)
    except Exception as e:
        console.print(f"[red]Failed to connect: {e}[/red]")
        return

    # Get data from last 10 minutes
    ten_minutes_ago = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()

    try:
        # Get recent price data
        response = (
            client.table("price_data")
            .select("symbol, timestamp, price")
            .gte("timestamp", ten_minutes_ago)
            .execute()
        )

        # Process data to get unique symbols and counts
        symbol_data = {}
        for record in response.data:
            symbol = record["symbol"]
            if symbol not in symbol_data:
                symbol_data[symbol] = {
                    "count": 0,
                    "latest_price": 0,
                    "latest_time": None,
                }

            symbol_data[symbol]["count"] += 1
            if (
                not symbol_data[symbol]["latest_time"]
                or record["timestamp"] > symbol_data[symbol]["latest_time"]
            ):
                symbol_data[symbol]["latest_price"] = float(record["price"])
                symbol_data[symbol]["latest_time"] = record["timestamp"]

        # Create table
        table = Table(
            title="Data Collection Status (Last 10 Minutes)",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Symbol", style="cyan", width=10)
        table.add_column("Latest Price", style="green", justify="right")
        table.add_column("Records", style="yellow", justify="center")
        table.add_column("Last Update", style="white")

        # Sort by symbol
        sorted_symbols = sorted(symbol_data.items())

        for symbol, data in sorted_symbols[:20]:  # Show first 20
            # Format time
            if data["latest_time"]:
                last_update = datetime.fromisoformat(
                    data["latest_time"].replace("Z", "+00:00")
                )
                time_ago = (datetime.now(timezone.utc) - last_update).total_seconds()
                if time_ago < 60:
                    time_str = f"{int(time_ago)}s ago"
                else:
                    time_str = f"{int(time_ago/60)}m ago"
            else:
                time_str = "N/A"

            table.add_row(
                symbol, f"${data['latest_price']:,.2f}", str(data["count"]), time_str
            )

        console.print(table)

        # Summary
        console.print("\n[bold]Summary:[/bold]")
        console.print(f"Total unique symbols: {len(symbol_data)}")
        console.print(f"Total records: {sum(d['count'] for d in symbol_data.values())}")

        # Show any missing symbols from expected list
        expected_symbols = [
            "BTC",
            "ETH",
            "SOL",
            "BNB",
            "XRP",
            "ADA",
            "AVAX",
            "DOGE",
            "DOT",
            "POL",
        ]

        collected_symbols = set(symbol_data.keys())
        missing = [s for s in expected_symbols if s not in collected_symbols]

        if missing:
            console.print(
                f"\n[yellow]Missing symbols from top 10: {', '.join(missing)}[/yellow]"
            )
        else:
            console.print("\n[green]✓ All top 10 symbols are being collected![/green]")

    except Exception as e:
        console.print(f"[red]Error querying data: {e}[/red]")


if __name__ == "__main__":
    check_data_collection()
