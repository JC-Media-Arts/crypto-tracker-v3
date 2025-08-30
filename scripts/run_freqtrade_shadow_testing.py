#!/usr/bin/env python3
"""
Freqtrade Shadow Testing Service
Creates and evaluates shadow variations for Freqtrade scans
Works without ML predictions initially
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime, timezone, timedelta
from loguru import logger

sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from src.analysis.shadow_evaluator import ShadowEvaluator
from src.analysis.shadow_logger import ShadowLogger
from src.config.config_loader import ConfigLoader


class FreqtradeShadowTesting:
    """Shadow testing service for Freqtrade integration"""
    
    def __init__(self):
        self.db = SupabaseClient()
        self.shadow_logger = ShadowLogger(self.db)
        self.shadow_evaluator = ShadowEvaluator(self.db.client)
        self.config_loader = ConfigLoader()
        
        # Service intervals
        self.monitor_interval = 60  # Check for new scans every minute
        self.evaluation_interval = 300  # Evaluate shadows every 5 minutes
        
        self.running = True
        self.stats = {
            "scans_processed": 0,
            "shadows_created": 0,
            "shadows_evaluated": 0,
            "start_time": datetime.now(timezone.utc)
        }
    
    async def create_shadow_variations(self, scan):
        """Create shadow variations for a Freqtrade scan"""
        try:
            symbol = scan.get("symbol")
            strategy = scan.get("strategy_name", "CHANNEL")
            
            # Get tier config for this symbol
            tier_config = self.config_loader.get_tier_config(symbol)
            base_params = self.config_loader.get_exit_params(strategy, symbol)
            
            # Create variations with different parameters
            variations = []
            
            # Conservative variation
            variations.append({
                "confidence_threshold": 0.70,
                "position_size_multiplier": 0.5,
                "take_profit_percentage": base_params.get("take_profit", 0.03) * 0.5,  # Half TP
                "stop_loss_percentage": base_params.get("stop_loss", 0.02) * 2,  # Double SL
                "trailing_stop_percentage": base_params.get("trailing_stop", 0.01),
                "variation_type": "conservative"
            })
            
            # Baseline variation (use config values)
            variations.append({
                "confidence_threshold": 0.60,
                "position_size_multiplier": 1.0,
                "take_profit_percentage": base_params.get("take_profit", 0.03),
                "stop_loss_percentage": base_params.get("stop_loss", 0.02),
                "trailing_stop_percentage": base_params.get("trailing_stop", 0.01),
                "variation_type": "baseline"
            })
            
            # Aggressive variation
            variations.append({
                "confidence_threshold": 0.50,
                "position_size_multiplier": 1.5,
                "take_profit_percentage": base_params.get("take_profit", 0.03) * 2,  # Double TP
                "stop_loss_percentage": base_params.get("stop_loss", 0.02) * 0.5,  # Half SL
                "trailing_stop_percentage": base_params.get("trailing_stop", 0.01) * 2,
                "variation_type": "aggressive"
            })
            
            # Risk-adjusted variations
            variations.append({
                "confidence_threshold": 0.65,
                "position_size_multiplier": 0.75,
                "take_profit_percentage": base_params.get("take_profit", 0.03) * 1.5,
                "stop_loss_percentage": base_params.get("stop_loss", 0.02) * 1.5,
                "trailing_stop_percentage": base_params.get("trailing_stop", 0.01) * 1.5,
                "variation_type": "risk_adjusted"
            })
            
            # Log shadows for this scan
            for params in variations:
                # Determine if this variation would take the trade
                # For now, without ML, base it on scan features
                features = scan.get("features", {})
                
                # Simple decision logic (will be replaced by ML later)
                would_trade = self._would_take_trade(features, params, strategy)
                
                # Create shadow variation
                await self.shadow_logger.log_shadow_decision(
                    scan_id=scan["scan_id"],
                    symbol=symbol,
                    strategy_name=strategy,
                    parameters=params,
                    would_take_trade=would_trade,
                    ml_predictions={},  # No ML predictions yet
                    decision={
                        "action": "BUY" if would_trade else "SKIP",
                        "reason": "Based on technical indicators",
                        "confidence": params["confidence_threshold"]
                    }
                )
            
            return len(variations)
            
        except Exception as e:
            logger.error(f"Error creating shadow variations: {e}")
            return 0
    
    def _would_take_trade(self, features, params, strategy):
        """Simple decision logic until ML is trained"""
        if not features:
            return False
        
        # For CHANNEL strategy, check Bollinger Band position
        if strategy == "CHANNEL":
            bb_position = features.get("bb_position", 0.5)
            rsi = features.get("rsi", 50)
            
            # Buy if near lower band and RSI oversold
            if bb_position < 0.25 and rsi < 35:
                # Check confidence threshold
                confidence = 0.7 - (bb_position * 0.2)  # Higher confidence at lower positions
                return confidence >= params["confidence_threshold"]
        
        return False
    
    async def monitor_scans(self):
        """Monitor for new Freqtrade scans and create shadows"""
        logger.info("Starting scan monitor...")
        
        last_scan_id = 0
        
        while self.running:
            try:
                # Get new scans since last check
                result = self.db.client.table("scan_history")\
                    .select("*")\
                    .gt("scan_id", last_scan_id)\
                    .order("scan_id")\
                    .limit(100)\
                    .execute()
                
                if result.data:
                    logger.info(f"Processing {len(result.data)} new scans...")
                    
                    for scan in result.data:
                        shadows_created = await self.create_shadow_variations(scan)
                        
                        if shadows_created > 0:
                            self.stats["scans_processed"] += 1
                            self.stats["shadows_created"] += shadows_created
                        
                        last_scan_id = max(last_scan_id, scan["scan_id"])
                    
                    # Flush shadow logger buffer
                    await self.shadow_logger.flush()
                    
                    logger.info(
                        f"Progress: {self.stats['scans_processed']} scans, "
                        f"{self.stats['shadows_created']} shadows created"
                    )
                
            except Exception as e:
                logger.error(f"Error in scan monitor: {e}")
            
            await asyncio.sleep(self.monitor_interval)
    
    async def evaluate_shadows(self):
        """Evaluate pending shadow trades"""
        logger.info("Starting shadow evaluator...")
        
        while self.running:
            try:
                # Let shadows age for 5 minutes before evaluation
                await asyncio.sleep(self.evaluation_interval)
                
                # Evaluate pending shadows
                outcomes = await self.shadow_evaluator.evaluate_pending_shadows()
                
                if outcomes:
                    self.stats["shadows_evaluated"] += len(outcomes)
                    
                    # Log results
                    wins = sum(1 for o in outcomes if o.outcome_status == "WIN")
                    losses = sum(1 for o in outcomes if o.outcome_status == "LOSS")
                    
                    logger.info(
                        f"Evaluated {len(outcomes)} shadows: "
                        f"{wins} wins, {losses} losses"
                    )
                
            except Exception as e:
                logger.error(f"Error in shadow evaluator: {e}")
    
    async def log_stats(self):
        """Log statistics periodically"""
        while self.running:
            await asyncio.sleep(3600)  # Every hour
            
            runtime = datetime.now(timezone.utc) - self.stats["start_time"]
            hours = runtime.total_seconds() / 3600
            
            logger.info("="*60)
            logger.info("SHADOW TESTING STATISTICS")
            logger.info("="*60)
            logger.info(f"Runtime: {hours:.1f} hours")
            logger.info(f"Scans processed: {self.stats['scans_processed']:,}")
            logger.info(f"Shadows created: {self.stats['shadows_created']:,}")
            logger.info(f"Shadows evaluated: {self.stats['shadows_evaluated']:,}")
            
            if self.stats["scans_processed"] > 0:
                avg_shadows = self.stats["shadows_created"] / self.stats["scans_processed"]
                logger.info(f"Average shadows per scan: {avg_shadows:.1f}")
            
            logger.info("="*60)
    
    async def run(self):
        """Run all shadow testing services"""
        logger.info("="*60)
        logger.info("FREQTRADE SHADOW TESTING SERVICE STARTING")
        logger.info("="*60)
        
        # Create tasks
        tasks = [
            asyncio.create_task(self.monitor_scans()),
            asyncio.create_task(self.evaluate_shadows()),
            asyncio.create_task(self.log_stats())
        ]
        
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("Shutting down shadow testing service...")
            self.running = False


async def main():
    """Main entry point"""
    service = FreqtradeShadowTesting()
    await service.run()


if __name__ == "__main__":
    asyncio.run(main())
