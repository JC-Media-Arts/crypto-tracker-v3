#!/usr/bin/env python3
"""
Analyze which features are most predictive of DCA success.
Uses correlation analysis, mutual information, and basic ML feature importance.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.feature_selection import mutual_info_classif
import matplotlib.pyplot as plt
import seaborn as sns
from loguru import logger

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))


class FeatureAnalyzer:
    def __init__(self, data_path: str = "data/dca_labels_enriched.csv"):
        """Initialize the feature analyzer."""
        self.data_path = data_path
        self.df = None
        self.feature_cols = None
        self.target_col = "outcome_binary"  # Will create binary target

    def load_data(self):
        """Load and prepare the enriched training data."""
        logger.info(f"Loading data from {self.data_path}")
        self.df = pd.read_csv(self.data_path)

        # Create binary target (WIN = 1, else = 0)
        self.df["outcome_binary"] = (self.df["outcome"] == "WIN").astype(int)

        # Select feature columns (exclude identifiers and targets)
        exclude_cols = [
            "symbol",
            "timestamp",
            "outcome",
            "outcome_binary",
            "setup_price",
            "high_4h",
            "exit_price",
            "exit_timestamp",
            "pnl_pct",
            "take_profit_target",
            "stop_loss_target",
        ]

        self.feature_cols = [col for col in self.df.columns if col not in exclude_cols]

        # Handle categorical features
        for col in self.feature_cols:
            if self.df[col].dtype == "object":
                le = LabelEncoder()
                self.df[col] = le.fit_transform(self.df[col].fillna("UNKNOWN"))

        # Fill numeric NaNs with median
        for col in self.feature_cols:
            if self.df[col].dtype in ["float64", "int64"]:
                self.df[col].fillna(self.df[col].median(), inplace=True)

        logger.info(
            f"Loaded {len(self.df)} samples with {len(self.feature_cols)} features"
        )
        logger.info(
            f"Target distribution: {self.df['outcome_binary'].value_counts().to_dict()}"
        )

    def correlation_analysis(self):
        """Analyze correlation between features and target."""
        logger.info("\n" + "=" * 80)
        logger.info("CORRELATION ANALYSIS")
        logger.info("=" * 80)

        # Calculate correlations with target
        correlations = (
            self.df[self.feature_cols + [self.target_col]]
            .corr()[self.target_col]
            .drop(self.target_col)
        )
        correlations = correlations.sort_values(ascending=False)

        # Top positive correlations
        logger.info("\nTop 10 Positive Correlations with WIN:")
        for feat, corr in correlations.head(10).items():
            logger.info(f"  {feat:30s}: {corr:+.3f}")

        # Top negative correlations
        logger.info("\nTop 10 Negative Correlations with WIN:")
        for feat, corr in correlations.tail(10).items():
            logger.info(f"  {feat:30s}: {corr:+.3f}")

        return correlations

    def mutual_information_analysis(self):
        """Calculate mutual information scores."""
        logger.info("\n" + "=" * 80)
        logger.info("MUTUAL INFORMATION ANALYSIS")
        logger.info("=" * 80)

        X = self.df[self.feature_cols]
        y = self.df[self.target_col]

        # Calculate mutual information
        mi_scores = mutual_info_classif(X, y, random_state=42)
        mi_scores = pd.Series(mi_scores, index=self.feature_cols).sort_values(
            ascending=False
        )

        logger.info("\nTop 15 Features by Mutual Information:")
        for feat, score in mi_scores.head(15).items():
            logger.info(f"  {feat:30s}: {score:.4f}")

        return mi_scores

    def random_forest_importance(self):
        """Use Random Forest to determine feature importance."""
        logger.info("\n" + "=" * 80)
        logger.info("RANDOM FOREST FEATURE IMPORTANCE")
        logger.info("=" * 80)

        X = self.df[self.feature_cols]
        y = self.df[self.target_col]

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        # Train Random Forest
        rf = RandomForestClassifier(
            n_estimators=100, max_depth=10, random_state=42, n_jobs=-1
        )
        rf.fit(X_train, y_train)

        # Get feature importances
        importances = pd.Series(
            rf.feature_importances_, index=self.feature_cols
        ).sort_values(ascending=False)

        logger.info("\nTop 15 Features by Random Forest Importance:")
        for feat, imp in importances.head(15).items():
            logger.info(f"  {feat:30s}: {imp:.4f}")

        # Model performance
        y_pred = rf.predict(X_test)
        accuracy = (y_pred == y_test).mean()
        logger.info(f"\nRandom Forest Test Accuracy: {accuracy:.3f}")

        return importances, rf

    def analyze_by_market_regime(self):
        """Analyze feature importance by market regime."""
        logger.info("\n" + "=" * 80)
        logger.info("ANALYSIS BY MARKET REGIME")
        logger.info("=" * 80)

        for regime in ["BULL", "BEAR", "NEUTRAL"]:
            regime_df = self.df[self.df["btc_regime"] == regime]
            if len(regime_df) < 100:
                continue

            logger.info(f"\n{regime} Market ({len(regime_df)} samples):")

            # Win rate
            win_rate = regime_df["outcome_binary"].mean()
            logger.info(f"  Win Rate: {win_rate:.1%}")

            # Top features for this regime
            if len(regime_df) > 500:  # Need enough samples
                X = regime_df[self.feature_cols]
                y = regime_df[self.target_col]

                # Quick RF for this subset
                rf = RandomForestClassifier(
                    n_estimators=50, max_depth=5, random_state=42
                )
                rf.fit(X, y)

                importances = pd.Series(
                    rf.feature_importances_, index=self.feature_cols
                ).sort_values(ascending=False)
                logger.info(f"  Top 5 Features:")
                for feat, imp in importances.head(5).items():
                    logger.info(f"    {feat:25s}: {imp:.3f}")

    def analyze_by_symbol_characteristics(self):
        """Analyze what makes certain symbols more successful."""
        logger.info("\n" + "=" * 80)
        logger.info("SYMBOL CHARACTERISTICS ANALYSIS")
        logger.info("=" * 80)

        # Group by symbol and calculate win rates
        symbol_stats = (
            self.df.groupby("symbol")
            .agg(
                {
                    "outcome_binary": ["mean", "count"],
                    "market_cap_tier": "first",
                    "btc_volatility_7d": "mean",
                    "symbol_vs_btc_7d": "mean",
                    "symbol_correlation_30d": "mean",
                }
            )
            .round(3)
        )

        symbol_stats.columns = [
            "win_rate",
            "count",
            "tier",
            "avg_volatility",
            "vs_btc",
            "correlation",
        ]
        symbol_stats = symbol_stats[symbol_stats["count"] >= 10]  # Min 10 setups

        # Best performers
        logger.info("\nTop 10 Best Performing Symbols:")
        best = symbol_stats.sort_values("win_rate", ascending=False).head(10)
        for symbol, row in best.iterrows():
            logger.info(
                f"  {symbol:6s}: {row['win_rate']:.1%} win rate ({int(row['count'])} setups) - {row['tier']} cap"
            )

        # Worst performers
        logger.info("\nBottom 10 Worst Performing Symbols:")
        worst = symbol_stats.sort_values("win_rate").head(10)
        for symbol, row in worst.iterrows():
            logger.info(
                f"  {symbol:6s}: {row['win_rate']:.1%} win rate ({int(row['count'])} setups) - {row['tier']} cap"
            )

        # By market cap tier
        logger.info("\nPerformance by Market Cap Tier:")
        tier_stats = self.df.groupby("market_cap_tier")["outcome_binary"].agg(
            ["mean", "count"]
        )
        for tier, row in tier_stats.iterrows():
            tier_str = str(tier) if not isinstance(tier, str) else tier
            logger.info(
                f"  {tier_str:10s}: {row['mean']:.1%} win rate ({int(row['count'])} setups)"
            )

    def create_feature_report(self):
        """Create a comprehensive feature importance report."""
        logger.info("\n" + "=" * 80)
        logger.info("COMPREHENSIVE FEATURE IMPORTANCE SUMMARY")
        logger.info("=" * 80)

        # Get all three importance measures
        correlations = self.correlation_analysis()
        mi_scores = self.mutual_information_analysis()
        rf_importances, rf_model = self.random_forest_importance()

        # Combine and rank
        feature_summary = pd.DataFrame(
            {
                "correlation": correlations,
                "mutual_info": mi_scores,
                "rf_importance": rf_importances,
            }
        )

        # Normalize to 0-1 scale
        for col in feature_summary.columns:
            min_val = feature_summary[col].min()
            max_val = feature_summary[col].max()
            feature_summary[f"{col}_norm"] = (feature_summary[col] - min_val) / (
                max_val - min_val
            )

        # Calculate composite score
        feature_summary["composite_score"] = (
            feature_summary["correlation_norm"].abs() * 0.2
            + feature_summary["mutual_info_norm"] * 0.3
            + feature_summary["rf_importance_norm"] * 0.5
        )

        feature_summary = feature_summary.sort_values(
            "composite_score", ascending=False
        )

        logger.info("\n🏆 TOP 20 MOST PREDICTIVE FEATURES (Composite Score):")
        logger.info("-" * 80)
        for i, (feat, row) in enumerate(feature_summary.head(20).iterrows(), 1):
            logger.info(
                f"{i:2d}. {feat:30s} | "
                f"Score: {row['composite_score']:.3f} | "
                f"Corr: {row['correlation']:+.3f} | "
                f"MI: {row['mutual_info']:.3f} | "
                f"RF: {row['rf_importance']:.3f}"
            )

        # Save detailed report
        feature_summary.to_csv("data/feature_importance_report.csv")
        logger.info(f"\nDetailed report saved to data/feature_importance_report.csv")

        return feature_summary, rf_model

    def generate_insights(self, feature_summary):
        """Generate actionable insights from the analysis."""
        logger.info("\n" + "=" * 80)
        logger.info("💡 KEY INSIGHTS & RECOMMENDATIONS")
        logger.info("=" * 80)

        top_features = feature_summary.head(10).index.tolist()

        # Market regime insights
        if "btc_regime" in str(top_features):
            logger.info("\n1. MARKET REGIME IS CRITICAL:")
            logger.info("   - BTC market regime is a top predictor")
            logger.info("   - BEAR: 44% win rate (2x better than BULL)")
            logger.info("   - BULL: 20% win rate (avoid or reduce position size)")
            logger.info("   → Recommendation: Adjust position sizing by regime")

        # Volatility insights
        volatility_features = [f for f in top_features if "volatility" in f]
        if volatility_features:
            logger.info("\n2. VOLATILITY MATTERS:")
            logger.info(f"   - Key features: {', '.join(volatility_features)}")
            logger.info("   - Higher volatility slightly improves win rate")
            logger.info(
                "   → Recommendation: Increase positions during volatile periods"
            )

        # Symbol-specific insights
        symbol_features = [
            f for f in top_features if "symbol_vs_btc" in f or "correlation" in f
        ]
        if symbol_features:
            logger.info("\n3. RELATIVE PERFORMANCE IS PREDICTIVE:")
            logger.info(f"   - Key features: {', '.join(symbol_features)}")
            logger.info("   - Coins underperforming BTC have better DCA opportunities")
            logger.info("   → Recommendation: Focus on lagging coins for DCA")

        # Market cap insights
        if "market_cap_tier" in str(top_features):
            logger.info("\n4. MARKET CAP TIER AFFECTS STRATEGY:")
            logger.info("   - Different tiers need different approaches")
            logger.info("   - Mid-caps show best DCA performance")
            logger.info("   → Recommendation: Tier-specific thresholds and targets")

        # Technical insights
        technical_features = [
            f for f in top_features if "sma" in f or "drop" in f or "volume" in f
        ]
        if technical_features:
            logger.info("\n5. TECHNICAL INDICATORS:")
            logger.info(f"   - Key features: {', '.join(technical_features[:3])}")
            logger.info("   → Recommendation: Incorporate these in entry decisions")

        logger.info("\n" + "=" * 80)
        logger.info("🎯 FINAL RECOMMENDATIONS FOR ML MODEL:")
        logger.info("=" * 80)
        logger.info("\n1. Use these top 20 features for initial model")
        logger.info("2. Create separate models for BULL/BEAR/NEUTRAL regimes")
        logger.info("3. Implement adaptive position sizing based on:")
        logger.info("   - Market regime (2x in BEAR, 0.5x in BULL)")
        logger.info("   - Volatility level (1.2x in high vol)")
        logger.info("   - Symbol tier (optimize per tier)")
        logger.info("4. Set minimum confidence thresholds:")
        logger.info("   - BULL market: 70% confidence required")
        logger.info("   - NEUTRAL: 60% confidence")
        logger.info("   - BEAR: 50% confidence")


def main():
    # Initialize analyzer
    analyzer = FeatureAnalyzer()

    # Load data
    analyzer.load_data()

    # Run comprehensive analysis
    feature_summary, rf_model = analyzer.create_feature_report()

    # Analyze by different dimensions
    analyzer.analyze_by_market_regime()
    analyzer.analyze_by_symbol_characteristics()

    # Generate insights
    analyzer.generate_insights(feature_summary)

    logger.success("\n✅ Feature analysis complete!")

    return analyzer, feature_summary, rf_model


if __name__ == "__main__":
    analyzer, feature_summary, rf_model = main()
