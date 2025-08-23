#!/usr/bin/env python3
"""
Test all data source connections to ensure they're working.
Tests Polygon, Supabase, Kraken, and Slack connections.
"""

import asyncio
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table


# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

console = Console()


async def test_polygon_connection():
    """Test Polygon.io API connection."""
    try:
        from polygon import RESTClient
        from src.config import get_settings

        settings = get_settings()
        client = RESTClient(api_key=settings.polygon_api_key)

        # Test with a simple ticker request
        ticker = client.get_ticker_details("X:BTCUSD")

        if ticker:
            return True, "✅ Connected - BTC ticker retrieved"
        else:
            return False, "❌ Connected but no data returned"

    except Exception as e:
        return False, f"❌ Connection failed: {str(e)[:50]}"


async def test_supabase_connection():
    """Test Supabase database connection."""
    try:
        from supabase import create_client
        from src.config import get_settings

        settings = get_settings()
        client = create_client(settings.supabase_url, settings.supabase_key)

        # Test with a simple query
        try:
            client.table("price_data").select("*").limit(1).execute()
            return True, "✅ Connected to Supabase (tables exist)"
        except Exception as table_error:
            # If table doesn't exist, that's OK - connection still works
            error_msg = str(table_error)
            if "Could not find the table" in error_msg or "does not exist" in error_msg:
                return True, "✅ Connected (tables not created yet - run migrations)"
            else:
                return False, f"❌ Query failed: {error_msg[:50]}"

    except Exception as e:
        return False, f"❌ Connection failed: {str(e)[:50]}"


async def test_kraken_connection():
    """Test Kraken API connection."""
    try:
        import krakenex
        from src.config import get_settings

        settings = get_settings()
        kraken = krakenex.API(key=settings.kraken_api_key, secret=settings.kraken_api_secret)

        # Test with server time (public endpoint)
        response = kraken.query_public("Time")

        if response.get("error"):
            return False, f"❌ API error: {response['error']}"

        return True, "✅ Connected to Kraken"

    except Exception as e:
        return False, f"❌ Connection failed: {str(e)[:50]}"


async def test_slack_connection():
    """Test Slack API connection."""
    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError
        from src.config import get_settings

        settings = get_settings()
        client = WebClient(token=settings.slack_bot_token)

        # Test authentication
        response = client.auth_test()

        if response["ok"]:
            return True, f"✅ Connected as {response['user']}"
        else:
            return False, "❌ Authentication failed"

    except SlackApiError as e:
        return False, f"❌ Slack API error: {e.response['error']}"
    except Exception as e:
        return False, f"❌ Connection failed: {str(e)[:50]}"


async def test_websocket_connection():
    """Test Polygon WebSocket connection."""
    try:
        from polygon import WebSocketClient
        from src.config import get_settings

        settings = get_settings()

        # Create WebSocket client
        ws = WebSocketClient(api_key=settings.polygon_api_key, feed="delayed", market="crypto")

        # Test subscription
        ws.subscribe("XA.BTC-USD")

        return True, "✅ WebSocket client created (live test requires connection)"

    except Exception as e:
        return False, f"❌ WebSocket setup failed: {str(e)[:50]}"


async def main():
    """Run all connection tests."""
    console.print("\n[bold cyan]Crypto Tracker v3 - Connection Tests[/bold cyan]\n")

    # Create results table
    table = Table(title="Data Source Connections", show_header=True, header_style="bold magenta")
    table.add_column("Service", style="cyan", width=20)
    table.add_column("Status", width=60)

    # Run tests
    tests = [
        ("Polygon REST API", test_polygon_connection()),
        ("Polygon WebSocket", test_websocket_connection()),
        ("Supabase Database", test_supabase_connection()),
        ("Kraken API", test_kraken_connection()),
        ("Slack API", test_slack_connection()),
    ]

    all_passed = True
    for name, test_coro in tests:
        passed, message = await test_coro
        table.add_row(name, message)
        if not passed:
            all_passed = False

    console.print(table)

    # Additional checks
    console.print("\n[bold yellow]Required Slack Channels:[/bold yellow]")
    console.print("• #ml-signals - Real-time predictions and trades")
    console.print("• #daily-reports - 7 AM and 7 PM summaries")
    console.print("• #system-alerts - Critical issues only")

    # Summary
    if all_passed:
        console.print("\n[bold green]✅ All connections successful![/bold green]")
        console.print("\nNext steps:")
        console.print("1. Create Slack channels listed above")
        console.print("2. Set up GitHub repository")
        console.print("3. Run database migrations")
        return 0
    else:
        console.print("\n[bold red]❌ Some connections failed. Check your API keys in .env[/bold red]")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
