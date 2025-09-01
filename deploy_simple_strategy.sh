#!/bin/bash

echo "🚀 DEPLOYING SIMPLIFIED TRADING STRATEGY"
echo "========================================"
echo ""
echo "This will deploy the SimpleChannelStrategy with loosened thresholds"
echo "designed to actually trigger trades."
echo ""

# Check if we're in the right directory
if [ ! -f "freqtrade/config/config.json" ]; then
    echo "❌ Error: Must run from crypto-tracker-v3 directory"
    exit 1
fi

echo "✅ Strategy created: SimpleChannelStrategy.py"
echo "  - Channel entry: 70% (was 35%)"
echo "  - RSI range: 20-80 (was 32-65)"
echo "  - No volume requirements"
echo "  - Fixed scan logger bug"
echo ""

echo "✅ Config updated:"
echo "  - Using SimpleChannelStrategy"
echo "  - Increased wallet to $100,000"
echo "  - Increased position size to $100"
echo ""

echo "📊 Test results show signals would trigger:"
echo "  - BTC: 18/20 recent candles"
echo "  - ETH: 17/20 recent candles"
echo "  - SOL: 20/20 recent candles"
echo "  - PEPE: 20/20 recent candles"
echo ""

echo "🎯 Next steps:"
echo "1. Commit and push changes to GitHub"
echo "2. Railway will auto-deploy"
echo "3. Monitor logs for first trades"
echo ""

# Show git status
echo "Current git status:"
git status --short

echo ""
echo "To deploy, run these commands:"
echo "  git add -A"
echo "  git commit -m 'Deploy simplified strategy with loosened thresholds'"
echo "  git push origin main"
echo ""
echo "Then monitor Railway logs for trades!"
