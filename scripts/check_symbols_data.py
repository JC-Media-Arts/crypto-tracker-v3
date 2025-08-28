import os
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

cutoff = datetime.now(timezone.utc) - timedelta(days=14)

# Get unique symbols with recent data
response = supabase.table('ohlc_data').select('symbol').gte('timestamp', cutoff.isoformat()).eq('timeframe', '15m').execute()

symbols = list(set([row['symbol'] for row in response.data]))
print(f"Found {len(symbols)} symbols with 15m data in last 14 days")
print("Symbols:", sorted(symbols)[:20])  # Show first 20
