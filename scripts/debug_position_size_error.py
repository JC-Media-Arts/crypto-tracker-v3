#!/usr/bin/env python3
"""
Debug script to find where position_size_multiplier error is occurring
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import asyncio
from loguru import logger
from src.strategies.manager import StrategyManager
from src.config.settings import Settings
from src.strategies.swing.detector import SwingDetector
from src.strategies.swing.analyzer import SwingAnalyzer
from src.data.supabase_client import SupabaseClient
import pandas as pd
import numpy as np
from datetime import datetime

async def test_full_flow():
    """Test the full flow to find where the error occurs"""
    
    # Initialize components
    settings = Settings()
    supabase = SupabaseClient(settings)
    
    # Create test data
    dates = pd.date_range(end=datetime.now(), periods=100, freq='15min')
    prices = np.random.randn(100).cumsum() + 100
    prices[-10:] = prices[-10:] * 1.03  # Create breakout
    
    test_data = pd.DataFrame({
        'timestamp': dates,
        'open': prices * 0.99,
        'high': prices * 1.01,
        'low': prices * 0.98,
        'close': prices,
        'volume': np.random.randint(1000, 10000, 100)
    })
    
    try:
        # Test 1: Direct SwingDetector
        logger.info("Testing SwingDetector directly...")
        detector = SwingDetector(supabase)
        setup = detector.detect_setup("TEST", test_data)
        if setup:
            logger.info(f"✅ SwingDetector setup has position_size_multiplier: {setup.get('position_size_multiplier', 'MISSING')}")
        
        # Test 2: Through StrategyManager
        logger.info("\nTesting through StrategyManager...")
        config = {
            "ml_enabled": False,
            "shadow_enabled": False,
            "swing_breakout_threshold": 2.0
        }
        manager = StrategyManager(config, settings)
        
        # Test swing detection
        market_data = {"TEST": test_data}
        signals = await manager._scan_swing_opportunities(market_data)
        
        logger.info(f"Found {len(signals)} signals")
        for signal in signals:
            logger.info(f"\nSignal attributes:")
            logger.info(f"  strategy_type: {signal.strategy_type}")
            logger.info(f"  symbol: {signal.symbol}")
            logger.info(f"  confidence: {signal.confidence}")
            logger.info(f"  setup_data keys: {list(signal.setup_data.keys())}")
            
            # Check the setup
            setup = signal.setup_data.get('setup', {})
            logger.info(f"  setup keys: {list(setup.keys())}")
            
            # Try to access position_size_multiplier
            try:
                # This might be where the error occurs
                multiplier = setup['position_size_multiplier']
                logger.info(f"  ✅ Direct access to position_size_multiplier: {multiplier}")
            except KeyError as e:
                logger.error(f"  ❌ KeyError on direct access: {e}")
            
            # Safe access
            multiplier_safe = setup.get('position_size_multiplier', 'NOT FOUND')
            logger.info(f"  Safe access to position_size_multiplier: {multiplier_safe}")
            
            # Check analysis if present
            analysis = signal.setup_data.get('analysis', {})
            if analysis:
                logger.info(f"  analysis keys: {list(analysis.keys())}")
                adj_mult = analysis.get('adjusted_size_multiplier', 'NOT FOUND')
                logger.info(f"  adjusted_size_multiplier: {adj_mult}")
        
    except Exception as e:
        logger.error(f"Error in test: {e}")
        import traceback
        logger.error(traceback.format_exc())

async def check_paper_trading_config():
    """Check if paper trading config is being used incorrectly"""
    logger.info("\nChecking paper trading config usage...")
    
    try:
        # Load the config
        from configs.paper_trading_config import PAPER_TRADING_CONFIG
        
        logger.info(f"Config has position_size_multiplier: {PAPER_TRADING_CONFIG.get('position_size_multiplier', 'NOT FOUND')}")
        
        # This might be where someone is trying to access it incorrectly
        try:
            # Wrong way - treating it as an object attribute
            multiplier = PAPER_TRADING_CONFIG.position_size_multiplier
            logger.error("❌ FOUND THE BUG: Config being accessed as object attribute!")
        except AttributeError:
            logger.info("✅ Config not being accessed as object attribute")
            
        # Check if it's being accessed as a string key
        try:
            # This would cause the error we're seeing
            multiplier = 'position_size_multiplier'
            value = PAPER_TRADING_CONFIG[multiplier]
            logger.info(f"✅ String key access works: {value}")
        except KeyError:
            logger.error("❌ String key access failed")
            
    except Exception as e:
        logger.error(f"Error checking config: {e}")

async def main():
    logger.info("=" * 60)
    logger.info("DEBUGGING position_size_multiplier ERROR")
    logger.info("=" * 60)
    
    await test_full_flow()
    await check_paper_trading_config()
    
    logger.info("\n" + "=" * 60)
    logger.info("Debug complete - check output for errors")

if __name__ == "__main__":
    asyncio.run(main())
