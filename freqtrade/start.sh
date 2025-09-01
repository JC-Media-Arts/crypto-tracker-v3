#!/bin/sh
# Startup script for Freqtrade on Railway with Supabase data sync

echo "Starting Freqtrade with Supabase integration..."
echo "SUPABASE_URL is set: $([ ! -z "$SUPABASE_URL" ] && echo "Yes" || echo "No")"
echo "SUPABASE_KEY is set: $([ ! -z "$SUPABASE_KEY" ] && echo "Yes" || echo "No")"
echo "Trading mode: ${TRADING_MODE:-dry_run}"
echo "API Port: ${PORT:-8080}"

# First, sync data from Supabase to local JSON files
echo "Syncing data from Supabase..."
cd /freqtrade
# Use pairs from config file and sync more historical data
python user_data/freqtrade_supabase_bridge.py --timeframe 1m --days 7 --pairs_from_config

# Check if sync was successful
if [ $? -eq 0 ]; then
    echo "✅ Data sync successful"
else
    echo "⚠️ Data sync failed, but continuing anyway..."
fi

# Start Freqtrade with proper configuration
echo "Starting Freqtrade trading engine..."
exec freqtrade trade \
    --config user_data/config.json \
    --strategy ChannelStrategyV1 \
    --strategy-path user_data/strategies \
    --datadir user_data/data \
    --logfile user_data/logs/freqtrade.log