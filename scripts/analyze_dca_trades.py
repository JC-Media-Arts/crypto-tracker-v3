"""Analyze DCA paper trades from the last 14 days."""
import os
import sys
from datetime import datetime, timedelta, timezone
import json
from supabase import create_client, Client
from dotenv import load_dotenv
import pandas as pd
import numpy as np

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

def analyze_dca_trades():
    """Analyze DCA trades from the last 14 days."""
    
    # Get trades from last 14 days
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=14)
    
    print("Fetching DCA trades from the last 14 days...")
    
    # Fetch all paper trades with DCA strategy
    response = supabase.table('paper_trades').select('*').eq('strategy_name', 'DCA').gte('created_at', cutoff_date.isoformat()).execute()
    
    if not response.data:
        print("No DCA trades found in the last 14 days")
        return
    
    trades = pd.DataFrame(response.data)
    
    # Convert timestamp to datetime
    trades['created_at'] = pd.to_datetime(trades['created_at'])
    
    # Group by trade_group_id to identify complete trades
    grouped = trades.groupby('trade_group_id')
    
    completed_trades = []
    open_trades = []
    
    for group_id, group in grouped:
        buy_trades = group[group['side'] == 'BUY']
        sell_trades = group[group['side'] == 'SELL']
        
        if len(sell_trades) > 0:
            # This is a completed trade
            entry_price = buy_trades['price'].mean()
            entry_time = buy_trades['created_at'].min()
            exit_price = sell_trades['price'].iloc[0]
            exit_time = sell_trades['created_at'].iloc[0]
            exit_reason = sell_trades['exit_reason'].iloc[0] if 'exit_reason' in sell_trades.columns else 'unknown'
            
            # Calculate profit/loss
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100
            hold_time = (exit_time - entry_time).total_seconds() / 3600  # in hours
            
            completed_trades.append({
                'symbol': group['symbol'].iloc[0],
                'entry_price': entry_price,
                'exit_price': exit_price,
                'pnl_pct': pnl_pct,
                'exit_reason': exit_reason,
                'hold_time_hours': hold_time,
                'entry_time': entry_time,
                'market_cap_tier': group['market_cap_tier'].iloc[0] if 'market_cap_tier' in group.columns else 'unknown'
            })
        else:
            # Open trade
            entry_price = buy_trades['price'].mean()
            entry_time = buy_trades['created_at'].min()
            
            open_trades.append({
                'symbol': group['symbol'].iloc[0],
                'entry_price': entry_price,
                'entry_time': entry_time,
                'market_cap_tier': group['market_cap_tier'].iloc[0] if 'market_cap_tier' in group.columns else 'unknown'
            })
    
    print(f"\n=== DCA TRADES ANALYSIS (Last 14 Days) ===")
    print(f"Total Trade Groups: {len(grouped)}")
    print(f"Completed Trades: {len(completed_trades)}")
    print(f"Open Trades: {len(open_trades)}")
    
    if completed_trades:
        df_completed = pd.DataFrame(completed_trades)
        
        print(f"\n=== COMPLETED TRADES STATISTICS ===")
        print(f"Win Rate: {(df_completed['pnl_pct'] > 0).mean():.1%}")
        print(f"Average P&L: {df_completed['pnl_pct'].mean():.2f}%")
        print(f"Median P&L: {df_completed['pnl_pct'].median():.2f}%")
        print(f"Best Trade: {df_completed['pnl_pct'].max():.2f}%")
        print(f"Worst Trade: {df_completed['pnl_pct'].min():.2f}%")
        print(f"Avg Hold Time: {df_completed['hold_time_hours'].mean():.1f} hours")
        
        # Exit reason breakdown
        print(f"\n=== EXIT REASONS ===")
        exit_counts = df_completed['exit_reason'].value_counts()
        for reason, count in exit_counts.items():
            pct = (count / len(df_completed)) * 100
            avg_pnl = df_completed[df_completed['exit_reason'] == reason]['pnl_pct'].mean()
            print(f"{reason}: {count} trades ({pct:.1f}%), Avg P&L: {avg_pnl:.2f}%")
        
        # Performance by market cap tier
        if 'market_cap_tier' in df_completed.columns:
            print(f"\n=== PERFORMANCE BY MARKET CAP TIER ===")
            for tier in df_completed['market_cap_tier'].unique():
                tier_trades = df_completed[df_completed['market_cap_tier'] == tier]
                if len(tier_trades) > 0:
                    win_rate = (tier_trades['pnl_pct'] > 0).mean()
                    avg_pnl = tier_trades['pnl_pct'].mean()
                    print(f"{tier}: {len(tier_trades)} trades, Win Rate: {win_rate:.1%}, Avg P&L: {avg_pnl:.2f}%")
        
        # Save detailed results
        df_completed.to_csv('data/dca_completed_trades_analysis.csv', index=False)
        print(f"\nDetailed results saved to data/dca_completed_trades_analysis.csv")
    
    # Analyze entry conditions
    print(f"\n=== ANALYZING ENTRY CONDITIONS ===")
    
    # Get all BUY trades
    buy_trades = trades[trades['side'] == 'BUY']
    
    if 'features' in buy_trades.columns and len(buy_trades) > 0:
        # Extract drop percentages from features
        drops = []
        for idx, row in buy_trades.iterrows():
            if row['features'] and isinstance(row['features'], dict):
                if 'price_drop_4h' in row['features']:
                    drops.append(row['features']['price_drop_4h'])
        
        if drops:
            drops = np.array(drops)
            print(f"Entry Drop Statistics:")
            print(f"  Average: {np.mean(drops):.2f}%")
            print(f"  Median: {np.median(drops):.2f}%")
            print(f"  Min: {np.min(drops):.2f}%")
            print(f"  Max: {np.max(drops):.2f}%")
            print(f"  25th percentile: {np.percentile(drops, 25):.2f}%")
            print(f"  75th percentile: {np.percentile(drops, 75):.2f}%")

if __name__ == "__main__":
    analyze_dca_trades()
