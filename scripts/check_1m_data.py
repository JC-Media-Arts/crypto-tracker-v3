import os
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

cutoff = datetime.now(timezone.utc) - timedelta(days=14)

# Get unique symbols with recent 1m data
response = supabase.table('ohlc_data').select('symbol').gte('timestamp', cutoff.isoformat()).eq('timeframe', '1m').limit(1000).execute()

symbols = list(set([row['symbol'] for row in response.data]))
print(f"Found {len(symbols)} symbols with 1m data in last 14 days")

# Check how much data we have
for tf in ['1m', '5m', '15m', '1h', '4h']:
    response = supabase.table('ohlc_data').select('symbol').gte('timestamp', cutoff.isoformat()).eq('timeframe', tf).limit(1000).execute()
    symbols = list(set([row['symbol'] for row in response.data]))
    print(f"{tf}: {len(symbols)} symbols")
