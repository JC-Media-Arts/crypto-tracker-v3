#!/usr/bin/env python3
"""
Test Polygon.io WebSocket connection.
Verifies we can connect and receive crypto data.
"""

import sys
import time
import json
from pathlib import Path
from rich.console import Console

import websocket
import threading

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.config import get_settings

console = Console()


def test_polygon_websocket():
    """Test Polygon WebSocket connection."""
    console.print("\n[bold cyan]Testing Polygon.io WebSocket Connection[/bold cyan]\n")

    # Get settings
    try:
        settings = get_settings()
        api_key = settings.polygon_api_key
    except Exception as e:
        console.print(f"[red]Failed to load settings: {e}[/red]")
        return False

    # Test data storage
    messages_received = []
    connection_established = False
    auth_success = False

    def on_open(ws):
        """Handle connection open."""
        nonlocal connection_established
        connection_established = True
        console.print("[green]✓ WebSocket connection established[/green]")

        # Send authentication
        auth_msg = {"action": "auth", "params": api_key}
        ws.send(json.dumps(auth_msg))
        console.print("[yellow]→ Sent authentication request[/yellow]")

    def on_message(ws, message):
        """Handle incoming messages."""
        nonlocal auth_success

        try:
            data = json.loads(message)

            if isinstance(data, list):
                for msg in data:
                    if msg.get("status") == "auth_success":
                        auth_success = True
                        console.print("[green]✓ Authentication successful[/green]")

                        # Subscribe to BTC and ETH for testing
                        subscribe_msg = {
                            "action": "subscribe",
                            "params": "XA.BTC-USD,XA.ETH-USD",
                        }
                        ws.send(json.dumps(subscribe_msg))
                        console.print(
                            "[yellow]→ Subscribed to BTC-USD and ETH-USD[/yellow]"
                        )

                    elif msg.get("ev") == "XA":  # Crypto aggregate
                        symbol = msg["pair"].replace("-USD", "")
                        price = msg.get("c", 0)
                        volume = msg.get("v", 0)

                        messages_received.append(msg)
                        console.print(
                            f"[green]✓ Received {symbol} data: "
                            f"${price:,.2f} (volume: {volume:,.0f})[/green]"
                        )

                        # Close after receiving some data
                        if len(messages_received) >= 5:
                            ws.close()
            else:
                if data.get("status") == "error":
                    console.print(
                        f"[red]✗ Error: {data.get('message', 'Unknown error')}[/red]"
                    )

        except Exception as e:
            console.print(f"[red]Error parsing message: {e}[/red]")

    def on_error(ws, error):
        """Handle errors."""
        console.print(f"[red]✗ WebSocket error: {error}[/red]")

    def on_close(ws, close_status_code, close_msg):
        """Handle connection close."""
        console.print("[yellow]WebSocket closed[/yellow]")

    # Create WebSocket connection
    ws_url = "wss://socket.polygon.io/crypto"

    try:
        ws = websocket.WebSocketApp(
            ws_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )

        # Run in a thread with timeout
        wst = threading.Thread(target=ws.run_forever)
        wst.daemon = True
        wst.start()

        # Wait for data or timeout
        timeout = 30  # seconds
        start_time = time.time()

        console.print(f"\n[cyan]Waiting for data (timeout: {timeout}s)...[/cyan]\n")

        while time.time() - start_time < timeout:
            if len(messages_received) >= 5:
                break
            time.sleep(0.5)

        # Close connection
        ws.close()

        # Results
        console.print("\n[bold]Test Results:[/bold]")
        console.print(
            f"Connection established: {'✓' if connection_established else '✗'}"
        )
        console.print(f"Authentication successful: {'✓' if auth_success else '✗'}")
        console.print(f"Messages received: {len(messages_received)}")

        if messages_received:
            console.print("\n[bold]Sample data received:[/bold]")
            for msg in messages_received[:3]:
                symbol = msg["pair"].replace("-USD", "")
                console.print(f"  {symbol}: ${msg.get('c', 0):,.2f}")

        success = connection_established and auth_success and len(messages_received) > 0

        if success:
            console.print(
                "\n[bold green]✅ Polygon WebSocket test PASSED![/bold green]"
            )
            console.print("\nYou're ready to start collecting real-time crypto data!")
        else:
            console.print("\n[bold red]❌ Polygon WebSocket test FAILED![/bold red]")
            if not connection_established:
                console.print("Could not establish connection - check network")
            elif not auth_success:
                console.print("Authentication failed - check API key")
            else:
                console.print("No data received - subscription may have failed")

        return success

    except Exception as e:
        console.print(f"[red]Failed to create WebSocket: {e}[/red]")
        return False


def main():
    """Run the test."""
    success = test_polygon_websocket()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
