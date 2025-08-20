#!/usr/bin/env python3
"""
Real-time trading activity monitor for terminal
"""

import asyncio
import sys
from datetime import datetime, timedelta
from collections import Counter
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from src.data.supabase_client import SupabaseClient

console = Console()


def create_layout():
    """Create the dashboard layout"""
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="footer", size=3)
    )
    
    layout["main"].split_row(
        Layout(name="scans"),
        Layout(name="shadows")
    )
    
    return layout


def get_header():
    """Create header panel"""
    return Panel(
        Text("📊 CRYPTO TRADING ACTIVITY MONITOR", justify="center", style="bold cyan"),
        border_style="cyan"
    )


def get_footer():
    """Create footer panel"""
    return Panel(
        Text(f"Last updated: {datetime.now().strftime('%H:%M:%S')} | Press Ctrl+C to exit", 
             justify="center", style="dim"),
        border_style="dim"
    )


def get_scan_table(client):
    """Get recent scan activity"""
    table = Table(title="🤖 Paper Trading Scans (Last 30 min)", 
                  show_header=True, header_style="bold magenta")
    
    table.add_column("Time", style="cyan", width=8)
    table.add_column("Symbol", style="yellow", width=8)
    table.add_column("Strategy", width=10)
    table.add_column("Decision", width=10)
    table.add_column("ML Conf", justify="right", width=8)
    table.add_column("Regime", width=10)
    
    try:
        # Get recent scans
        cutoff = (datetime.utcnow() - timedelta(minutes=30)).isoformat()
        result = (
            client.client.table("scan_history")
            .select("*")
            .gte("timestamp", cutoff)
            .order("scan_id", desc=True)
            .limit(15)
            .execute()
        )
        
        if result.data:
            for scan in result.data:
                time_str = scan["timestamp"][11:19] if scan.get("timestamp") else "N/A"
                decision = scan.get("decision", "SKIP")
                ml_conf = scan.get("ml_confidence", 0) or 0
                
                # Color code decision
                if decision == "TAKE":
                    decision_style = "bold green"
                elif decision == "SKIP":
                    decision_style = "dim red"
                else:
                    decision_style = "yellow"
                
                # Extract regime from features if available
                import json
                regime = "N/A"
                if scan.get("features"):
                    try:
                        features = json.loads(scan["features"])
                        regime = features.get("market_regime", "N/A")
                    except:
                        pass
                
                table.add_row(
                    time_str,
                    scan.get("symbol", "N/A"),
                    scan.get("strategy_name", "N/A"),
                    Text(decision, style=decision_style),
                    f"{ml_conf:.1%}",
                    regime
                )
        else:
            table.add_row("No scans", "", "", "", "", "")
            
    except Exception as e:
        table.add_row(f"Error: {str(e)[:30]}", "", "", "", "", "")
    
    return table


def get_shadow_table(client):
    """Get shadow trading activity"""
    table = Table(title="👻 Shadow Testing Activity", 
                  show_header=True, header_style="bold green")
    
    table.add_column("Metric", style="cyan", width=25)
    table.add_column("Value", justify="right", width=15)
    
    try:
        # Total shadows
        total = client.client.table("shadow_variations").select("count", count="exact").execute()
        table.add_row("Total Shadows", f"{total.count:,}")
        
        # Recent shadows (10 min)
        cutoff = (datetime.utcnow() - timedelta(minutes=10)).isoformat()
        recent = client.client.table("shadow_variations").select("count", count="exact").gte("created_at", cutoff).execute()
        table.add_row("Last 10 min", f"{recent.count:,}")
        
        # Would take trade
        would_take = client.client.table("shadow_variations").select("count", count="exact").eq("would_take_trade", True).execute()
        table.add_row("Would Take Trade", f"{would_take.count:,}")
        
        # Outcomes evaluated
        outcomes = client.client.table("shadow_outcomes").select("count", count="exact").execute()
        table.add_row("Outcomes Evaluated", f"{outcomes.count:,}")
        
        # Get variation breakdown
        variations = (
            client.client.table("shadow_variations")
            .select("variation_name")
            .gte("created_at", cutoff)
            .limit(100)
            .execute()
        )
        
        if variations.data:
            var_counts = Counter(v["variation_name"] for v in variations.data)
            table.add_row("", "")  # Empty row
            table.add_row("Recent Variations:", "", style="bold")
            for name, count in var_counts.most_common(3):
                table.add_row(f"  {name}", str(count))
        
    except Exception as e:
        table.add_row(f"Error: {str(e)[:40]}", "")
    
    return table


async def monitor():
    """Main monitoring loop"""
    client = SupabaseClient()
    layout = create_layout()
    
    with Live(layout, refresh_per_second=0.5, screen=True) as live:
        while True:
            try:
                # Update header and footer
                layout["header"].update(get_header())
                layout["footer"].update(get_footer())
                
                # Update main panels
                layout["scans"].update(Panel(get_scan_table(client), border_style="blue"))
                layout["shadows"].update(Panel(get_shadow_table(client), border_style="green"))
                
                # Wait before next update
                await asyncio.sleep(5)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                await asyncio.sleep(5)


if __name__ == "__main__":
    console.print("[bold cyan]Starting Trading Activity Monitor...[/bold cyan]")
    console.print("[dim]Press Ctrl+C to exit[/dim]\n")
    
    try:
        asyncio.run(monitor())
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitor stopped[/yellow]")
        sys.exit(0)
