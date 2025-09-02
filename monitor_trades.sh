#!/bin/bash

echo "📊 FREQTRADE MONITORING COMMANDS"
echo "================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}1. Quick Trade Summary:${NC}"
echo "   sqlite3 freqtrade/tradesv3.dryrun.sqlite \"SELECT strategy, COUNT(*) as count, SUM(CASE WHEN is_open=1 THEN 1 ELSE 0 END) as open FROM trades GROUP BY strategy\""
echo ""

echo -e "${GREEN}2. All SimpleChannelStrategy Trades:${NC}"
echo "   sqlite3 freqtrade/tradesv3.dryrun.sqlite \"SELECT pair, open_rate, open_date, CASE WHEN is_open=1 THEN 'OPEN' ELSE 'CLOSED' END as status FROM trades WHERE strategy='SimpleChannelStrategy'\""
echo ""

echo -e "${GREEN}3. Live Monitoring (tail logs):${NC}"
echo "   tail -f freqtrade/freqtrade_output.log | grep -E 'Entry signal|BUY|SELL|profit'"
echo ""

echo -e "${GREEN}4. Check if Freqtrade is running:${NC}"
echo "   ps aux | grep -E 'freqtrade.*SimpleChannel' | grep -v grep"
echo ""

echo -e "${GREEN}5. Profit/Loss Summary:${NC}"
echo "   sqlite3 freqtrade/tradesv3.dryrun.sqlite \"SELECT strategy, SUM(close_profit_abs) as total_profit FROM trades WHERE is_open=0 GROUP BY strategy\""
echo ""

echo -e "${YELLOW}Running quick summary now...${NC}"
echo ""

# Run the summary
echo -e "${BLUE}Strategy Summary:${NC}"
sqlite3 freqtrade/tradesv3.dryrun.sqlite "SELECT strategy, COUNT(*) as total_trades, SUM(CASE WHEN is_open=1 THEN 1 ELSE 0 END) as open_trades FROM trades GROUP BY strategy"

echo ""
echo -e "${BLUE}Open Trades:${NC}"
sqlite3 freqtrade/tradesv3.dryrun.sqlite "SELECT pair, open_rate, open_date FROM trades WHERE is_open=1"

echo ""
echo -e "${BLUE}Recent Closed Trades (if any):${NC}"
sqlite3 freqtrade/tradesv3.dryrun.sqlite "SELECT pair, close_profit_abs, close_date FROM trades WHERE is_open=0 ORDER BY close_date DESC LIMIT 3"
