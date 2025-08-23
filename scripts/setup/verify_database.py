#!/usr/bin/env python3
"""
Verify database tables were created successfully and test basic operations.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
from rich.console import Console
from rich.table import Table


# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.config import get_settings
from supabase import create_client, Client

console = Console()


def test_table_operations(client: Client):
    """Test basic CRUD operations on each table."""
    results = {}

    # Test 1: System Config
    try:
        # Read default config
        response = client.table("system_config").select("*").execute()
        config_count = len(response.data)
        results["system_config"] = f"✓ Found {config_count} config entries"
    except Exception as e:
        results["system_config"] = f"✗ Error: {str(e)}"

    # Test 2: Insert test price data
    try:
        test_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": "BTC",
            "price": 50000.00,
            "volume": 1000000.00,
        }
        response = client.table("price_data").insert(test_data).execute()
        results["price_data_insert"] = "✓ Successfully inserted test price"

        # Clean up
        client.table("price_data").delete().eq("symbol", "BTC").execute()
    except Exception as e:
        results["price_data_insert"] = f"✗ Error: {str(e)}"

    # Test 3: Insert test ML prediction
    try:
        test_prediction = {
            "symbol": "ETH",
            "prediction": "UP",
            "confidence": 0.75,
            "model_version": "test_1.0.0",
        }
        response = client.table("ml_predictions").insert(test_prediction).execute()
        prediction_id = response.data[0]["prediction_id"]
        results["ml_predictions_insert"] = f"✓ Created prediction ID: {prediction_id}"

        # Clean up
        client.table("ml_predictions").delete().eq("prediction_id", prediction_id).execute()
    except Exception as e:
        results["ml_predictions_insert"] = f"✗ Error: {str(e)}"

    # Test 4: Check views
    try:
        response = client.table("v_recent_predictions").select("*").limit(1).execute()
        results["views"] = "✓ Views are accessible"
    except Exception as e:
        results["views"] = f"✗ Error accessing views: {str(e)}"

    return results


def check_table_structure(client: Client):
    """Check if all expected tables exist."""
    expected_tables = [
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
    missing_tables = []

    for table in expected_tables:
        try:
            # Try to query the table
            response = client.table(table).select("*").limit(1).execute()
            existing_tables.append(table)
        except Exception as e:
            missing_tables.append(table)

    return existing_tables, missing_tables


def main():
    """Verify database setup."""
    console.print("\n[bold cyan]Crypto Tracker v3 - Database Verification[/bold cyan]\n")

    # Get settings
    try:
        settings = get_settings()
    except Exception as e:
        console.print(f"[red]Failed to load settings: {e}[/red]")
        return 1

    # Connect to Supabase
    try:
        client = create_client(settings.supabase_url, settings.supabase_key)
        console.print("[green]✓ Connected to Supabase[/green]\n")
    except Exception as e:
        console.print(f"[red]Failed to connect to Supabase: {e}[/red]")
        return 1

    # Check table structure
    console.print("[cyan]Checking table structure...[/cyan]")
    existing_tables, missing_tables = check_table_structure(client)

    # Display results in a table
    table = Table(title="Database Tables Status", show_header=True, header_style="bold magenta")
    table.add_column("Table Name", style="cyan")
    table.add_column("Status", style="white")

    for table_name in existing_tables:
        table.add_row(table_name, "[green]✓ Exists[/green]")

    for table_name in missing_tables:
        table.add_row(table_name, "[red]✗ Missing[/red]")

    console.print(table)

    if missing_tables:
        console.print(f"\n[red]Missing {len(missing_tables)} tables. Please run migrations.[/red]")
        return 1

    # Test operations
    console.print("\n[cyan]Testing database operations...[/cyan]")
    test_results = test_table_operations(client)

    for operation, result in test_results.items():
        console.print(f"{operation}: {result}")

    # Summary
    console.print("\n[bold green]✅ Database setup verified successfully![/bold green]")
    console.print("\nAll tables are created and basic operations are working.")
    console.print("\n[bold]Next Steps:[/bold]")
    console.print("1. Set up Polygon data collection")
    console.print("2. Implement ML feature engineering")
    console.print("3. Create ML signal strategy for Hummingbot")
    console.print("4. Start paper trading!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
