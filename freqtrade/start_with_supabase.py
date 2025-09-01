#!/usr/bin/env python3
"""
Custom Freqtrade startup script that uses Supabase data provider
This replaces the need to download data from exchanges
"""

import sys
import os
from pathlib import Path

# Add user_data to path for imports
sys.path.insert(0, str(Path(__file__).parent / "user_data"))

# Import Freqtrade components
from freqtrade.main import main
from freqtrade.commands import Arguments
from freqtrade.configuration import Configuration
from loguru import logger

# Import our custom data provider
from custom_dataprovider import CustomDataProvider


def start_freqtrade_with_supabase():
    """
    Start Freqtrade with custom Supabase data provider
    """
    
    # Set up arguments for Freqtrade
    args = [
        'trade',
        '--config', 'config/config.json',
        '--strategy', 'ChannelStrategyV1',
        '--strategy-path', 'user_data/strategies',
        '--dry-run',
        '--logfile', 'user_data/logs/freqtrade.log'
    ]
    
    logger.info("🚀 Starting Freqtrade with Supabase data provider")
    logger.info(f"Environment: SUPABASE_URL={os.getenv('SUPABASE_URL', 'Not set')[:50]}...")
    logger.info(f"Environment: SUPABASE_KEY={'Set' if os.getenv('SUPABASE_KEY') else 'Not set'}")
    
    try:
        # Parse arguments
        arguments = Arguments(args)
        args = arguments.get_parsed_arg()
        
        # Load configuration
        configuration = Configuration(args, None)
        config = configuration.get_config()
        
        # Override the data provider in config
        # This tells Freqtrade to use our custom provider
        config['dataformat_ohlcv'] = 'json'  # Keep this for compatibility
        config['dataformat_trades'] = 'jsongz'
        
        # Add custom flag to indicate we're using Supabase
        config['use_custom_dataprovider'] = True
        
        logger.info("✅ Configuration loaded successfully")
        logger.info(f"📊 Trading pairs: {config['exchange']['pair_whitelist']}")
        logger.info(f"⏰ Timeframe: {config.get('timeframe', '5m')}")
        
        # Start Freqtrade
        from freqtrade.worker import Worker
        
        # Create worker with custom configuration
        worker = Worker(args=args, config=config)
        
        # Monkey-patch the data provider initialization
        original_init = worker._init_modules
        
        def custom_init_modules():
            """Custom initialization that uses our data provider"""
            original_init()
            
            # Replace the data provider with our custom one
            if hasattr(worker, 'freqtrade'):
                logger.info("🔄 Replacing data provider with Supabase provider...")
                worker.freqtrade.dataprovider = CustomDataProvider(
                    config=config,
                    exchange=worker.freqtrade.exchange if hasattr(worker.freqtrade, 'exchange') else None,
                    pairlists=worker.freqtrade.pairlists if hasattr(worker.freqtrade, 'pairlists') else None,
                    rpc=worker.freqtrade.rpc if hasattr(worker.freqtrade, 'rpc') else None
                )
                logger.info("✅ Custom data provider installed")
                
        worker._init_modules = custom_init_modules
        
        # Run the worker
        logger.info("🎯 Starting Freqtrade worker...")
        worker.run()
        
    except KeyboardInterrupt:
        logger.info("👋 Freqtrade stopped by user")
        return 0
    except Exception as e:
        logger.error(f"❌ Error starting Freqtrade: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(start_freqtrade_with_supabase())
