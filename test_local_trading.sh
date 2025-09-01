#!/bin/bash

echo "🚀 TESTING FREQTRADE LOCALLY"
echo "============================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -d "freqtrade" ]; then
    echo -e "${RED}❌ Error: Must run from crypto-tracker-v3 directory${NC}"
    exit 1
fi

cd freqtrade

# Check if venv exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
echo -e "${GREEN}Activating virtual environment...${NC}"
source venv/bin/activate

# Install/upgrade Freqtrade if needed
echo -e "${GREEN}Ensuring Freqtrade is installed...${NC}"
pip install freqtrade --quiet

# Sync data from Supabase
echo -e "${GREEN}Syncing data from Supabase...${NC}"
python3 sync_supabase_for_backtesting.py

# Test the strategy loads
echo -e "${GREEN}Testing SimpleChannelStrategy loads...${NC}"
freqtrade test-pairlist --config config/config.json --strategy SimpleChannelStrategy

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Strategy failed to load!${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Strategy loaded successfully!${NC}"
echo ""

# Run a quick backtest to see if trades would trigger
echo -e "${GREEN}Running quick backtest (last 24 hours)...${NC}"
freqtrade backtesting \
    --config config/config.json \
    --strategy SimpleChannelStrategy \
    --timerange $(date -u -d '1 day ago' +%Y%m%d)-$(date -u +%Y%m%d) \
    --dry-run-wallet 10000 \
    --breakdown day

echo ""
echo -e "${GREEN}Starting Freqtrade in dry-run mode locally...${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

# Start Freqtrade with live data
freqtrade trade \
    --config config/config.json \
    --strategy SimpleChannelStrategy \
    --strategy-path user_data/strategies \
    --datadir user_data/data \
    --logfile user_data/logs/freqtrade_local_test.log \
    --db-url sqlite:///tradesv3.local_test.sqlite
