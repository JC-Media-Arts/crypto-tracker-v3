#!/usr/bin/env python3
"""
Run database migrations on Supabase.
Executes SQL migration files in order.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich import print as rprint

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.config import get_settings
from supabase import create_client, Client

console = Console()


def get_migration_files():
    """Get all SQL migration files in order."""
    migrations_dir = project_root / "migrations"
    if not migrations_dir.exists():
        return []

    # Get all .sql files and sort them
    migration_files = sorted(migrations_dir.glob("*.sql"))
    return migration_files


def run_migration(client: Client, migration_file: Path):
    """Run a single migration file."""
    console.print(f"\n[cyan]Running migration: {migration_file.name}[/cyan]")

    try:
        # Read the SQL file
        with open(migration_file, "r") as f:
            sql_content = f.read()

        # Split into individual statements (basic split on semicolon)
        # Note: This is simplified - production code should use a proper SQL parser
        statements = [s.strip() for s in sql_content.split(";") if s.strip()]

        # Execute each statement
        for i, statement in enumerate(statements):
            if statement and not statement.startswith("--"):
                try:
                    # Supabase doesn't have a direct SQL execution method in the Python client
                    # We'll use RPC or raw postgrest calls
                    # For now, we'll print the statements and provide instructions
                    console.print(f"[yellow]Statement {i+1}:[/yellow]")
                    console.print(
                        statement[:100] + "..." if len(statement) > 100 else statement
                    )

                except Exception as e:
                    console.print(f"[red]Error in statement {i+1}: {e}[/red]")
                    raise

        return True

    except Exception as e:
        console.print(f"[red]Failed to run migration {migration_file.name}: {e}[/red]")
        return False


def check_tables_exist(client: Client):
    """Check which tables already exist."""
    # This is a simplified check - in production you'd query information_schema
    tables_to_check = [
        "price_data",
        "ml_features",
        "ml_predictions",
        "hummingbot_trades",
        "hummingbot_performance",
        "daily_performance",
        "health_metrics",
        "system_config",
        "model_training_history",
    ]

    existing_tables = []
    for table in tables_to_check:
        try:
            # Try to query the table
            response = client.table(table).select("*").limit(1).execute()
            existing_tables.append(table)
        except:
            pass

    return existing_tables


def main():
    """Run all pending migrations."""
    console.print(
        "\n[bold cyan]Crypto Tracker v3 - Database Migration Runner[/bold cyan]\n"
    )

    # Get settings
    try:
        settings = get_settings()
    except Exception as e:
        console.print(f"[red]Failed to load settings: {e}[/red]")
        console.print("Make sure your .env file is configured correctly.")
        return 1

    # Connect to Supabase
    try:
        client = create_client(settings.supabase_url, settings.supabase_key)
        console.print("[green]✓ Connected to Supabase[/green]")
    except Exception as e:
        console.print(f"[red]Failed to connect to Supabase: {e}[/red]")
        return 1

    # Check existing tables
    existing_tables = check_tables_exist(client)
    if existing_tables:
        console.print(
            f"\n[yellow]Found existing tables: {', '.join(existing_tables)}[/yellow]"
        )

    # Get migration files
    migration_files = get_migration_files()
    if not migration_files:
        console.print(
            "[yellow]No migration files found in migrations/ directory[/yellow]"
        )
        return 0

    console.print(f"\n[cyan]Found {len(migration_files)} migration file(s)[/cyan]")

    # Important note about Supabase SQL execution
    console.print("\n[bold yellow]⚠️  Important: Supabase SQL Execution[/bold yellow]")
    console.print(
        "\nThe Supabase Python client doesn't directly support raw SQL execution."
    )
    console.print("You have two options to run the migrations:\n")

    console.print("[bold]Option 1: Use Supabase Dashboard (Recommended)[/bold]")
    console.print("1. Go to your Supabase project dashboard")
    console.print("2. Navigate to the SQL Editor")
    console.print("3. Copy and paste the migration SQL")
    console.print("4. Click 'Run'\n")

    console.print("[bold]Option 2: Use Supabase CLI[/bold]")
    console.print("1. Install Supabase CLI: brew install supabase/tap/supabase")
    console.print("2. Login: supabase login")
    console.print("3. Link project: supabase link --project-ref <your-project-ref>")
    console.print("4. Run: supabase db push\n")

    # Display migration content
    console.print("[bold cyan]Migration SQL Content:[/bold cyan]\n")

    for migration_file in migration_files:
        console.print(f"\n[green]File: {migration_file.name}[/green]")
        console.print("-" * 50)

        with open(migration_file, "r") as f:
            content = f.read()
            # Show first 500 characters
            if len(content) > 500:
                console.print(content[:500] + "\n... (truncated)")
            else:
                console.print(content)

    # Create a summary table
    table = Table(
        title="Tables to be Created", show_header=True, header_style="bold magenta"
    )
    table.add_column("Table Name", style="cyan")
    table.add_column("Purpose", style="white")

    table.add_row("price_data", "Real-time price data from Polygon.io")
    table.add_row("ml_features", "Technical indicators for ML")
    table.add_row("ml_predictions", "ML model predictions")
    table.add_row("hummingbot_trades", "Paper trading records")
    table.add_row("hummingbot_performance", "Trading performance metrics")
    table.add_row("daily_performance", "Daily summaries")
    table.add_row("health_metrics", "System health monitoring")
    table.add_row("system_config", "Configuration storage")
    table.add_row("model_training_history", "ML model versions")

    console.print("\n")
    console.print(table)

    # Save migration to a file for easy copying
    output_file = project_root / "migrations" / "combined_migration.sql"
    with open(output_file, "w") as f:
        for migration_file in migration_files:
            with open(migration_file, "r") as mf:
                f.write(f"-- {migration_file.name}\n")
                f.write(mf.read())
                f.write("\n\n")

    console.print(f"\n[green]✓ Combined migration saved to: {output_file}[/green]")
    console.print("\n[bold]Next Steps:[/bold]")
    console.print("1. Copy the SQL from migrations/combined_migration.sql")
    console.print("2. Go to your Supabase dashboard > SQL Editor")
    console.print("3. Paste and run the SQL")
    console.print("4. Verify tables were created in the Table Editor")

    return 0


if __name__ == "__main__":
    sys.exit(main())
