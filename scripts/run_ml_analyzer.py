#!/usr/bin/env python3
"""
ML Analyzer Service - Research & Development System
Analyzes scan history and generates ML predictions offline
Part of the Research module - completely separate from Trading
"""

import asyncio
import os
import sys
import pickle
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, List
import pandas as pd
import numpy as np
from loguru import logger

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient  # noqa: E402
from src.config.settings import Settings  # noqa: E402

# Force research mode
os.environ["RESEARCH_MODE"] = "true"
os.environ["DB_ACCESS_MODE"] = "read_only"


class MLAnalyzer:
    """
    Analyzes trading patterns and generates ML predictions offline
    Read-only access to trading data
    """

    def __init__(self):
        """Initialize ML Analyzer"""
        self.settings = Settings()
        self.db = SupabaseClient()
        self.models = {}
        self.analysis_interval = 300  # Run every 5 minutes
        self.lookback_hours = 24  # Analyze last 24 hours

        # Load ML models
        self._load_models()

        logger.info("ML Analyzer initialized in RESEARCH mode")
        logger.info("Database access: READ-ONLY")

    def _load_models(self):
        """Load trained ML models"""
        model_dir = Path("models")

        # Load DCA model
        dca_model_path = model_dir / "dca" / "xgboost_multi_output.pkl"
        if dca_model_path.exists():
            with open(dca_model_path, "rb") as f:
                self.models["DCA"] = pickle.load(f)
            logger.info("Loaded DCA model")

        # Load Swing model
        swing_model_path = model_dir / "swing" / "swing_classifier.pkl"
        if swing_model_path.exists():
            with open(swing_model_path, "rb") as f:
                self.models["SWING"] = pickle.load(f)
            logger.info("Loaded SWING model")

        # Load Channel model
        channel_model_path = model_dir / "channel" / "classifier.pkl"
        if channel_model_path.exists():
            with open(channel_model_path, "rb") as f:
                self.models["CHANNEL"] = pickle.load(f)
            logger.info("Loaded CHANNEL model")

    async def analyze_scan_history(self):
        """Analyze recent scan history and generate predictions"""
        try:
            # Get recent scans (READ-ONLY)
            cutoff_time = (
                datetime.now(timezone.utc) - timedelta(hours=self.lookback_hours)
            ).isoformat()

            scans = (
                self.db.client.table("scan_history")
                .select(
                    "scan_id, timestamp, symbol, strategy_name, decision, features, "
                    "ml_confidence, setup_data, market_regime, btc_price"
                )
                .gte("timestamp", cutoff_time)
                .order("timestamp", desc=True)
                .execute()
            )

            if not scans.data:
                logger.info("No recent scans to analyze")
                return

            logger.info(
                f"Analyzing {len(scans.data)} scans from last {self.lookback_hours} hours"
            )

            # Group by strategy for analysis
            scans_df = pd.DataFrame(scans.data)

            analysis_results = []

            for strategy in ["DCA", "SWING", "CHANNEL"]:
                strategy_scans = scans_df[scans_df["strategy_name"] == strategy]

                if len(strategy_scans) > 0 and strategy in self.models:
                    results = await self._analyze_strategy(strategy, strategy_scans)
                    analysis_results.extend(results)

            # Save analysis results
            if analysis_results:
                await self._save_analysis(analysis_results)
                logger.info(f"Saved {len(analysis_results)} analysis results")

            # Generate summary statistics
            await self._generate_summary_stats(scans_df, analysis_results)

        except Exception as e:
            logger.error(f"Error analyzing scan history: {e}")

    async def _analyze_strategy(
        self, strategy: str, scans_df: pd.DataFrame
    ) -> List[Dict]:
        """Analyze scans for a specific strategy"""
        results = []
        model = self.models[strategy]

        for _, scan in scans_df.iterrows():
            try:
                # Parse features
                features = scan["features"]
                if isinstance(features, str):
                    features = json.loads(features)

                # Generate ML prediction
                prediction = self._generate_ml_prediction(model, features, strategy)

                # Compare with actual decision
                accuracy_analysis = self._analyze_accuracy(
                    scan["decision"],
                    scan.get("ml_confidence") or 0,  # Handle None
                    prediction["confidence"],
                )

                # Create analysis record
                analysis = {
                    "scan_id": scan["scan_id"],
                    "timestamp": scan["timestamp"],
                    "symbol": scan["symbol"],
                    "strategy": strategy,
                    "original_decision": scan["decision"],
                    "original_confidence": scan.get("ml_confidence", 0),
                    "research_prediction": prediction,
                    "accuracy_analysis": accuracy_analysis,
                    "market_regime": scan.get("market_regime", "NORMAL"),
                    "btc_price": scan.get("btc_price", 0),
                }

                results.append(analysis)

            except Exception as e:
                logger.debug(f"Error analyzing scan {scan.get('scan_id')}: {e}")
                continue

        return results

    def _generate_ml_prediction(self, model, features: Dict, strategy: str) -> Dict:
        """Generate ML prediction for given features"""
        try:
            # Prepare feature vector based on strategy
            if strategy == "DCA":
                feature_vector = self._prepare_dca_features(features)
                # DCA has multi-output model
                predictions = model.predict(feature_vector.reshape(1, -1))

                return {
                    "confidence": float(predictions[0][0])
                    if len(predictions) > 0
                    else 0.5,
                    "take_profit": float(predictions[0][1])
                    if len(predictions) > 0
                    else 10.0,
                    "stop_loss": float(predictions[0][2])
                    if len(predictions) > 0
                    else 5.0,
                    "position_size_mult": float(predictions[0][3])
                    if len(predictions) > 0
                    else 1.0,
                    "hold_hours": float(predictions[0][4])
                    if len(predictions) > 0
                    else 48,
                }

            elif strategy == "SWING":
                feature_vector = self._prepare_swing_features(features)
                confidence = model.predict_proba(feature_vector.reshape(1, -1))[0][1]

                return {
                    "confidence": float(confidence),
                    "take_profit": 15.0,  # Default for swing
                    "stop_loss": 5.0,
                    "position_size_mult": 1.0,
                    "hold_hours": 48,
                }

            elif strategy == "CHANNEL":
                feature_vector = self._prepare_channel_features(features)
                confidence = model.predict_proba(feature_vector.reshape(1, -1))[0][1]

                return {
                    "confidence": float(confidence),
                    "take_profit": 5.0,  # Default for channel
                    "stop_loss": 3.0,
                    "position_size_mult": 1.0,
                    "hold_hours": 24,
                }

        except Exception as e:
            logger.debug(f"Error generating prediction: {e}")
            return {
                "confidence": 0.5,
                "take_profit": 10.0,
                "stop_loss": 5.0,
                "position_size_mult": 1.0,
                "hold_hours": 48,
            }

    def _prepare_dca_features(self, features: Dict) -> np.ndarray:
        """Prepare feature vector for DCA model - matching training features"""
        # Must match the 22 features from models/dca/features.json

        # Get current datetime for time features
        now = datetime.now()

        # Market regime mapping
        regime = features.get("market_regime", "NORMAL")
        btc_regime = 1 if regime == "BEAR" else (2 if regime == "BULL" else 0)

        feature_vector = [
            features.get("volume", 1000000),  # volume
            features.get("volume_ratio", 1.0),  # volume_ratio
            features.get("threshold", 5.0),  # threshold (DCA drop)
            1,  # market_cap_tier (default to 1 - mid cap)
            btc_regime,  # btc_regime (0=normal, 1=bear, 2=bull)
            features.get("btc_price", 50000),  # btc_price
            features.get("btc_price", 50000),  # btc_sma50 (approximate)
            features.get("btc_price", 50000),  # btc_sma200 (approximate)
            0,  # btc_sma50_distance
            0,  # btc_sma200_distance
            0.5,  # btc_trend_strength
            0.1,  # btc_volatility_7d
            0.1,  # btc_volatility_30d
            0.05,  # btc_high_low_range_7d
            features.get("btc_correlation", 0),  # symbol_vs_btc_7d
            features.get("btc_correlation", 0),  # symbol_vs_btc_30d
            features.get("btc_correlation", 0.5),  # symbol_correlation_30d
            1 if features.get("volatility", 0.1) > 0.15 else 0,  # is_high_volatility
            1 if features.get("rsi", 50) < 30 else 0,  # is_oversold
            1 if features.get("rsi", 50) > 70 else 0,  # is_overbought
            now.weekday(),  # day_of_week (0-6)
            now.hour,  # hour (0-23)
        ]
        return np.array(feature_vector)

    def _prepare_swing_features(self, features: Dict) -> np.ndarray:
        """Prepare feature vector for Swing model"""
        feature_vector = [
            features.get("breakout_strength", 0),
            features.get("volume_ratio", 1),
            features.get("rsi", 50),
            features.get("macd_signal", 0),
            features.get("trend_strength", 0),
            features.get("resistance_distance", 0),
        ]
        return np.array(feature_vector)

    def _prepare_channel_features(self, features: Dict) -> np.ndarray:
        """Prepare feature vector for Channel model"""
        feature_vector = [
            features.get("channel_position", 0.5),
            features.get("range_width", 0),
            features.get("touches_count", 0),
            features.get("volume_profile", 1),
            features.get("time_in_range", 0),
        ]
        return np.array(feature_vector)

    def _analyze_accuracy(
        self, actual_decision: str, original_conf: float, research_conf: float
    ) -> Dict:
        """Analyze prediction accuracy"""
        threshold = 0.60  # Standard confidence threshold

        # What would research model have done?
        research_decision = "BUY" if research_conf >= threshold else "SKIP"

        # Compare decisions
        agreed = actual_decision == research_decision

        # Calculate confidence delta
        conf_delta = research_conf - original_conf

        return {
            "decisions_agreed": agreed,
            "confidence_delta": conf_delta,
            "research_would_trade": research_decision == "BUY",
            "actual_traded": actual_decision == "BUY",
            "confidence_improvement": conf_delta > 0.05,
        }

    async def _save_analysis(self, results: List[Dict]):
        """Save analysis results to database using existing ml_predictions table"""
        try:
            # Use the existing ml_predictions table with its simple schema
            records = []

            for result in results:
                # Determine if ML would go UP (buy) or DOWN (skip)
                ml_would_buy = result["research_prediction"]["confidence"] >= 0.6

                # Map to the actual ml_predictions schema (simple UP/DOWN)
                record = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "symbol": result["symbol"],
                    "prediction": "UP" if ml_would_buy else "DOWN",
                    "confidence": min(
                        result["research_prediction"]["confidence"], 0.99
                    ),  # Cap at 0.99
                    "model_version": f"{result['strategy']}_analyzer_v1",
                }

                records.append(record)

            # Save to existing ml_predictions table
            if records:
                self.db.client.table("ml_predictions").insert(records).execute()
                logger.info(f"Saved {len(records)} ML predictions to database")

        except Exception as e:
            logger.error(f"Error saving analysis: {e}")

    async def _generate_summary_stats(
        self, scans_df: pd.DataFrame, analysis_results: List[Dict]
    ):
        """Generate and log summary statistics"""
        try:
            total_scans = len(scans_df)
            total_analyzed = len(analysis_results)

            if total_analyzed == 0:
                return

            # Calculate agreement rate
            agreements = sum(
                1
                for r in analysis_results
                if r["accuracy_analysis"]["decisions_agreed"]
            )
            agreement_rate = agreements / total_analyzed * 100

            # Calculate average confidence improvement
            conf_improvements = [
                r["accuracy_analysis"]["confidence_delta"] for r in analysis_results
            ]
            avg_conf_improvement = np.mean(conf_improvements)

            # Strategy breakdown
            strategy_stats = {}
            for strategy in ["DCA", "SWING", "CHANNEL"]:
                strategy_results = [
                    r for r in analysis_results if r["strategy"] == strategy
                ]
                if strategy_results:
                    strategy_agreements = sum(
                        1
                        for r in strategy_results
                        if r["accuracy_analysis"]["decisions_agreed"]
                    )
                    strategy_stats[strategy] = {
                        "total": len(strategy_results),
                        "agreement_rate": strategy_agreements
                        / len(strategy_results)
                        * 100,
                    }

            # Log summary
            logger.info("=" * 60)
            logger.info("ML ANALYSIS SUMMARY")
            logger.info("=" * 60)
            logger.info(f"Period: Last {self.lookback_hours} hours")
            logger.info(f"Total scans: {total_scans}")
            logger.info(f"Analyzed: {total_analyzed}")
            logger.info(f"Agreement rate: {agreement_rate:.1f}%")
            logger.info(f"Avg confidence improvement: {avg_conf_improvement:+.3f}")

            for strategy, stats in strategy_stats.items():
                logger.info(
                    f"{strategy}: {stats['total']} scans, "
                    f"{stats['agreement_rate']:.1f}% agreement"
                )

            logger.info("=" * 60)

            # Skip saving to daily_performance for now (schema mismatch)
            # This table is primarily for trading performance, not ML analysis
            logger.debug(
                f"ML Analysis complete - Agreement rate: {agreement_rate:.1f}%"
            )

        except Exception as e:
            logger.error(f"Error generating summary: {e}")

    async def check_prediction_accuracy(self):
        """Check accuracy of past predictions against actual outcomes"""
        try:
            # Get trades that have completed in last 24 hours
            cutoff_time = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

            completed_trades = (
                self.db.client.table("paper_trades")
                .select("trade_id, symbol, strategy_name, created_at, status, pnl")
                .gte("created_at", cutoff_time)
                .in_("status", ["CLOSED", "STOPPED"])
                .execute()
            )

            if not completed_trades.data:
                logger.info("No completed trades to evaluate")
                return

            logger.info(f"Evaluating {len(completed_trades.data)} completed trades")

            # TODO: Match trades with predictions and calculate accuracy
            # This will be implemented once we have ml_analysis_results populated

        except Exception as e:
            logger.error(f"Error checking prediction accuracy: {e}")

    async def run(self):
        """Main run loop"""
        logger.info("Starting ML Analyzer Service")
        logger.info(f"Analysis interval: {self.analysis_interval} seconds")
        logger.info(f"Lookback period: {self.lookback_hours} hours")

        while True:
            try:
                start_time = datetime.now()

                # Run analysis
                await self.analyze_scan_history()

                # Check prediction accuracy
                await self.check_prediction_accuracy()

                # Calculate processing time
                processing_time = (datetime.now() - start_time).total_seconds()
                logger.info(
                    f"Analysis cycle completed in {processing_time:.1f} seconds"
                )

                # Wait for next cycle
                await asyncio.sleep(self.analysis_interval)

            except KeyboardInterrupt:
                logger.info("ML Analyzer stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(60)  # Wait a minute before retrying


async def main():
    """Main entry point"""
    analyzer = MLAnalyzer()
    await analyzer.run()


if __name__ == "__main__":
    # Configure logging
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
        "<level>{message}</level>",
        level="INFO",
    )

    # Add file logging
    logger.add(
        "logs/ml_analyzer.log", rotation="1 day", retention="7 days", level="DEBUG"
    )

    logger.info("=" * 60)
    logger.info("ML ANALYZER - RESEARCH & DEVELOPMENT SYSTEM")
    logger.info("Mode: READ-ONLY Research")
    logger.info("=" * 60)

    # Run the analyzer
    asyncio.run(main())
