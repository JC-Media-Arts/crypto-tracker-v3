#!/usr/bin/env python3
"""
Monitor the progress of 15-minute OHLC data fetching
"""

import time
import json
from pathlib import Path
from datetime import datetime
from src.data.supabase_client import SupabaseClient

def main():
    client = SupabaseClient()
    
    print("=" * 60)
    print("15-MINUTE OHLC FETCH MONITOR")
    print("=" * 60)
    
    while True:
        # Check how many symbols have 15m data
        symbols_with_15m = []
        all_symbols = ['BTC', 'ETH', 'SOL', 'XRP', 'ADA', 'AVAX', 'DOGE', 'TRX', 'DOT', 'MATIC',
                      'LINK', 'UNI', 'LTC', 'BCH', 'ICP', 'ATOM', 'ETC', 'FIL', 'APT', 'ARB',
                      'ALT', 'API3', 'AXS', 'BAL', 'BEAM', 'BLUR', 'BONK', 'CHZ', 'COMP', 'CRV',
                      'CTSI', 'DASH', 'DYM', 'ENJ', 'ENS', 'EOS', 'FET', 'FLOKI', 'FLOW', 'GALA',
                      'GIGA', 'GOAT', 'GRT', 'HBAR', 'IMX', 'INJ', 'JTO', 'JUP', 'KAS', 'KSM',
                      'LDO', 'LRC', 'MANA', 'MASK', 'MEME', 'MEW', 'MKR', 'MOG', 'NEAR', 'NEIRO',
                      'OCEAN', 'OP', 'PENDLE', 'PEPE', 'PNUT', 'POL', 'PONKE', 'POPCAT', 'PYTH',
                      'QNT', 'RENDER', 'RPL', 'RUNE', 'SAND', 'SEI', 'SHIB', 'SNX', 'STRK', 'STX',
                      'SUSHI', 'TIA', 'TON', 'TREMP', 'TRUMP', 'TURBO', 'VET', 'WIF', 'XLM', 'XMR',
                      'YFI', 'ZEC', 'ALGO', 'ANKR', 'AAVE']
        
        for symbol in all_symbols[:30]:  # Check first 30 to avoid timeout
            try:
                result = client.client.table('ohlc_data').select('symbol').eq(
                    'symbol', symbol
                ).eq('timeframe', '15m').limit(1).execute()
                
                if result.data:
                    symbols_with_15m.append(symbol)
            except:
                pass
        
        # Display status
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Progress Update:")
        print(f"Symbols with 15m data: {len(symbols_with_15m)}/30 checked")
        print(f"Recently completed: {', '.join(symbols_with_15m[-5:])}")
        
        # Check backfill results file
        results_file = Path('data/backfill_results.json')
        if results_file.exists():
            try:
                with open(results_file) as f:
                    results = json.load(f)
                if results:
                    last_symbol = list(results.keys())[-1] if results else "None"
                    print(f"Last processed: {last_symbol}")
            except:
                pass
        
        # Check if process is still running
        import subprocess
        result = subprocess.run(['pgrep', '-f', 'fetch_all_historical'], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print("\n⚠️  Fetch process has stopped!")
            break
        
        print("-" * 40)
        time.sleep(30)  # Check every 30 seconds

if __name__ == "__main__":
    main()
