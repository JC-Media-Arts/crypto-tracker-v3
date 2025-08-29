"""Check if current market has any drops that should trigger DCA."""
import os
from datetime import datetime, timedelta, timezone
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

print("CURRENT MARKET CONDITIONS CHECK")
print("="*60)

# Check recent price movements for major coins
symbols = ['BTC', 'ETH', 'SOL', 'LINK', 'MATIC']
cutoff = datetime.now(timezone.utc) - timedelta(hours=4)

for symbol in symbols:
    response = supabase.table('ohlc_data').select('high, low, close').eq(
        'symbol', symbol
    ).eq('timeframe', '15m').gte(
        'timestamp', cutoff.isoformat()
    ).order('timestamp', desc=False).execute()
    
    if response.data and len(response.data) > 0:
        data = response.data
        recent_high = max([d['high'] for d in data])
        current_price = data[-1]['close']
        drop_pct = ((current_price - recent_high) / recent_high) * 100
        
        # Check against new thresholds
        if symbol in ['BTC', 'ETH', 'SOL']:
            threshold = -1.75  # large cap
            tier = "large_cap"
        else:
            threshold = -2.25  # mid cap
            tier = "mid_cap"
        
        status = "🎯 SHOULD TRIGGER" if drop_pct <= threshold else "⏳ Not ready"
        
        print(f"{symbol:6} 4h drop: {drop_pct:+.2f}% (needs {threshold}% for {tier}) - {status}")

print("\nIf drops are close to thresholds, trades should trigger soon.")
print("If market is flat/rising, DCA won't trigger (by design).")
