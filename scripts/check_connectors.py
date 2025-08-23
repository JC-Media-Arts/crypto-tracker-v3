#!/usr/bin/env python3
"""Check available connectors for accounts"""

import asyncio
import aiohttp
from loguru import logger

async def check():
    base_url = "http://localhost:8000"
    auth = aiohttp.BasicAuth("admin", "changeme123")
    
    async with aiohttp.ClientSession() as session:
        # Get accounts
        async with session.get(f"{base_url}/accounts", auth=auth) as resp:
            if resp.status == 200:
                accounts = await resp.json()
                logger.info(f"Accounts: {accounts}")
            else:
                logger.error(f"Failed to get accounts: {resp.status}")
                
        # Get connectors  
        async with session.get(f"{base_url}/connectors", auth=auth) as resp:
            if resp.status == 200:
                connectors = await resp.json()
                logger.info(f"Available connectors: {connectors[:10]}")  # First 10
            else:
                logger.error(f"Failed to get connectors: {resp.status}")

asyncio.run(check())
