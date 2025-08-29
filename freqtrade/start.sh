#!/bin/bash
# Startup script for Freqtrade on Railway

echo "Starting Freqtrade..."
echo "SUPABASE_URL is set: $([ ! -z "$SUPABASE_URL" ] && echo "Yes" || echo "No")"
echo "SUPABASE_KEY is set: $([ ! -z "$SUPABASE_KEY" ] && echo "Yes" || echo "No")"
echo "Trading mode: ${TRADING_MODE:-dry_run}"

# Start Freqtrade with proper configuration
exec freqtrade trade \
    --config config/config.json \
    --strategy ChannelStrategyV1 \
    --logfile user_data/logs/freqtrade.log
