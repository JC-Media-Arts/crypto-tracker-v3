"""
Hummingbot API Client for ML Integration
Connects our ML trading system to Hummingbot API
"""

import asyncio
import aiohttp
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class HummingbotOrder:
    """Order structure for Hummingbot API"""

    symbol: str
    side: str  # 'buy' or 'sell'
    price: float
    amount: float
    order_type: str = "limit"
    client_order_id: Optional[str] = None


@dataclass
class HummingbotPosition:
    """Position tracking for Hummingbot"""

    symbol: str
    side: str
    amount: float
    entry_price: float
    current_price: float
    pnl: float
    timestamp: datetime


class HummingbotAPIClient:
    """Client for interacting with Hummingbot API"""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        username: str = "admin",
        password: str = "admin",
    ):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.session: Optional[aiohttp.ClientSession] = None
        self.token: Optional[str] = None

    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()

    async def connect(self):
        """Initialize connection and authenticate"""
        self.session = aiohttp.ClientSession()
        await self.authenticate()

    async def disconnect(self):
        """Close connection"""
        if self.session:
            await self.session.close()

    async def authenticate(self):
        """Authenticate with the API"""
        try:
            async with self.session.post(
                f"{self.base_url}/auth/token",
                data={"username": self.username, "password": self.password},
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.token = data.get("access_token")
                    logger.info("Successfully authenticated with Hummingbot API")
                else:
                    logger.error(f"Authentication failed: {response.status}")
        except Exception as e:
            logger.error(f"Authentication error: {e}")

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with authentication"""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def create_bot(
        self,
        bot_name: str,
        exchange: str = "binance_paper_trade",
        config: Optional[Dict] = None,
    ) -> Dict:
        """Create a new trading bot"""
        try:
            payload = {
                "bot_name": bot_name,
                "exchange": exchange,
                "config": config or {},
            }

            async with self.session.post(
                f"{self.base_url}/bots", json=payload, headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Created bot: {bot_name}")
                    return data
                else:
                    logger.error(f"Failed to create bot: {response.status}")
                    return {}
        except Exception as e:
            logger.error(f"Error creating bot: {e}")
            return {}

    async def place_order(self, bot_id: str, order: HummingbotOrder) -> Dict:
        """Place an order through Hummingbot"""
        try:
            payload = {
                "symbol": order.symbol,
                "side": order.side,
                "price": order.price,
                "amount": order.amount,
                "order_type": order.order_type,
                "client_order_id": order.client_order_id,
            }

            async with self.session.post(
                f"{self.base_url}/bots/{bot_id}/orders",
                json=payload,
                headers=self._get_headers(),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(
                        f"Order placed: {order.symbol} {order.side} {order.amount}@{order.price}"
                    )
                    return data
                else:
                    logger.error(f"Failed to place order: {response.status}")
                    return {}
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return {}

    async def cancel_order(self, bot_id: str, order_id: str) -> bool:
        """Cancel an order"""
        try:
            async with self.session.delete(
                f"{self.base_url}/bots/{bot_id}/orders/{order_id}",
                headers=self._get_headers(),
            ) as response:
                if response.status == 200:
                    logger.info(f"Order cancelled: {order_id}")
                    return True
                else:
                    logger.error(f"Failed to cancel order: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False

    async def get_positions(self, bot_id: str) -> List[HummingbotPosition]:
        """Get current positions"""
        try:
            async with self.session.get(
                f"{self.base_url}/bots/{bot_id}/positions", headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    positions = []
                    for pos in data:
                        positions.append(
                            HummingbotPosition(
                                symbol=pos["symbol"],
                                side=pos["side"],
                                amount=pos["amount"],
                                entry_price=pos["entry_price"],
                                current_price=pos["current_price"],
                                pnl=pos["pnl"],
                                timestamp=datetime.fromisoformat(pos["timestamp"]),
                            )
                        )
                    return positions
                else:
                    logger.error(f"Failed to get positions: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    async def get_balance(self, bot_id: str) -> Dict[str, float]:
        """Get account balance"""
        try:
            async with self.session.get(
                f"{self.base_url}/bots/{bot_id}/balance", headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    logger.error(f"Failed to get balance: {response.status}")
                    return {}
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return {}

    async def get_performance(self, bot_id: str) -> Dict:
        """Get bot performance metrics"""
        try:
            async with self.session.get(
                f"{self.base_url}/bots/{bot_id}/performance",
                headers=self._get_headers(),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    logger.error(f"Failed to get performance: {response.status}")
                    return {}
        except Exception as e:
            logger.error(f"Error getting performance: {e}")
            return {}

    async def execute_dca_grid(
        self,
        bot_id: str,
        symbol: str,
        grid_orders: List[Dict],
        take_profit: float,
        stop_loss: float,
    ) -> bool:
        """Execute a DCA grid strategy"""
        try:
            # Place all grid orders
            for grid_order in grid_orders:
                order = HummingbotOrder(
                    symbol=symbol,
                    side="buy",
                    price=grid_order["price"],
                    amount=grid_order["size"],
                    order_type="limit",
                )
                await self.place_order(bot_id, order)

            # Set take profit and stop loss (this would need custom strategy implementation)
            logger.info(
                f"DCA grid executed for {symbol}: {len(grid_orders)} orders, TP: {take_profit}, SL: {stop_loss}"
            )
            return True

        except Exception as e:
            logger.error(f"Error executing DCA grid: {e}")
            return False


# Example usage
async def main():
    """Example of using the Hummingbot API client"""

    async with HummingbotAPIClient() as client:
        # Create a bot
        bot = await client.create_bot(
            bot_name="ml_dca_bot", exchange="binance_paper_trade"
        )

        if bot:
            bot_id = bot.get("id")

            # Place an order
            order = HummingbotOrder(
                symbol="BTC-USDT", side="buy", price=65000, amount=0.001
            )
            await client.place_order(bot_id, order)

            # Check positions
            positions = await client.get_positions(bot_id)
            for pos in positions:
                print(
                    f"Position: {pos.symbol} {pos.amount} @ {pos.entry_price}, PnL: {pos.pnl}"
                )

            # Get balance
            balance = await client.get_balance(bot_id)
            print(f"Balance: {balance}")


if __name__ == "__main__":
    asyncio.run(main())
