"""Analyze ML predictions and shadow testing results for CHANNEL strategy."""
import os
from datetime import datetime, timedelta, timezone
from supabase import create_client
from dotenv import load_dotenv
import pandas as pd
import numpy as np
import json

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def analyze_ml_predictions():
    """Analyze ML predictions for CHANNEL strategy."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    
    print("="*80)
    print("ML PREDICTIONS ANALYSIS FOR CHANNEL STRATEGY")
    print("="*80)
    
    # Get ML predictions for CHANNEL
    response = supabase.table('ml_predictions').select('*').eq(
        'strategy_name', 'CHANNEL'
    ).gte('created_at', cutoff.isoformat()).limit(1000).execute()
    
    if response.data:
        predictions = pd.DataFrame(response.data)
        print(f"\nFound {len(predictions)} ML predictions for CHANNEL in last 14 days")
        
        # Analyze confidence distribution
        if 'ml_confidence' in predictions.columns:
            print(f"\nML Confidence Statistics:")
            print(f"  Mean: {predictions['ml_confidence'].mean():.3f}")
            print(f"  Median: {predictions['ml_confidence'].median():.3f}")
            print(f"  75th percentile: {predictions['ml_confidence'].quantile(0.75):.3f}")
            print(f"  90th percentile: {predictions['ml_confidence'].quantile(0.90):.3f}")
        
        # Analyze predicted outcomes
        if 'predicted_outcome' in predictions.columns:
            outcomes = predictions['predicted_outcome'].value_counts()
            print(f"\nPredicted Outcomes:")
            for outcome, count in outcomes.items():
                print(f"  {outcome}: {count} ({count/len(predictions)*100:.1f}%)")
    else:
        print("\nNo ML predictions found for CHANNEL strategy")
    
    return predictions if response.data else None

def analyze_shadow_testing():
    """Analyze shadow testing results for CHANNEL strategy."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    
    print("\n" + "="*80)
    print("SHADOW TESTING ANALYSIS FOR CHANNEL STRATEGY")
    print("="*80)
    
    # Get shadow testing results
    response = supabase.table('shadow_results').select('*').eq(
        'strategy_name', 'CHANNEL'
    ).gte('created_at', cutoff.isoformat()).limit(1000).execute()
    
    if response.data:
        shadow = pd.DataFrame(response.data)
        print(f"\nFound {len(shadow)} shadow testing results for CHANNEL")
        
        # Analyze performance
        if 'pnl' in shadow.columns:
            wins = shadow[shadow['pnl'] > 0]
            print(f"\nShadow Testing Performance:")
            print(f"  Win Rate: {len(wins)/len(shadow)*100:.1f}%")
            print(f"  Avg P&L: {shadow['pnl'].mean():.2f}")
            print(f"  Total P&L: {shadow['pnl'].sum():.2f}")
        
        # Analyze recommendations
        if 'recommendation' in shadow.columns:
            recs = shadow['recommendation'].value_counts()
            print(f"\nRecommendations:")
            for rec, count in recs.items():
                if rec and 'threshold' in str(rec).lower():
                    print(f"  {rec}")
    else:
        print("\nNo shadow testing results found for CHANNEL strategy")
    
    return shadow if response.data else None

def analyze_scan_history():
    """Analyze CHANNEL scan history for threshold insights."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    
    print("\n" + "="*80)
    print("CHANNEL SCAN HISTORY ANALYSIS")
    print("="*80)
    
    response = supabase.table('scan_history').select('*').eq(
        'strategy_name', 'CHANNEL'
    ).gte('timestamp', cutoff.isoformat()).limit(2000).execute()
    
    if response.data:
        scans = pd.DataFrame(response.data)
        print(f"\nFound {len(scans)} CHANNEL scans in last 14 days")
        
        # Parse features to analyze channel metrics
        channel_positions = []
        channel_widths = []
        channel_strengths = []
        
        for idx, row in scans.iterrows():
            if row.get('features'):
                features = row['features'] if isinstance(row['features'], dict) else json.loads(row['features'])
                if 'channel_position' in features:
                    channel_positions.append(features['channel_position'])
                if 'channel_width' in features:
                    channel_widths.append(features['channel_width'])
                if 'channel_strength' in features:
                    channel_strengths.append(features['channel_strength'])
        
        if channel_positions:
            print(f"\nChannel Position Distribution (0=bottom, 1=top):")
            positions = np.array(channel_positions)
            print(f"  10th percentile: {np.percentile(positions, 10):.3f}")
            print(f"  25th percentile: {np.percentile(positions, 25):.3f}")
            print(f"  Median: {np.median(positions):.3f}")
            print(f"  75th percentile: {np.percentile(positions, 75):.3f}")
            print(f"  90th percentile: {np.percentile(positions, 90):.3f}")
        
        if channel_widths:
            print(f"\nChannel Width Distribution:")
            widths = np.array(channel_widths)
            print(f"  Mean: {np.mean(widths)*100:.2f}%")
            print(f"  Median: {np.median(widths)*100:.2f}%")
            print(f"  Min: {np.min(widths)*100:.2f}%")
            print(f"  Max: {np.max(widths)*100:.2f}%")
        
        if channel_strengths:
            print(f"\nChannel Strength Distribution:")
            strengths = np.array(channel_strengths)
            print(f"  Mean: {np.mean(strengths):.3f}")
            print(f"  Median: {np.median(strengths):.3f}")
            print(f"  75th percentile: {np.percentile(strengths, 75):.3f}")
    else:
        print("\nNo CHANNEL scan history found")
    
    return scans if response.data else None

def analyze_paper_trades():
    """Analyze actual CHANNEL paper trading performance."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    
    print("\n" + "="*80)
    print("CHANNEL PAPER TRADING PERFORMANCE (Last 14 Days)")
    print("="*80)
    
    response = supabase.table('paper_trades').select('*').eq(
        'strategy_name', 'CHANNEL'
    ).gte('created_at', cutoff.isoformat()).execute()
    
    if response.data:
        trades = pd.DataFrame(response.data)
        
        # Group by trade_group_id
        groups = trades.groupby('trade_group_id')
        
        completed = []
        open_positions = []
        
        for group_id, group in groups:
            buys = group[group['side'] == 'BUY']
            sells = group[group['side'] == 'SELL']
            
            if len(sells) > 0:
                # Completed trade
                entry_price = buys['price'].mean()
                exit_price = sells['price'].iloc[0]
                pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                
                completed.append({
                    'symbol': group['symbol'].iloc[0],
                    'pnl_pct': pnl_pct,
                    'exit_reason': sells['exit_reason'].iloc[0] if 'exit_reason' in sells.columns else 'unknown'
                })
            else:
                open_positions.append({
                    'symbol': group['symbol'].iloc[0],
                    'entry_time': buys['created_at'].min()
                })
        
        print(f"\nTotal Positions: {len(groups)}")
        print(f"Completed: {len(completed)}")
        print(f"Open: {len(open_positions)}")
        
        if completed:
            df_completed = pd.DataFrame(completed)
            wins = df_completed[df_completed['pnl_pct'] > 0]
            
            print(f"\nCompleted Trade Statistics:")
            print(f"  Win Rate: {len(wins)/len(df_completed)*100:.1f}%")
            print(f"  Avg P&L: {df_completed['pnl_pct'].mean():.2f}%")
            print(f"  Best Trade: {df_completed['pnl_pct'].max():.2f}%")
            print(f"  Worst Trade: {df_completed['pnl_pct'].min():.2f}%")
            
            # Exit reasons
            if 'exit_reason' in df_completed.columns:
                print(f"\nExit Reasons:")
                for reason, count in df_completed['exit_reason'].value_counts().items():
                    print(f"  {reason}: {count}")
    else:
        print("\nNo CHANNEL paper trades found")

if __name__ == "__main__":
    ml_predictions = analyze_ml_predictions()
    shadow_results = analyze_shadow_testing()
    scan_history = analyze_scan_history()
    analyze_paper_trades()
