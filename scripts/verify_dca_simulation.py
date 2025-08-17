#!/usr/bin/env python3
"""
Verify DCA simulation accuracy by spot-checking specific setups.
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient

# Load environment variables
load_dotenv()


def verify_simulation():
    """Verify the DCA simulation with real data."""
    
    print("=" * 80)
    print("DCA SIMULATION VERIFICATION")
    print("=" * 80)
    
    # Load the generated labels
    labels_df = pd.read_csv('data/dca_training_labels.csv')
    
    # Initialize Supabase
    supabase = SupabaseClient()
    
    # Pick a few setups to verify in detail
    # 1. A winning setup
    # 2. A losing setup  
    # 3. A breakeven setup
    
    win_setups = labels_df[labels_df['label'] == 'WIN']
    loss_setups = labels_df[labels_df['label'] == 'LOSS']
    breakeven_setups = labels_df[labels_df['label'] == 'BREAKEVEN']
    
    print(f"\nTotal setups to verify: {len(labels_df)}")
    print(f"Wins: {len(win_setups)}, Losses: {len(loss_setups)}, Breakeven: {len(breakeven_setups)}")
    
    # Verify a winning setup
    if len(win_setups) > 0:
        print("\n" + "=" * 80)
        print("VERIFYING A WINNING SETUP")
        print("=" * 80)
        verify_single_setup(win_setups.iloc[0], supabase)
    
    # Verify a losing setup
    if len(loss_setups) > 0:
        print("\n" + "=" * 80)
        print("VERIFYING A LOSING SETUP")
        print("=" * 80)
        verify_single_setup(loss_setups.iloc[0], supabase)
    
    # Verify a breakeven setup
    if len(breakeven_setups) > 0:
        print("\n" + "=" * 80)
        print("VERIFYING A BREAKEVEN SETUP")
        print("=" * 80)
        verify_single_setup(breakeven_setups.iloc[0], supabase)
    
    # Check data quality
    print("\n" + "=" * 80)
    print("DATA QUALITY CHECKS")
    print("=" * 80)
    
    # Check if drops are real
    print("\nVerifying drop percentages are accurate:")
    sample_setups = labels_df.sample(min(5, len(labels_df)))
    
    for _, setup in sample_setups.iterrows():
        symbol = setup['symbol']
        setup_time = pd.to_datetime(setup['setup_time'])
        drop_pct = setup['drop_pct']
        
        # Get price data before setup
        start_time = setup_time - timedelta(hours=4)
        
        result = supabase.client.table('price_data')\
            .select('price')\
            .eq('symbol', symbol)\
            .gte('timestamp', start_time.isoformat())\
            .lte('timestamp', setup_time.isoformat())\
            .order('timestamp')\
            .execute()
        
        if result.data:
            prices = [r['price'] for r in result.data]
            if prices:
                high_4h = max(prices)
                current = prices[-1]
                actual_drop = ((current - high_4h) / high_4h) * 100
                
                print(f"\n{symbol} at {setup_time.strftime('%Y-%m-%d %H:%M')}:")
                print(f"  Recorded drop: {drop_pct:.2f}%")
                print(f"  Verified drop: {actual_drop:.2f}%")
                print(f"  Difference: {abs(drop_pct - actual_drop):.2f}%")
                
                if abs(drop_pct - actual_drop) > 0.5:
                    print("  ⚠️ WARNING: Significant discrepancy!")


def verify_single_setup(setup, supabase):
    """Verify a single setup in detail."""
    
    symbol = setup['symbol']
    setup_time = pd.to_datetime(setup['setup_time'])
    setup_price = setup['setup_price']
    outcome = setup['label']
    pnl = setup['pnl_pct']
    
    print(f"\nSetup: {symbol} on {setup_time.strftime('%Y-%m-%d %H:%M')}")
    print(f"Setup price: ${setup_price:.2f}")
    print(f"Drop: {setup['drop_pct']:.2f}%")
    print(f"Outcome: {outcome} ({pnl:.2f}%)")
    
    # Get price data for 72 hours after setup
    end_time = setup_time + timedelta(hours=72)
    
    result = supabase.client.table('price_data')\
        .select('timestamp, price')\
        .eq('symbol', symbol)\
        .gte('timestamp', setup_time.isoformat())\
        .lte('timestamp', end_time.isoformat())\
        .order('timestamp')\
        .limit(5000)\
        .execute()
    
    if not result.data:
        print("❌ No data found for verification")
        return
    
    df = pd.DataFrame(result.data)
    df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601')
    df = df.set_index('timestamp')
    
    print(f"\nPrice data points: {len(df)}")
    
    # Simulate the grid
    print("\nDCA Grid Simulation:")
    grid_levels = []
    filled_levels = []
    
    for i in range(5):
        level_price = setup_price * (1 - 0.02 * i)  # 0%, -2%, -4%, -6%, -8%
        grid_levels.append(level_price)
        
        # Check if this level was hit
        min_price_after = df['price'].min()
        if min_price_after <= level_price:
            filled_levels.append(level_price)
            # Find when it was hit
            hit_time = df[df['price'] <= level_price].index[0] if any(df['price'] <= level_price) else None
            time_to_fill = (hit_time - setup_time).total_seconds() / 3600 if hit_time else None
            print(f"  Level {i+1}: ${level_price:.2f} - FILLED (after {time_to_fill:.1f}h)" if time_to_fill else f"  Level {i+1}: ${level_price:.2f} - FILLED")
        else:
            print(f"  Level {i+1}: ${level_price:.2f} - NOT FILLED")
    
    if not filled_levels:
        print("\n❌ No grid levels filled - should be SKIP")
        return
    
    # Calculate average entry
    avg_entry = np.mean(filled_levels)
    print(f"\nAverage entry: ${avg_entry:.2f}")
    
    # Calculate targets
    take_profit = avg_entry * 1.10
    lowest_grid = setup_price * 0.92
    stop_loss = lowest_grid * 0.97
    
    print(f"Take profit target: ${take_profit:.2f} (+10%)")
    print(f"Stop loss: ${stop_loss:.2f}")
    
    # Check what actually happened
    print("\nPrice action after entry:")
    print(f"  Lowest price: ${df['price'].min():.2f}")
    print(f"  Highest price: ${df['price'].max():.2f}")
    
    # Determine actual outcome
    actual_outcome = None
    actual_pnl = 0
    
    for idx, row in df.iterrows():
        price = row['price']
        hours_elapsed = (idx - setup_time).total_seconds() / 3600
        
        if price >= take_profit:
            actual_outcome = 'WIN'
            actual_pnl = 10.0
            print(f"\n✅ Take profit hit at ${price:.2f} after {hours_elapsed:.1f} hours")
            break
        elif price <= stop_loss:
            actual_outcome = 'LOSS'
            actual_pnl = ((stop_loss - avg_entry) / avg_entry) * 100
            print(f"\n❌ Stop loss hit at ${price:.2f} after {hours_elapsed:.1f} hours")
            break
    
    if not actual_outcome:
        # Check final price
        final_price = df['price'].iloc[-1]
        final_pnl = ((final_price - avg_entry) / avg_entry) * 100
        
        if final_pnl > 2:
            actual_outcome = 'WIN'
        elif final_pnl < -2:
            actual_outcome = 'LOSS'
        else:
            actual_outcome = 'BREAKEVEN'
        
        actual_pnl = final_pnl
        print(f"\n⏱️ Time exit: Final price ${final_price:.2f} ({final_pnl:+.2f}%)")
    
    # Compare with recorded outcome
    print(f"\nVerification:")
    print(f"  Recorded outcome: {outcome} ({pnl:.2f}%)")
    print(f"  Verified outcome: {actual_outcome} ({actual_pnl:.2f}%)")
    
    if outcome != actual_outcome:
        print("  ⚠️ WARNING: Outcome mismatch!")
    elif abs(pnl - actual_pnl) > 1:
        print(f"  ⚠️ WARNING: PnL discrepancy > 1%")
    else:
        print("  ✅ Simulation verified correctly")


if __name__ == "__main__":
    verify_simulation()
