#!/usr/bin/env python3
"""Analyze why SWING strategy is not triggering trades."""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.settings import get_settings
from supabase import create_client


def check_swing_trades(supabase):
    """Check if any SWING trades were attempted or executed."""
    print("\n" + "="*60)
    print("SWING TRADE HISTORY CHECK")
    print("="*60)
    
    # Check last 7 days for any SWING activity
    end_time = datetime.now(pytz.UTC)
    start_time = end_time - timedelta(days=7)
    
    # Check paper_trades table
    query = supabase.table('paper_trades').select('*').gte(
        'created_at', start_time.isoformat()
    ).eq('strategy_name', 'SWING')
    
    result = query.execute()
    
    if result.data:
        print(f"\n✅ Found {len(result.data)} SWING trades in last 7 days")
        trades_df = pd.DataFrame(result.data)
        trades_df['created_at'] = pd.to_datetime(trades_df['created_at'])
        
        # Group by day
        daily_counts = trades_df.groupby(trades_df['created_at'].dt.date).size()
        print("\nDaily SWING trades:")
        for date, count in daily_counts.items():
            print(f"  {date}: {count} trades")
        
        # Show recent trades
        recent = trades_df.nlargest(5, 'created_at')
        print("\nMost recent SWING trades:")
        for _, trade in recent.iterrows():
            print(f"  {trade['created_at'].strftime('%Y-%m-%d %H:%M')} - {trade['symbol']} - {trade['status']}")
    else:
        print("\n❌ NO SWING trades found in last 7 days!")
    
    return result.data


def check_scan_history(supabase):
    """Check scan_history for SWING strategy detections."""
    print("\n" + "="*60)
    print("SWING SCAN HISTORY ANALYSIS")
    print("="*60)
    
    end_time = datetime.now(pytz.UTC)
    start_time = end_time - timedelta(hours=48)
    
    # Check scan_history for SWING scans
    query = supabase.table('scan_history').select('*').gte(
        'timestamp', start_time.isoformat()
    ).eq('strategy_name', 'SWING')
    
    result = query.execute()
    
    if result.data:
        scans_df = pd.DataFrame(result.data)
        scans_df['timestamp'] = pd.to_datetime(scans_df['timestamp'])
        
        print(f"\n📊 Found {len(scans_df)} SWING scans in last 48 hours")
        
        # Analyze decisions
        decision_counts = scans_df['decision'].value_counts()
        print("\nScan Decisions:")
        for decision, count in decision_counts.items():
            print(f"  {decision}: {count} ({count/len(scans_df)*100:.1f}%)")
        
        # Check if any were close to triggering
        if 'ml_confidence' in scans_df.columns:
            high_conf = scans_df[scans_df['ml_confidence'] >= 0.5]
            if not high_conf.empty:
                print(f"\n🎯 {len(high_conf)} scans with ML confidence >= 50%")
                print("Top candidates that didn't trigger:")
                top = high_conf.nlargest(5, 'ml_confidence')
                for _, scan in top.iterrows():
                    print(f"  {scan['symbol']} - Conf: {scan['ml_confidence']:.2f} - Decision: {scan['decision']}")
        
        # Check features to understand why not triggering
        if 'features' in scans_df.columns:
            print("\n🔍 Analyzing feature patterns...")
            features_list = []
            for _, row in scans_df.iterrows():
                if row['features']:
                    try:
                        features = json.loads(row['features']) if isinstance(row['features'], str) else row['features']
                        features['symbol'] = row['symbol']
                        features['decision'] = row['decision']
                        features_list.append(features)
                    except:
                        pass
            
            if features_list:
                features_df = pd.DataFrame(features_list)
                
                # Check key swing indicators
                if 'breakout_strength' in features_df.columns:
                    print(f"  Avg breakout strength: {features_df['breakout_strength'].mean():.3f}")
                    print(f"  Max breakout strength: {features_df['breakout_strength'].max():.3f}")
                    strong_breakouts = features_df[features_df['breakout_strength'] > 2.0]
                    print(f"  Symbols with >2% breakout: {len(strong_breakouts)}")
                
                if 'volume_ratio' in features_df.columns:
                    print(f"  Avg volume ratio: {features_df['volume_ratio'].mean():.2f}")
                    high_volume = features_df[features_df['volume_ratio'] > 1.5]
                    print(f"  High volume events: {len(high_volume)}")
                
                if 'momentum_score' in features_df.columns:
                    print(f"  Avg momentum score: {features_df['momentum_score'].mean():.2f}")
                
                # Find best candidates
                if 'breakout_strength' in features_df.columns and 'volume_ratio' in features_df.columns:
                    features_df['combined_score'] = features_df['breakout_strength'] * features_df['volume_ratio']
                    best_candidates = features_df.nlargest(10, 'combined_score')
                    print("\n📈 Best SWING candidates (not triggered):")
                    for _, cand in best_candidates.iterrows():
                        print(f"  {cand['symbol']}: Breakout={cand.get('breakout_strength', 0):.2f}%, "
                              f"Volume={cand.get('volume_ratio', 0):.1f}x, "
                              f"Decision={cand['decision']}")
    else:
        print("\n❌ NO SWING scans found in scan_history!")
    
    return result.data


def analyze_market_conditions(supabase):
    """Check if market conditions are suitable for SWING trades."""
    print("\n" + "="*60)
    print("MARKET CONDITIONS FOR SWING TRADING")
    print("="*60)
    
    end_time = datetime.now(pytz.UTC)
    start_time = end_time - timedelta(hours=48)
    
    # Get OHLC data to check for breakouts
    query = supabase.table('ohlc_data').select('*').gte(
        'timestamp', start_time.isoformat()
    ).order('symbol', desc=False).order('timestamp', desc=False)
    
    result = query.execute()
    
    if result.data:
        df = pd.DataFrame(result.data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        print(f"\n📊 Analyzing {df['symbol'].nunique()} symbols for breakout patterns...")
        
        breakout_candidates = []
        
        for symbol in df['symbol'].unique():
            symbol_data = df[df['symbol'] == symbol].sort_values('timestamp')
            
            if len(symbol_data) < 10:
                continue
            
            # Calculate potential breakouts
            symbol_data['high_20'] = symbol_data['high'].rolling(20, min_periods=5).max()
            symbol_data['low_20'] = symbol_data['low'].rolling(20, min_periods=5).min()
            symbol_data['breakout_pct'] = ((symbol_data['close'] - symbol_data['high_20'].shift(1)) / 
                                           symbol_data['high_20'].shift(1) * 100)
            
            # Check for volume spikes
            symbol_data['volume_ma'] = symbol_data['volume'].rolling(20, min_periods=5).mean()
            symbol_data['volume_ratio'] = symbol_data['volume'] / symbol_data['volume_ma']
            
            # Find potential breakouts
            breakouts = symbol_data[
                (symbol_data['breakout_pct'] > 2.0) &  # 2% above resistance
                (symbol_data['volume_ratio'] > 1.5)     # 50% above average volume
            ]
            
            if not breakouts.empty:
                for _, breakout in breakouts.iterrows():
                    breakout_candidates.append({
                        'symbol': symbol,
                        'timestamp': breakout['timestamp'],
                        'breakout_pct': breakout['breakout_pct'],
                        'volume_ratio': breakout['volume_ratio'],
                        'price': breakout['close']
                    })
        
        if breakout_candidates:
            candidates_df = pd.DataFrame(breakout_candidates)
            print(f"\n✅ Found {len(candidates_df)} potential breakout events!")
            
            # Group by symbol
            by_symbol = candidates_df.groupby('symbol').agg({
                'breakout_pct': 'max',
                'volume_ratio': 'max',
                'timestamp': 'count'
            }).round(2)
            by_symbol.columns = ['max_breakout', 'max_volume', 'events']
            by_symbol = by_symbol.sort_values('max_breakout', ascending=False)
            
            print("\nTop breakout candidates:")
            for symbol in by_symbol.head(10).index:
                row = by_symbol.loc[symbol]
                print(f"  {symbol}: Max breakout={row['max_breakout']:.1f}%, "
                      f"Max volume={row['max_volume']:.1f}x, "
                      f"Events={row['events']}")
        else:
            print("\n⚠️ No significant breakout patterns found in market data")
            print("This explains why SWING isn't triggering!")
    
    return breakout_candidates if 'breakout_candidates' in locals() else []


def check_configuration(supabase):
    """Check SWING strategy configuration and thresholds."""
    print("\n" + "="*60)
    print("SWING STRATEGY CONFIGURATION")
    print("="*60)
    
    # Check paper_trading.json config
    config_path = "configs/paper_trading.json"
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        if 'strategies' in config and 'SWING' in config['strategies']:
            swing_config = config['strategies']['SWING']
            print("\n📋 SWING Configuration:")
            print(f"  Enabled: {swing_config.get('enabled', False)}")
            print(f"  Min Confidence: {swing_config.get('min_confidence', 'N/A')}")
            
            if 'thresholds' in swing_config:
                print("\n  Thresholds:")
                thresholds = swing_config['thresholds']
                print(f"    Breakout: {thresholds.get('breakout_threshold', 'N/A')}%")
                print(f"    Volume Surge: {thresholds.get('volume_surge', 'N/A')}x")
                print(f"    Momentum Min: {thresholds.get('momentum_min', 'N/A')}")
            
            if 'exits_by_tier' in swing_config:
                print("\n  Exit Parameters by Tier:")
                for tier, params in swing_config['exits_by_tier'].items():
                    print(f"    {tier}:")
                    print(f"      TP: {params.get('take_profit', 'N/A')}%")
                    print(f"      SL: {params.get('stop_loss', 'N/A')}%")
                    print(f"      Trail: {params.get('trailing_stop', 'N/A')}%")
    else:
        print(f"\n❌ Config file not found: {config_path}")
    
    # Check if SWING is being scanned
    print("\n📊 Checking recent scan activity...")
    query = supabase.table('scan_history').select('strategy_name').gte(
        'timestamp', (datetime.now(pytz.UTC) - timedelta(hours=24)).isoformat()
    ).limit(1000)
    
    result = query.execute()
    if result.data:
        scans_df = pd.DataFrame(result.data)
        strategy_counts = scans_df['strategy_name'].value_counts()
        print("\nScans by strategy (last 24h):")
        for strategy, count in strategy_counts.items():
            print(f"  {strategy}: {count}")
        
        if 'SWING' not in strategy_counts:
            print("\n⚠️ WARNING: SWING strategy is not being scanned!")


def check_swing_detector():
    """Check if SwingDetector is working properly."""
    print("\n" + "="*60)
    print("SWING DETECTOR FUNCTIONALITY CHECK")
    print("="*60)
    
    try:
        from src.strategies.swing.detector import SwingDetector
        from src.config.settings import get_settings
        
        settings = get_settings()
        detector = SwingDetector()
        
        print("✅ SwingDetector imported successfully")
        
        # Check detector methods
        methods = ['detect_setup', '_calculate_breakout_strength', '_check_volume_surge']
        for method in methods:
            if hasattr(detector, method):
                print(f"  ✅ Method '{method}' exists")
            else:
                print(f"  ❌ Method '{method}' missing!")
        
        # Test with mock data
        print("\n🧪 Testing with mock breakout scenario...")
        mock_data = pd.DataFrame({
            'timestamp': pd.date_range(end=datetime.now(pytz.UTC), periods=100, freq='1H'),
            'open': [100] * 100,
            'high': [101] * 50 + [105] * 50,  # Breakout in second half
            'low': [99] * 100,
            'close': [100] * 50 + [104] * 50,  # 4% breakout
            'volume': [1000] * 50 + [2000] * 50  # Volume doubles
        })
        
        # Try detection
        setup = detector.detect_setup('TEST', mock_data)
        if setup:
            print(f"  ✅ Setup detected: {setup}")
        else:
            print("  ❌ No setup detected with mock breakout data")
            print("     This suggests thresholds might be too strict!")
        
    except Exception as e:
        print(f"❌ Error checking SwingDetector: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main analysis function."""
    print("="*80)
    print("🔍 SWING STRATEGY ANALYSIS - Why No Trades?")
    print("="*80)
    
    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_key)
    
    # 1. Check for any SWING trades
    swing_trades = check_swing_trades(supabase)
    
    # 2. Check scan history
    scan_history = check_scan_history(supabase)
    
    # 3. Analyze market conditions
    breakouts = analyze_market_conditions(supabase)
    
    # 4. Check configuration
    check_configuration(supabase)
    
    # 5. Test detector functionality
    check_swing_detector()
    
    # Summary
    print("\n" + "="*80)
    print("📋 ANALYSIS SUMMARY")
    print("="*80)
    
    issues = []
    
    if not swing_trades:
        issues.append("No SWING trades executed in 7 days")
    
    if not scan_history:
        issues.append("SWING not appearing in scan_history")
    elif scan_history:
        scans_df = pd.DataFrame(scan_history)
        if 'decision' in scans_df.columns:
            take_count = (scans_df['decision'] == 'TAKE').sum()
            if take_count == 0:
                issues.append("SWING scans never returning TAKE decision")
    
    if not breakouts:
        issues.append("No breakout patterns in market (expected behavior)")
    
    if issues:
        print("\n🚨 Issues Found:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        
        print("\n💡 Likely Causes:")
        print("  1. Breakout threshold too high (currently 3% in many configs)")
        print("  2. Volume requirements too strict")
        print("  3. Market has been ranging, not trending (no breakouts)")
        print("  4. ML confidence threshold preventing triggers")
        print("  5. Detector logic might be too conservative")
        
        print("\n🔧 Recommended Actions:")
        print("  1. Lower breakout threshold to 2.0% (from 3.0%)")
        print("  2. Reduce volume surge requirement to 1.3x (from 2.0x)")
        print("  3. Lower min_confidence to 0.45 for SWING")
        print("  4. Consider different indicators for ranging markets")
        print("  5. Add more sensitive breakout detection")
    else:
        print("\n✅ SWING strategy appears to be functioning")
        print("   Market conditions may just not be favorable for breakouts")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    main()
