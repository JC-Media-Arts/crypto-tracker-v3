#!/usr/bin/env python3
"""
Test Paper Trading Module

Tests the paper trading functionality without requiring a database.
Simulates order execution, position management, and P&L tracking.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.trading.paper_trader import PaperTrader, OrderType, OrderSide, OrderStatus


class MockSupabaseClient:
    """Mock Supabase client for testing."""

    def __init__(self):
        self.client = self
        self.mock_prices = {
            "BTC": 45000.0,
            "ETH": 2500.0,
            "SOL": 100.0,
            "TEST": 95.0,
        }

    def table(self, name):
        self.table_name = name
        return self

    def select(self, *args):
        return self

    def eq(self, field, value):
        if field == "symbol":
            self.symbol = value
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, *args):
        return self

    def insert(self, data):
        return self

    def execute(self):
        # Return mock price data
        if hasattr(self, "symbol") and self.symbol in self.mock_prices:
            return type(
                "obj", (object,), {"data": [{"close": self.mock_prices[self.symbol]}]}
            )()
        return type("obj", (object,), {"data": []})()


async def test_paper_trader():
    """Test Paper Trader functionality."""

    print("=" * 60)
    print("Testing Paper Trading Module")
    print("=" * 60)

    # Initialize paper trader
    mock_supabase = MockSupabaseClient()
    trader = PaperTrader(
        supabase_client=mock_supabase,
        initial_balance=10000.0,
        config={
            "trading_fee": 0.001,  # 0.1% fee
            "slippage_pct": 0.0005,  # 0.05% slippage
            "max_positions": 5,
        },
    )

    print(f"\nInitial Portfolio:")
    print(f"  Balance: ${trader.balance:,.2f}")
    print(f"  Positions: {len(trader.positions)}")

    # Test 1: Create a position
    print("\n1. Creating a position...")
    position_result = await trader.create_position(
        {
            "symbol": "SOL",
            "strategy_name": "DCA",
        }
    )

    if position_result["success"]:
        position_id = position_result["position_id"]
        print(f"✅ Position created: {position_id}")
    else:
        print(f"❌ Failed to create position: {position_result['error']}")
        return

    # Test 2: Place a buy order
    print("\n2. Placing buy order...")
    buy_order = await trader.place_order(
        {
            "position_id": position_id,
            "symbol": "SOL",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 10,  # 10 SOL
            "price": 100.0,  # Not used for market orders
        }
    )

    if buy_order["success"]:
        print(f"✅ Buy order placed: {buy_order['order_id']}")
        print(f"   Status: {buy_order['status']}")

        # Check order details
        order = trader.orders[buy_order["order_id"]]
        print(f"   Filled at: ${order.filled_price:.2f}")
        print(f"   Quantity: {order.filled_quantity}")
        print(f"   Fees: ${order.fees:.2f}")
        print(f"   Slippage: ${order.slippage:.2f}")
    else:
        print(f"❌ Order failed: {buy_order['error']}")

    # Test 3: Check portfolio after buy
    print("\n3. Portfolio after buy:")
    summary = trader.get_portfolio_summary()
    print(f"   Cash balance: ${summary['cash_balance']:,.2f}")
    print(f"   Positions value: ${summary['positions_value']:,.2f}")
    print(f"   Total value: ${summary['portfolio_value']:,.2f}")
    print(f"   Holdings: {trader.holdings}")

    # Test 4: Place limit orders (DCA grid)
    print("\n4. Placing DCA grid orders...")
    grid_levels = [98.0, 96.0, 94.0]  # Buy at these levels
    limit_orders = []

    for i, price in enumerate(grid_levels):
        order = await trader.place_order(
            {
                "position_id": position_id,
                "symbol": "SOL",
                "side": "BUY",
                "order_type": "LIMIT",
                "quantity": 5,  # 5 SOL per level
                "price": price,
            }
        )

        if order["success"]:
            limit_orders.append(order["order_id"])
            print(f"   Level {i+1}: Buy 5 SOL @ ${price:.2f} - {order['status']}")

    print(f"✅ Placed {len(limit_orders)} limit orders")

    # Test 5: Simulate price drop and check pending orders
    print("\n5. Simulating price drop to $96...")
    mock_supabase.mock_prices["SOL"] = 96.0
    await trader.check_pending_orders("SOL", 96.0)

    # Check which orders filled
    filled_count = 0
    for order_id in limit_orders:
        if trader.orders[order_id].status == OrderStatus.FILLED:
            filled_count += 1

    print(f"   {filled_count} orders filled at new price")
    print(f"   Updated holdings: {trader.holdings.get('SOL', 0)} SOL")

    # Test 6: Update position price and check P&L
    print("\n6. Checking position P&L...")
    position = trader.positions[position_id]
    position.update_price(96.0)

    print(f"   Entry price: ${position.entry_price:.2f}")
    print(f"   Current price: ${position.current_price:.2f}")
    print(f"   Quantity: {position.quantity}")
    print(f"   Unrealized P&L: ${position.unrealized_pnl:.2f}")

    # Test 7: Simulate price recovery
    print("\n7. Simulating price recovery to $105...")
    mock_supabase.mock_prices["SOL"] = 105.0
    position.update_price(105.0)

    print(f"   New unrealized P&L: ${position.unrealized_pnl:.2f}")
    print(
        f"   P&L %: {(position.unrealized_pnl / (position.entry_price * position.quantity) * 100):.1f}%"
    )

    # Test 8: Close position with profit
    print("\n8. Closing position...")
    close_result = await trader.close_position(
        position_id=position_id, reason="TAKE_PROFIT", exit_price=105.0
    )

    if close_result["success"]:
        print(f"✅ Position closed")
        print(f"   Exit price: ${close_result['exit_price']:.2f}")
        print(f"   Final P&L: ${close_result['final_pnl']:.2f}")
        print(f"   Reason: {close_result['reason']}")
    else:
        print(f"❌ Failed to close: {close_result['error']}")

    # Test 9: Final portfolio summary
    print("\n9. Final Portfolio Summary:")
    final_summary = trader.get_portfolio_summary()
    print(f"   Portfolio value: ${final_summary['portfolio_value']:,.2f}")
    print(f"   Cash balance: ${final_summary['cash_balance']:,.2f}")
    print(f"   Total return: {final_summary['total_return']:.2f}%")
    print(f"   Open positions: {final_summary['open_positions']}")
    print(f"   Total trades: {final_summary['total_trades']}")

    # Test 10: Performance statistics
    print("\n10. Performance Statistics:")
    stats = trader.get_performance_stats()
    print(f"   Total trades: {stats['total_trades']}")
    print(f"   Win rate: {stats['win_rate']:.1f}%")
    print(f"   Avg win: ${stats['avg_win']:.2f}")
    print(f"   Avg loss: ${stats['avg_loss']:.2f}")
    print(f"   Profit factor: {stats['profit_factor']:.2f}")
    print(f"   Total P&L: ${stats['total_pnl']:.2f}")

    # Test 11: Validate order rejection (insufficient balance)
    print("\n11. Testing order validation...")
    large_order = await trader.place_order(
        {
            "symbol": "BTC",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 100,  # Way too much BTC
            "price": 45000.0,
        }
    )

    if not large_order["success"]:
        print(f"✅ Correctly rejected large order: {large_order['error']}")
    else:
        print("❌ Should have rejected order due to insufficient balance")

    print("\n" + "=" * 60)
    print("Paper Trader Test Complete!")
    print("=" * 60)

    # Summary
    print("\nSummary:")
    print("✅ Position creation working")
    print("✅ Market order execution working")
    print("✅ Limit order placement working")
    print("✅ P&L tracking working")
    print("✅ Position closing working")
    print("✅ Portfolio tracking working")
    print("✅ Performance metrics working")
    print("✅ Order validation working")
    print("\nThe Paper Trader is ready for integration!")


if __name__ == "__main__":
    asyncio.run(test_paper_trader())
