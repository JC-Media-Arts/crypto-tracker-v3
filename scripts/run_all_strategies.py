#!/usr/bin/env python3
"""
Run all trading strategies (DCA, SWING, CHANNEL)
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from loguru import logger

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.config.settings import get_settings  # noqa: E402
from src.data.hybrid_fetcher import HybridDataFetcher  # noqa: E402
from src.data.supabase_client import SupabaseClient  # noqa: E402
from src.strategies.channel.detector import ChannelDetector  # noqa: E402
from src.strategies.dca.detector import DCADetector  # noqa: E402
from src.strategies.swing.detector import SwingDetector  # noqa: E402


class AllStrategiesRunner:
    """Runs all three strategies continuously"""

    def __init__(self):
        """Initialize all strategy runners"""
        self.settings = get_settings()
        self.supabase = SupabaseClient()
        self.data_fetcher = HybridDataFetcher()  # HybridDataFetcher creates its own client

        # Initialize detectors
        self.dca_detector = DCADetector(self.supabase)
        self.swing_detector = SwingDetector(self.supabase)
        self.channel_detector = ChannelDetector()

        # Get symbols to monitor
        self.symbols = self.get_symbols()

        logger.info(f"Initialized strategy runner for {len(self.symbols)} symbols")

    def get_symbols(self) -> List[str]:
        """Get list of symbols to monitor"""
        # Get from settings or use defaults
        symbols = getattr(self.settings, "trading_symbols", None)

        if not symbols:
            # Use top symbols as default
            symbols = [
                "BTC",
                "ETH",
                "SOL",
                "BNB",
                "XRP",
                "ADA",
                "AVAX",
                "DOGE",
                "DOT",
                "POL",
                "LINK",
                "TON",
                "SHIB",
                "TRX",
                "UNI",
                "ATOM",
                "BCH",
                "APT",
                "NEAR",
                "ICP",
            ]

        return symbols

    async def run_dca_strategy(self):
        """Run DCA strategy scanning"""
        while True:
            try:
                logger.info("Running DCA strategy scan...")

                for symbol in self.symbols:
                    try:
                        # Get OHLC data for the symbol
                        ohlc_data = await self.data_fetcher.get_recent_data(
                            symbol=symbol,
                            hours=24,
                            timeframe="15m",  # Get last 24 hours of data
                        )

                        if ohlc_data:
                            # DCA detector has detect_setup method (not async)
                            setup = self.dca_detector.detect_setup(symbol, ohlc_data)

                            if setup and setup.get("signal_strength", 0) > 0:
                                logger.info(f"DCA setup detected for {symbol}: {setup}")

                                # Log to scan_history
                                await self.log_scan(
                                    strategy="DCA",
                                    symbol=symbol,
                                    signal_detected=True,
                                    confidence=setup.get("signal_strength", 0),
                                    metadata=setup,
                                )
                            else:
                                # Log negative scan
                                await self.log_scan(strategy="DCA", symbol=symbol, signal_detected=False)
                        else:
                            logger.warning(f"No data available for {symbol}")

                    except Exception as e:
                        logger.error(f"Error in DCA scan for {symbol}: {e}")

                # Wait before next scan
                await asyncio.sleep(60)  # Scan every minute

            except Exception as e:
                logger.error(f"Error in DCA strategy loop: {e}")
                await asyncio.sleep(60)

    async def run_swing_strategy(self):
        """Run SWING strategy scanning"""
        while True:
            try:
                logger.info("Running SWING strategy scan...")

                # SwingDetector has detect_setups method that takes a list
                setups = await self.swing_detector.detect_setups(self.symbols)

                if setups:
                    for setup in setups:
                        logger.info(f"SWING setup detected: {setup}")

                        # Log to scan_history
                        await self.log_scan(
                            strategy="SWING",
                            symbol=setup.get("symbol"),
                            signal_detected=True,
                            confidence=setup.get("score", 0) / 10.0,  # Convert score to 0-1
                            metadata=setup,
                        )

                # Log symbols that didn't have signals
                symbols_with_signals = {s.get("symbol") for s in setups} if setups else set()
                for symbol in self.symbols:
                    if symbol not in symbols_with_signals:
                        await self.log_scan(strategy="SWING", symbol=symbol, signal_detected=False)

                # Wait before next scan
                await asyncio.sleep(60)  # Scan every minute

            except Exception as e:
                logger.error(f"Error in SWING strategy loop: {e}")
                await asyncio.sleep(60)

    async def run_channel_strategy(self):
        """Run CHANNEL strategy scanning"""
        while True:
            try:
                logger.info("Running CHANNEL strategy scan...")

                for symbol in self.symbols:
                    try:
                        # Get OHLC data for the symbol
                        ohlc_data = await self.data_fetcher.get_recent_data(
                            symbol=symbol,
                            hours=24,
                            timeframe="15m",  # Get last 24 hours of data
                        )

                        if ohlc_data:
                            # ChannelDetector has detect_channel method
                            channel = self.channel_detector.detect_channel(symbol, ohlc_data)

                            if channel and channel.is_valid():
                                # Get trading signal
                                signal = self.channel_detector.get_trading_signal(channel)

                                if signal:
                                    logger.info(f"CHANNEL setup detected for {symbol}: {signal}")

                                    # Log to scan_history
                                    await self.log_scan(
                                        strategy="CHANNEL",
                                        symbol=symbol,
                                        signal_detected=True,
                                        confidence=channel.strength,
                                        metadata={
                                            "signal": signal,
                                            "channel_type": channel.channel_type(),
                                            "width": channel.width,
                                            "touches": channel.touches,
                                        },
                                    )
                                else:
                                    # Channel found but no signal
                                    await self.log_scan(
                                        strategy="CHANNEL",
                                        symbol=symbol,
                                        signal_detected=False,
                                        metadata={"channel_found": True},
                                    )
                            else:
                                # No valid channel found
                                await self.log_scan(
                                    strategy="CHANNEL",
                                    symbol=symbol,
                                    signal_detected=False,
                                )

                    except Exception as e:
                        logger.error(f"Error in CHANNEL scan for {symbol}: {e}")

                # Wait before next scan
                await asyncio.sleep(60)  # Scan every minute

            except Exception as e:
                logger.error(f"Error in CHANNEL strategy loop: {e}")
                await asyncio.sleep(60)

    async def log_scan(
        self,
        strategy: str,
        symbol: str,
        signal_detected: bool,
        confidence: float = 0.0,
        metadata: Dict = None,
    ):
        """Log scan to database"""
        try:
            data = {
                "strategy_name": strategy,
                "symbol": symbol,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "decision": "SIGNAL" if signal_detected else "SKIP",
                "reason": "signal_detected" if signal_detected else "no_setup_detected",
                "market_regime": "NORMAL",
                "features": json.dumps(metadata) if metadata else "{}",
                "ml_confidence": confidence if signal_detected else None,
                "confidence_score": confidence,
                "metadata": metadata or {},
            }

            # Try to insert into scan_history table
            try:
                self.supabase.client.table("scan_history").insert(data).execute()
            except Exception as scan_error:
                # Log error but continue - schema cache might need refresh
                if "schema cache" in str(scan_error):
                    logger.warning("Schema cache issue for scan_history, will retry later")
                else:
                    logger.error(f"Error inserting to scan_history: {scan_error}")

            # Also insert into shadow_testing_scans
            shadow_data = {
                "strategy_name": strategy,
                "symbol": symbol,
                "timeframe": "15m",
                "scan_time": datetime.now(timezone.utc).isoformat(),
                "signal_detected": signal_detected,
                "confidence": confidence,
                "metadata": metadata or {},
            }

            try:
                self.supabase.client.table("shadow_testing_scans").insert(shadow_data).execute()
            except Exception as shadow_error:
                # Log error but continue
                if "schema cache" in str(shadow_error):
                    logger.warning("Schema cache issue for shadow_testing_scans, will retry later")
                else:
                    logger.error(f"Error inserting to shadow_testing_scans: {shadow_error}")

        except Exception as e:
            logger.error(f"Unexpected error in log_scan: {e}")

    async def run_all(self):
        """Run all strategies concurrently"""
        logger.info("=" * 60)
        logger.info("STARTING ALL STRATEGY SCANNERS")
        logger.info(f"Time: {datetime.now(timezone.utc)}")
        logger.info(f"Monitoring {len(self.symbols)} symbols")
        logger.info("=" * 60)

        # Create tasks for all strategies
        tasks = [
            asyncio.create_task(self.run_dca_strategy()),
            asyncio.create_task(self.run_swing_strategy()),
            asyncio.create_task(self.run_channel_strategy()),
        ]

        # Run all tasks concurrently
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("Shutting down strategy scanners...")
            for task in tasks:
                task.cancel()
        except Exception as e:
            logger.error(f"Error in strategy runner: {e}")
            raise


async def main():
    """Main entry point"""
    runner = AllStrategiesRunner()
    await runner.run_all()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Strategy scanner stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
