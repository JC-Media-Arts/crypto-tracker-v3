#!/bin/bash

echo "🔧 FIXING POSTGRESQL CONNECTION FOR RAILWAY"
echo "=========================================="
echo ""

# This script updates start.sh to properly use PostgreSQL
# and adds a trade sync mechanism

cat << 'EOF' > start_fixed.sh
#!/bin/bash
set -e

echo "========================================="
echo "FREQTRADE STARTUP SCRIPT"
echo "========================================="
echo "Environment: ${RAILWAY_ENVIRONMENT:-development}"
echo "Python version: $(python --version)"
echo "Freqtrade version: $(freqtrade --version 2>/dev/null || echo 'Not installed yet')"

# Install Freqtrade if not already installed
if ! command -v freqtrade &> /dev/null; then
    echo "Installing Freqtrade..."
    pip install freqtrade
fi

# Parse DATABASE_URL and force IPv4
if [ ! -z "$DATABASE_URL" ]; then
    echo "Configuring PostgreSQL connection..."
    
    # Parse the DATABASE_URL
    # Format: postgresql://user:password@host:port/database?options
    DB_USER=$(echo $DATABASE_URL | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
    DB_PASSWORD=$(echo $DATABASE_URL | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
    DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:\/]*\).*/\1/p')
    DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    DB_NAME=$(echo $DATABASE_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')
    
    # Force IPv4 by using IP address if possible
    # Railway PostgreSQL usually has format like xxx.railway.app
    if [[ "$DB_HOST" == *"railway.app" ]]; then
        echo "Railway PostgreSQL detected, attempting to resolve to IPv4..."
        # Try to get IPv4 address
        IPV4_ADDR=$(getent ahostsv4 "$DB_HOST" | head -n 1 | awk '{print $1}' || echo "")
        if [ ! -z "$IPV4_ADDR" ]; then
            echo "Resolved to IPv4: $IPV4_ADDR"
            DB_HOST="$IPV4_ADDR"
        else
            echo "Could not resolve to IPv4, using hostname"
        fi
    fi
    
    # Reconstruct DATABASE_URL with potential IPv4
    export FREQTRADE_DB_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
    echo "Database URL configured (host: $DB_HOST)"
else
    echo "WARNING: DATABASE_URL not set, using SQLite"
    export FREQTRADE_DB_URL="sqlite:///tradesv3.dryrun.sqlite"
fi

# Sync data from Supabase
echo "========================================="
echo "SYNCING DATA FROM SUPABASE"
echo "========================================="
cd /freqtrade
python sync_supabase_for_backtesting.py

if [ $? -eq 0 ]; then
    echo "✅ Data sync successful"
else
    echo "⚠️ Data sync failed, but continuing anyway..."
fi

# Start Freqtrade with database URL
echo "Starting Freqtrade trading engine..."
echo "Using database: ${FREQTRADE_DB_URL}"

exec freqtrade trade \
    --config config/config.json \
    --strategy SimpleChannelStrategy \
    --strategy-path user_data/strategies \
    --datadir user_data/data \
    --db-url "${FREQTRADE_DB_URL}" \
    --logfile user_data/logs/freqtrade.log
EOF

echo "✅ Created fixed start script: start_fixed.sh"
echo ""
echo "This script:"
echo "1. Properly parses DATABASE_URL"
echo "2. Attempts to resolve Railway PostgreSQL to IPv4"
echo "3. Uses PostgreSQL if available, falls back to SQLite"
echo "4. Passes the database URL to Freqtrade"
echo ""
echo "To deploy:"
echo "  mv start_fixed.sh start.sh"
echo "  git add freqtrade/start.sh"
echo "  git commit -m 'Fix PostgreSQL connection for Railway'"
echo "  git push origin main"
