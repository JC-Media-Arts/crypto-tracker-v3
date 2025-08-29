"""
Analyze volatility and optimal drop thresholds by market cap tier.
"""
import os
from datetime import datetime, timedelta, timezone
from supabase import create_client
from dotenv import load_dotenv
import pandas as pd
import numpy as np
import json

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def get_market_cap_tier(symbol: str) -> str:
    """Get market cap tier for a symbol."""
    # Load from unified config
    with open('configs/paper_trading_config_unified.json', 'r') as f:
        config = json.load(f)
    
    tiers = config['market_cap_tiers']
    
    for tier_name, symbols in tiers.items():
        if symbol in symbols:
            return tier_name
    return 'mid_cap'  # default

def analyze_scan_history_by_tier():
    """Analyze scan history patterns by market cap tier."""
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    
    print("Fetching scan history for analysis...")
    response = supabase.table('scan_history').select('*').gte(
        'timestamp', cutoff.isoformat()
    ).eq('strategy_name', 'DCA').limit(10000).execute()
    
    if not response.data:
        print("No scan history found")
        return
    
    scans = pd.DataFrame(response.data)
    print(f"Analyzing {len(scans)} DCA scans from last 30 days")
    
    # Add market cap tier
    scans['tier'] = scans['symbol'].apply(get_market_cap_tier)
    
    # Parse features
    features_data = []
    for idx, row in scans.iterrows():
        if row['features'] and isinstance(row['features'], (dict, str)):
            features = row['features'] if isinstance(row['features'], dict) else json.loads(row['features'])
            features['symbol'] = row['symbol']
            features['tier'] = row['tier']
            features['timestamp'] = row['timestamp']
            features['signal_strength'] = row.get('signal_strength', 0)
            features_data.append(features)
    
    df_features = pd.DataFrame(features_data)
    
    # Analyze by tier
    print("\n" + "="*80)
    print("VOLATILITY AND DROP ANALYSIS BY MARKET CAP TIER")
    print("="*80)
    
    tier_stats = {}
    
    for tier in ['large_cap', 'mid_cap', 'small_cap', 'memecoin']:
        tier_data = df_features[df_features['tier'] == tier]
        
        if len(tier_data) > 0:
            print(f"\n{tier.upper()} ({len(tier_data)} signals)")
            print("-" * 40)
            
            # Volatility analysis
            if 'volatility' in tier_data.columns:
                vol_stats = tier_data['volatility'].describe()
                print(f"Volatility (daily %):")
                print(f"  Mean: {vol_stats['mean']:.2f}%")
                print(f"  Median: {vol_stats['50%']:.2f}%")
                print(f"  75th percentile: {vol_stats['75%']:.2f}%")
            
            # Drop analysis
            if 'price_drop_4h' in tier_data.columns:
                drops = tier_data['price_drop_4h'].dropna()
                if len(drops) > 0:
                    print(f"\n4-Hour Drop Distribution:")
                    print(f"  Mean: {drops.mean():.2f}%")
                    print(f"  Median: {drops.median():.2f}%")
                    
                    # Key percentiles for threshold setting
                    percentiles = [10, 20, 30, 40, 50, 60, 70, 80, 90]
                    print(f"\n  Percentiles (for threshold selection):")
                    for p in percentiles:
                        val = np.percentile(drops, p)
                        print(f"    {p}th: {val:.2f}%")
                    
                    # Find optimal threshold (30th-40th percentile typically good)
                    optimal_threshold = np.percentile(drops, 35)
                    conservative_threshold = np.percentile(drops, 25)
                    aggressive_threshold = np.percentile(drops, 45)
                    
                    tier_stats[tier] = {
                        'mean_volatility': tier_data['volatility'].mean() if 'volatility' in tier_data.columns else 0,
                        'mean_drop': drops.mean(),
                        'median_drop': drops.median(),
                        'optimal_threshold': optimal_threshold,
                        'conservative_threshold': conservative_threshold,
                        'aggressive_threshold': aggressive_threshold,
                        'signal_count': len(tier_data)
                    }
    
    # Get completed trades by tier
    print("\n" + "="*80)
    print("ACTUAL TRADING PERFORMANCE BY TIER (Last 30 Days)")
    print("="*80)
    
    trades_response = supabase.table('paper_trades').select('*').gte(
        'created_at', cutoff.isoformat()
    ).eq('strategy_name', 'DCA').execute()
    
    if trades_response.data:
        trades = pd.DataFrame(trades_response.data)
        trades['tier'] = trades['symbol'].apply(get_market_cap_tier)
        
        # Group by tier and trade_group_id
        for tier in ['large_cap', 'mid_cap', 'small_cap', 'memecoin']:
            tier_trades = trades[trades['tier'] == tier]
            if len(tier_trades) > 0:
                # Count completed vs open
                groups = tier_trades.groupby('trade_group_id')
                completed = 0
                total = 0
                wins = 0
                
                for group_id, group in groups:
                    total += 1
                    sells = group[group['side'] == 'SELL']
                    if len(sells) > 0:
                        completed += 1
                        if sells.iloc[0]['pnl'] > 0:
                            wins += 1
                
                print(f"\n{tier.upper()}:")
                print(f"  Total positions: {total}")
                print(f"  Completed: {completed} ({completed/total*100:.1f}%)")
                if completed > 0:
                    print(f"  Win rate: {wins/completed*100:.1f}%")
    
    # Generate recommendations
    print("\n" + "="*80)
    print("RECOMMENDED TIERED ENTRY THRESHOLDS")
    print("="*80)
    
    recommendations = {}
    
    for tier, stats in tier_stats.items():
        # Adjust based on volatility and performance
        base_threshold = stats['optimal_threshold']
        
        # Round to nearest 0.5%
        threshold = round(base_threshold * 2) / 2
        
        # Apply bounds
        if tier == 'large_cap':
            threshold = max(threshold, -2.0)  # Not deeper than -2%
            threshold = min(threshold, -1.5)  # Not shallower than -1.5%
        elif tier == 'mid_cap':
            threshold = max(threshold, -3.0)  # Not deeper than -3%
            threshold = min(threshold, -2.0)  # Not shallower than -2%
        elif tier == 'small_cap':
            threshold = max(threshold, -4.0)  # Not deeper than -4%
            threshold = min(threshold, -2.5)  # Not shallower than -2.5%
        elif tier == 'memecoin':
            threshold = max(threshold, -5.0)  # Not deeper than -5%
            threshold = min(threshold, -3.5)  # Not shallower than -3.5%
        
        recommendations[tier] = {
            'recommended': threshold,
            'conservative': round(stats['conservative_threshold'] * 2) / 2,
            'aggressive': round(stats['aggressive_threshold'] * 2) / 2,
            'based_on_signals': stats['signal_count']
        }
    
    print("\nBased on volatility analysis and historical performance:\n")
    
    print("RECOMMENDED (Balanced approach):")
    for tier in ['large_cap', 'mid_cap', 'small_cap', 'memecoin']:
        if tier in recommendations:
            print(f"  {tier}: {recommendations[tier]['recommended']:.1f}%")
    
    print("\nCONSERVATIVE (Fewer, higher-quality signals):")
    for tier in ['large_cap', 'mid_cap', 'small_cap', 'memecoin']:
        if tier in recommendations:
            print(f"  {tier}: {recommendations[tier]['conservative']:.1f}%")
    
    print("\nAGGRESSIVE (More signals, accept more risk):")
    for tier in ['large_cap', 'mid_cap', 'small_cap', 'memecoin']:
        if tier in recommendations:
            print(f"  {tier}: {recommendations[tier]['aggressive']:.1f}%")
    
    # Volume threshold recommendations
    print("\n" + "="*80)
    print("VOLUME THRESHOLD RECOMMENDATIONS BY TIER")
    print("="*80)
    
    print("\nRecommended volume thresholds (vs average):")
    print("  large_cap: 0.8x (high liquidity, less concern)")
    print("  mid_cap: 0.9x (moderate liquidity)")
    print("  small_cap: 1.0x (ensure sufficient interest)")
    print("  memecoin: 1.2x (need momentum confirmation)")
    
    return tier_stats, recommendations

if __name__ == "__main__":
    tier_stats, recommendations = analyze_scan_history_by_tier()
