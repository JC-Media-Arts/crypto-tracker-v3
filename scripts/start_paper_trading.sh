#!/bin/bash

echo "🤖 STARTING HUMMINGBOT PAPER TRADING"
echo "===================================="
echo ""
echo "📊 Configuration:"
echo "  - Exchange: Kraken Paper Trade"
echo "  - Strategy: ML Signal Strategy"
echo "  - Balance: $10,000 USD"
echo ""
echo "Connecting to Hummingbot..."
echo ""
echo "TO START PAPER TRADING:"
echo "1. When you see the >>> prompt, type:"
echo "   start --script strategies/ml_signal_strategy.py"
echo ""
echo "2. Or for manual trading:"
echo "   paper_trade_enabled"
echo "   connect kraken_paper_trade"
echo ""
echo "Connecting now..."
echo "=================="

# Connect to the running Hummingbot instance
docker attach hummingbot-trading
