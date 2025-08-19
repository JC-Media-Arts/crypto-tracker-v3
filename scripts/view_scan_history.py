#!/usr/bin/env python3
"""
View and analyze scan history data
"""

import sys
import asyncio
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from loguru import logger

sys.path.append('.')

from src.data.supabase_client import SupabaseClient
from src.strategies.scan_logger import ScanLogger

console = Console()


class ScanHistoryViewer:
    def __init__(self):
        self.supabase = SupabaseClient()
        self.scan_logger = ScanLogger(self.supabase.client)
    
    def view_recent_scans(self, hours: int = 1):
        """View recent scan history"""
        
        console.print(Panel(f"[bold cyan]Recent Scan History (Last {hours} hours)[/bold cyan]"))
        
        # Get stats
        stats = self.scan_logger.get_decision_stats(hours=hours)
        
        # Display summary
        summary_table = Table(title="Summary Statistics", show_header=True)
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="green")
        
        summary_table.add_row("Total Scans", str(stats.get('total_scans', 0)))
        summary_table.add_row("Symbols Scanned", str(stats.get('symbols_scanned', 0)))
        summary_table.add_row("Avg ML Confidence", f"{stats.get('avg_confidence', 0):.3f}")
        
        console.print(summary_table)
        
        # Display decisions breakdown
        if stats.get('decisions'):
            decision_table = Table(title="Decisions Breakdown", show_header=True)
            decision_table.add_column("Decision", style="cyan")
            decision_table.add_column("Count", style="yellow")
            decision_table.add_column("Percentage", style="green")
            
            total = stats['total_scans']
            for decision, count in stats['decisions'].items():
                pct = (count / total * 100) if total > 0 else 0
                decision_table.add_row(decision, str(count), f"{pct:.1f}%")
            
            console.print(decision_table)
        
        # Display strategy breakdown
        if stats.get('strategies'):
            strategy_table = Table(title="Strategy Breakdown", show_header=True)
            strategy_table.add_column("Strategy", style="cyan")
            strategy_table.add_column("Count", style="yellow")
            
            for strategy, count in stats['strategies'].items():
                strategy_table.add_row(strategy, str(count))
            
            console.print(strategy_table)
    
    def view_near_misses(self, confidence_threshold: float = 0.50):
        """View near-miss opportunities"""
        
        console.print(Panel(f"[bold yellow]Near Misses (Confidence > {confidence_threshold})[/bold yellow]"))
        
        near_misses = self.scan_logger.get_near_misses(
            confidence_threshold=confidence_threshold,
            limit=20
        )
        
        if not near_misses:
            console.print("[yellow]No near misses found[/yellow]")
            return
        
        # Display near misses
        miss_table = Table(title="Top Near-Miss Opportunities", show_header=True)
        miss_table.add_column("Time", style="cyan")
        miss_table.add_column("Symbol", style="yellow")
        miss_table.add_column("Strategy", style="green")
        miss_table.add_column("Confidence", style="red")
        miss_table.add_column("Reason", style="white")
        
        for miss in near_misses[:10]:
            timestamp = miss.get('timestamp', '')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    time_str = dt.strftime('%H:%M:%S')
                except:
                    time_str = timestamp[:19]
            else:
                time_str = 'N/A'
            
            miss_table.add_row(
                time_str,
                miss.get('symbol', 'N/A'),
                miss.get('strategy_name', 'N/A'),
                f"{miss.get('ml_confidence', 0):.3f}",
                miss.get('reason', 'N/A')[:40]
            )
        
        console.print(miss_table)
    
    def analyze_thresholds(self):
        """Analyze if thresholds need adjustment"""
        
        console.print(Panel("[bold magenta]Threshold Analysis[/bold magenta]"))
        
        # Get recent scans
        scans = self.scan_logger.get_recent_scans(hours=24)
        
        if not scans:
            console.print("[yellow]No scan data available[/yellow]")
            return
        
        # Convert to DataFrame for analysis
        df = pd.DataFrame(scans)
        
        # Analyze by strategy
        strategies = df['strategy_name'].unique()
        
        for strategy in strategies:
            strategy_df = df[df['strategy_name'] == strategy]
            
            console.print(f"\n[bold]{strategy} Strategy Analysis:[/bold]")
            
            # Count decisions
            decision_counts = strategy_df['decision'].value_counts()
            
            # Calculate metrics
            total = len(strategy_df)
            takes = decision_counts.get('TAKE', 0)
            skips = decision_counts.get('SKIP', 0)
            near_misses = decision_counts.get('NEAR_MISS', 0)
            
            take_rate = (takes / total * 100) if total > 0 else 0
            near_miss_rate = (near_misses / total * 100) if total > 0 else 0
            
            console.print(f"  Total Scans: {total}")
            console.print(f"  Take Rate: {take_rate:.1f}%")
            console.print(f"  Near Miss Rate: {near_miss_rate:.1f}%")
            
            # Recommendations
            if take_rate < 0.5:
                console.print("  [red]⚠️ Very low take rate - consider lowering thresholds[/red]")
            elif near_miss_rate > 10:
                console.print("  [yellow]⚠️ High near-miss rate - consider slightly lowering confidence threshold[/yellow]")
            else:
                console.print("  [green]✅ Thresholds appear balanced[/green]")
    
    def export_to_csv(self, hours: int = 24, filename: Optional[str] = None):
        """Export scan history to CSV for analysis"""
        
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"scan_history_{timestamp}.csv"
        
        scans = self.scan_logger.get_recent_scans(hours=hours)
        
        if not scans:
            console.print("[yellow]No data to export[/yellow]")
            return
        
        df = pd.DataFrame(scans)
        df.to_csv(filename, index=False)
        
        console.print(f"[green]✅ Exported {len(scans)} records to {filename}[/green]")


async def main():
    viewer = ScanHistoryViewer()
    
    # Show menu
    console.print("\n[bold cyan]Scan History Viewer[/bold cyan]\n")
    console.print("1. View recent scans (last hour)")
    console.print("2. View recent scans (last 24 hours)")
    console.print("3. View near misses")
    console.print("4. Analyze thresholds")
    console.print("5. Export to CSV")
    console.print("6. Exit")
    
    choice = input("\nSelect option: ")
    
    if choice == '1':
        viewer.view_recent_scans(hours=1)
    elif choice == '2':
        viewer.view_recent_scans(hours=24)
    elif choice == '3':
        viewer.view_near_misses()
    elif choice == '4':
        viewer.analyze_thresholds()
    elif choice == '5':
        viewer.export_to_csv()
    elif choice == '6':
        console.print("[yellow]Goodbye![/yellow]")
    else:
        console.print("[red]Invalid option[/red]")


if __name__ == "__main__":
    asyncio.run(main())
