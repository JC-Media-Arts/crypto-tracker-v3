"""
Simple test to verify Hummingbot API paper trading works
"""

import asyncio
import aiohttp
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HummingbotAPITest:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.session = None
        
    async def test_api_connection(self):
        """Test basic API connection"""
        logger.info("=" * 60)
        logger.info("TESTING HUMMINGBOT API CONNECTION")
        logger.info("=" * 60)
        
        async with aiohttp.ClientSession() as session:
            # Test root endpoint
            async with session.get(f"{self.base_url}/") as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ API is running: {data}")
                else:
                    logger.error(f"❌ API not responding: {response.status}")
                    return False
                    
            # Test docs endpoint
            async with session.get(f"{self.base_url}/docs") as response:
                if response.status == 200:
                    logger.info("✅ API documentation available at http://localhost:8000/docs")
                else:
                    logger.error(f"❌ Docs not available: {response.status}")
                    
        return True
        
    async def test_available_endpoints(self):
        """Discover available API endpoints"""
        logger.info("\n" + "=" * 60)
        logger.info("DISCOVERING API ENDPOINTS")
        logger.info("=" * 60)
        
        # Common endpoints to test
        test_endpoints = [
            "/api/v1/accounts",
            "/api/v1/bots",
            "/api/v1/orders",
            "/api/v1/positions",
            "/api/v1/balance",
            "/accounts",
            "/bots",
            "/orders",
            "/positions",
            "/auth/token",
            "/auth/login"
        ]
        
        async with aiohttp.ClientSession() as session:
            for endpoint in test_endpoints:
                try:
                    async with session.get(f"{self.base_url}{endpoint}") as response:
                        if response.status == 200:
                            logger.info(f"✅ {endpoint} - Available")
                        elif response.status == 401:
                            logger.info(f"🔒 {endpoint} - Requires authentication")
                        elif response.status == 404:
                            logger.debug(f"❌ {endpoint} - Not found")
                        else:
                            logger.info(f"⚠️  {endpoint} - Status: {response.status}")
                except Exception as e:
                    logger.error(f"Error testing {endpoint}: {e}")
                    
    async def test_authentication(self):
        """Test authentication methods"""
        logger.info("\n" + "=" * 60)
        logger.info("TESTING AUTHENTICATION")
        logger.info("=" * 60)
        
        async with aiohttp.ClientSession() as session:
            # Try basic auth
            auth = aiohttp.BasicAuth('admin', 'admin')
            
            async with session.get(
                f"{self.base_url}/api/v1/accounts",
                auth=auth
            ) as response:
                if response.status == 200:
                    logger.info("✅ Basic auth successful")
                    data = await response.json()
                    logger.info(f"   Response: {data}")
                elif response.status == 404:
                    logger.info("⚠️  Endpoint not found with basic auth")
                else:
                    logger.info(f"❌ Basic auth failed: {response.status}")
                    
            # Try form-based auth
            async with session.post(
                f"{self.base_url}/auth/token",
                data={"username": "admin", "password": "admin"}
            ) as response:
                if response.status == 200:
                    logger.info("✅ Token auth successful")
                    data = await response.json()
                    logger.info(f"   Token: {data}")
                elif response.status == 404:
                    logger.info("⚠️  Token endpoint not found")
                else:
                    logger.info(f"❌ Token auth failed: {response.status}")
                    
    async def test_paper_trading_setup(self):
        """Test paper trading configuration"""
        logger.info("\n" + "=" * 60)
        logger.info("TESTING PAPER TRADING SETUP")
        logger.info("=" * 60)
        
        # Test creating a paper trading bot
        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth('admin', 'admin')
            
            # Try to create a bot
            bot_config = {
                "bot_name": "test_paper_bot",
                "exchange": "binance_paper_trade",
                "trading_pairs": ["BTC-USDT", "ETH-USDT"],
                "initial_balance": {
                    "USDT": 100000,
                    "BTC": 0,
                    "ETH": 0
                }
            }
            
            async with session.post(
                f"{self.base_url}/bots",
                json=bot_config,
                auth=auth
            ) as response:
                if response.status == 200:
                    logger.info("✅ Paper trading bot created")
                    data = await response.json()
                    logger.info(f"   Bot details: {data}")
                    return data
                elif response.status == 404:
                    logger.info("⚠️  Bot creation endpoint not found")
                else:
                    logger.info(f"❌ Failed to create bot: {response.status}")
                    try:
                        error = await response.text()
                        logger.info(f"   Error: {error}")
                    except:
                        pass
                        
        return None
        
    async def test_order_placement(self):
        """Test placing paper trading orders"""
        logger.info("\n" + "=" * 60)
        logger.info("TESTING ORDER PLACEMENT")
        logger.info("=" * 60)
        
        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth('admin', 'admin')
            
            # Test order
            order = {
                "symbol": "BTC-USDT",
                "side": "buy",
                "price": 65000,
                "amount": 0.001,
                "order_type": "limit"
            }
            
            # Try different order endpoints
            order_endpoints = [
                "/api/v1/orders",
                "/orders",
                "/api/v1/bots/test_bot/orders",
                "/bots/test_bot/orders"
            ]
            
            for endpoint in order_endpoints:
                async with session.post(
                    f"{self.base_url}{endpoint}",
                    json=order,
                    auth=auth
                ) as response:
                    if response.status == 200:
                        logger.info(f"✅ Order placed via {endpoint}")
                        data = await response.json()
                        logger.info(f"   Order: {data}")
                        break
                    elif response.status == 404:
                        logger.debug(f"   {endpoint} not found")
                    else:
                        logger.debug(f"   {endpoint} returned {response.status}")
                        
    async def run_all_tests(self):
        """Run all tests"""
        logger.info("\n" + "🚀 STARTING HUMMINGBOT API TESTS")
        logger.info("=" * 80)
        
        try:
            # Test connection
            if not await self.test_api_connection():
                logger.error("API connection failed. Is Hummingbot API running?")
                return
                
            # Discover endpoints
            await self.test_available_endpoints()
            
            # Test authentication
            await self.test_authentication()
            
            # Test paper trading
            bot = await self.test_paper_trading_setup()
            
            # Test orders
            await self.test_order_placement()
            
            logger.info("\n" + "=" * 80)
            logger.info("✅ TESTS COMPLETED")
            logger.info("=" * 80)
            
            logger.info("\n📝 NEXT STEPS:")
            logger.info("1. Check http://localhost:8000/docs for full API documentation")
            logger.info("2. Review which endpoints are available")
            logger.info("3. Configure authentication if needed")
            logger.info("4. Set up paper trading bots")
            
        except Exception as e:
            logger.error(f"Test error: {e}")
            import traceback
            traceback.print_exc()


async def main():
    tester = HummingbotAPITest()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
