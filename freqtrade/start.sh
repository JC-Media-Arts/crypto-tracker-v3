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

# Use PostgreSQL if DATABASE_URL is set, otherwise SQLite
if [ ! -z "$DATABASE_URL" ]; then
    echo "Configuring PostgreSQL connection with IPv4..."
    
    # Parse DATABASE_URL components
    # Format: postgresql://user:password@host:port/database
    DB_USER=$(echo $DATABASE_URL | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
    DB_PASSWORD=$(echo $DATABASE_URL | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
    DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:\/]*\).*/\1/p')
    DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    DB_NAME=$(echo $DATABASE_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')
    
    echo "Original host: $DB_HOST"
    
    # Try to resolve to IPv4 address using available tools
    IPV4_ADDR=""
    
    # Method 1: Try getent (usually available in Alpine/Debian)
    if command -v getent &> /dev/null; then
        IPV4_ADDR=$(getent ahostsv4 $DB_HOST 2>/dev/null | head -n 1 | awk '{print $1}')
        if [ ! -z "$IPV4_ADDR" ]; then
            echo "Resolved to IPv4 using getent: $IPV4_ADDR"
        fi
    fi
    
    # Method 2: Try Python with forced IPv4 resolution
    if [ -z "$IPV4_ADDR" ] && command -v python3 &> /dev/null; then
        IPV4_ADDR=$(python3 -c "
import socket
# Force IPv4 only resolution
result = socket.getaddrinfo('$DB_HOST', None, socket.AF_INET)
if result:
    print(result[0][4][0])
" 2>/dev/null || echo "")
        if [ ! -z "$IPV4_ADDR" ]; then
            echo "Resolved to IPv4 using Python: $IPV4_ADDR"
        fi
    fi
    
    # Method 3: Try nslookup if available
    if [ -z "$IPV4_ADDR" ] && command -v nslookup &> /dev/null; then
        IPV4_ADDR=$(nslookup $DB_HOST 2>/dev/null | grep -A1 "Name:" | grep "Address:" | awk '{print $2}' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' | head -n 1)
        if [ ! -z "$IPV4_ADDR" ]; then
            echo "Resolved to IPv4 using nslookup: $IPV4_ADDR"
        fi
    fi
    
    # If we got an IPv4 address, use it
    if [ ! -z "$IPV4_ADDR" ]; then
        DB_HOST="$IPV4_ADDR"
    else
        echo "Warning: Could not resolve to IPv4, using original hostname"
        echo "This may cause connection issues if the host only supports IPv6"
    fi
    
    # Reconstruct DATABASE_URL with IPv4 address
    DB_URL_IPV4="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}?connect_timeout=10"
    echo "Using PostgreSQL with IPv4: ${DB_HOST}:${DB_PORT}/${DB_NAME}"
    
    exec freqtrade trade \
        --config user_data/config.json \
        --strategy SimpleChannelStrategy \
        --strategy-path user_data/strategies \
        --datadir user_data/data \
        --db-url "${DB_URL_IPV4}" \
        --logfile user_data/logs/freqtrade.log
else
    echo "No DATABASE_URL found, using SQLite"
    exec freqtrade trade \
        --config user_data/config.json \
        --strategy SimpleChannelStrategy \
        --strategy-path user_data/strategies \
        --datadir user_data/data \
        --logfile user_data/logs/freqtrade.log
fi