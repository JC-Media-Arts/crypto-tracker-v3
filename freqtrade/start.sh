#!/bin/sh
# Startup script for Freqtrade on Railway with Supabase PostgreSQL

echo "========================================="
echo "FREQTRADE STARTUP SCRIPT EXECUTING"
echo "========================================="
echo "Starting Freqtrade with Supabase PostgreSQL..."
echo "SUPABASE_URL is set: $([ ! -z "$SUPABASE_URL" ] && echo "Yes" || echo "No")"
echo "SUPABASE_KEY is set: $([ ! -z "$SUPABASE_KEY" ] && echo "Yes" || echo "No")"
echo "DATABASE_URL is set: $([ ! -z "$DATABASE_URL" ] && echo "Yes" || echo "No")"
echo "Trading mode: ${TRADING_MODE:-dry_run}"
echo "API Port: ${PORT:-8080}"

# Parse DATABASE_URL for PostgreSQL connection
# Expected format: postgresql://user:password@host:port/database
if [ ! -z "$DATABASE_URL" ]; then
    echo "Parsing DATABASE_URL for PostgreSQL connection..."
    # Extract components from DATABASE_URL
    # Format: postgresql://user:password@host:port/database
    export DB_USER=$(echo $DATABASE_URL | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
    export DB_PASSWORD=$(echo $DATABASE_URL | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
    export DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
    export DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    export DB_NAME=$(echo $DATABASE_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')
    echo "Database connection configured for host: $DB_HOST"
else
    echo "WARNING: DATABASE_URL not set, will use SQLite"
fi

# First, sync data from Supabase to local JSON files
echo "========================================="
echo "STARTING DATA SYNC FROM SUPABASE"
echo "========================================="
cd /freqtrade
# Sync data for all USD pairs we're trading
python user_data/freqtrade_supabase_bridge.py --timeframe 1m --days 7 --pairs \
    BTC/USD ETH/USD SOL/USD XRP/USD ADA/USD AVAX/USD DOGE/USD DOT/USD \
    LINK/USD UNI/USD ATOM/USD NEAR/USD ALGO/USD AAVE/USD SAND/USD \
    MANA/USD SHIB/USD TRX/USD BCH/USD APT/USD ICP/USD ARB/USD OP/USD \
    CRV/USD LDO/USD SUSHI/USD COMP/USD SNX/USD INJ/USD GRT/USD FIL/USD \
    IMX/USD FLOW/USD CHZ/USD GALA/USD XLM/USD HBAR/USD BNB/USD AXS/USD \
    BAL/USD BLUR/USD ENS/USD FET/USD RPL/USD PEPE/USD WIF/USD BONK/USD \
    FLOKI/USD MEME/USD POPCAT/USD MEW/USD TURBO/USD NEIRO/USD PNUT/USD \
    GOAT/USD ACT/USD TRUMP/USD FARTCOIN/USD MOG/USD PONKE/USD TREMP/USD \
    GIGA/USD HIPPO/USD RUNE/USD LRC/USD OCEAN/USD QNT/USD XMR/USD ZEC/USD \
    DASH/USD KSM/USD STX/USD KAS/USD TIA/USD JTO/USD JUP/USD PYTH/USD \
    WLD/USD ONDO/USD BEAM/USD SEI/USD PENDLE/USD RENDER/USD POL/USD TON/USD

# Check if sync was successful
if [ $? -eq 0 ]; then
    echo "✅ Data sync successful"
else
    echo "⚠️ Data sync failed, but continuing anyway..."
fi

# Note: trade_sync.py is no longer needed - Freqtrade writes directly to PostgreSQL

# Start Freqtrade with proper configuration
echo "Starting Freqtrade trading engine..."

# TEMPORARY: Skip PostgreSQL due to IPv6 connectivity issues on Railway
# Use SQLite for now to get the service running
echo "Using SQLite database (PostgreSQL temporarily disabled due to IPv6 issues)"
echo "Note: Trades will be stored locally but not persisted across deploys"

exec freqtrade trade \
    --config user_data/config.json \
    --strategy ChannelStrategyV1 \
    --strategy-path user_data/strategies \
    --datadir user_data/data \
    --logfile user_data/logs/freqtrade.log