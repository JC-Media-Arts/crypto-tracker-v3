# Freqtrade Railway Setup with PostgreSQL

## Environment Variables Required

You need to set these environment variables in Railway for the Freqtrade service:

### Required Variables:
- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_KEY` - Your Supabase anon/public key  
- `DATABASE_URL` - Your Supabase PostgreSQL connection string

### Getting DATABASE_URL from Supabase:
1. Go to your Supabase project
2. Navigate to Settings → Database
3. Find "Connection string" section
4. Copy the "URI" connection string
5. It should look like: `postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres`

### Setting in Railway:
1. Go to your Freqtrade service in Railway
2. Click on "Variables" tab
3. Add the environment variables above
4. Railway will automatically redeploy

## How It Works

1. **Direct PostgreSQL Connection**: Freqtrade now writes trades directly to your Supabase PostgreSQL database
2. **No More SQLite**: No local database file that gets lost on redeploy
3. **No More Sync**: Removed trade_sync.py as it's no longer needed
4. **Immediate Visibility**: Trades appear instantly in your dashboard

## Database Tables

Freqtrade will automatically create these tables in your PostgreSQL database:
- `trades` - Main trades table (different from your custom `freqtrade_trades`)
- `pairlocks` - Pair locking information
- `trade_orders` - Order history

Note: You may want to create a view or trigger to sync from Freqtrade's `trades` table to your existing `freqtrade_trades` table if needed.

## Troubleshooting

If you see connection errors:
1. Verify DATABASE_URL is set correctly in Railway
2. Check that your Supabase database allows connections from Railway's IP
3. Ensure the password in DATABASE_URL is correct
4. Check Railway logs for specific PostgreSQL connection errors
