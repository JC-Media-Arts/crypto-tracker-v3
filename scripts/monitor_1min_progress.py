#!/usr/bin/env python3
"""
Monitor the progress of 1-minute OHLC data fetching
"""

import json
import time
from pathlib import Path
from datetime import datetime

def main():
    results_file = Path('data/1min_all_symbols_results.json')
    
    print("=" * 60)
    print("1-MINUTE OHLC FETCH MONITOR")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60)
    
    if not results_file.exists():
        print("Fetch process is initializing...")
        print("The script needs to:")
        print("  1. Connect to database")
        print("  2. Get list of all 90 symbols")
        print("  3. Start fetching data for each symbol")
        print("\nThis will take several hours to complete.")
        print("Each symbol needs ~365 days of minute-by-minute data.")
        return
    
    with open(results_file) as f:
        results = json.load(f)
    
    completed = sum(1 for r in results.values() if r['status'] == 'completed')
    skipped = sum(1 for r in results.values() if r['status'] == 'skipped')
    failed = sum(1 for r in results.values() if r['status'] in ['failed', 'error'])
    no_data = sum(1 for r in results.values() if r['status'] == 'no_data')
    total = len(results)
    
    print(f"\nProgress: {total}/90 symbols processed")
    print("-" * 40)
    print(f"✅ Completed: {completed}")
    print(f"⏭️  Skipped (already had data): {skipped}")
    print(f"⚠️  No data available: {no_data}")
    print(f"❌ Failed: {failed}")
    
    # Show recently completed symbols
    if results:
        print("\nRecent symbols:")
        print("-" * 40)
        for symbol, result in list(results.items())[-5:]:
            status = result['status']
            bars = result.get('bars_saved', 0)
            if status == 'completed':
                print(f"  {symbol}: ✅ {bars:,} bars saved")
            elif status == 'skipped':
                existing = result.get('existing', 0)
                print(f"  {symbol}: ⏭️  Skipped ({existing:,} bars exist)")
            elif status == 'no_data':
                print(f"  {symbol}: ⚠️  No data available")
            else:
                print(f"  {symbol}: ❌ {status}")
    
    # Estimate time remaining
    if completed + skipped > 0:
        avg_time_per_symbol = 120  # ~2 minutes per symbol (rough estimate)
        remaining = 90 - total
        est_minutes = remaining * avg_time_per_symbol / 60
        print(f"\nEstimated time remaining: ~{est_minutes:.1f} hours")
    
    print("\n" + "=" * 60)
    print("Note: 1-minute data is the most granular and takes longest to fetch")
    print("Expected total time: 3-4 hours for all 90 symbols")

if __name__ == "__main__":
    main()
