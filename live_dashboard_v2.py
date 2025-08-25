#!/usr/bin/env python3
"""
Enhanced multi-page trading dashboard with Market Protection
"""

from flask import Flask, render_template_string, jsonify
import sys
from pathlib import Path
import os
from datetime import datetime, timedelta, timezone

sys.path.append(str(Path(__file__).parent))

from src.data.supabase_client import SupabaseClient  # noqa: E402
from loguru import logger  # noqa: E402
from src.strategies.regime_detector import RegimeDetector  # noqa: E402
from src.trading.trade_limiter import TradeLimiter  # noqa: E402

app = Flask(__name__)

# Initialize market protection components
regime_detector = RegimeDetector(enabled=True)
trade_limiter = TradeLimiter()

# Base CSS that all pages share
BASE_CSS = r"""
    * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }

    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: #e2e8f0;
        min-height: 100vh;
    }

    /* Navigation */
    .nav-container {
        background: rgba(30, 41, 59, 0.9);
        backdrop-filter: blur(10px);
        border-bottom: 1px solid rgba(148, 163, 184, 0.2);
        position: sticky;
        top: 0;
        z-index: 100;
    }

    .nav-wrapper {
        max-width: 1800px;
        margin: 0 auto;
        padding: 0 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        height: 60px;
    }

    .nav-brand {
        font-size: 1.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .nav-links {
        display: flex;
        gap: 10px;
    }

    .nav-link {
        padding: 8px 16px;
        color: #94a3b8;
        text-decoration: none;
        border-radius: 8px;
        transition: all 0.3s ease;
    }

    .nav-link:hover {
        background: rgba(59, 130, 246, 0.1);
        color: #60a5fa;
    }

    .nav-link.active {
        background: rgba(59, 130, 246, 0.2);
        color: #3b82f6;
    }

    /* Main content */
    .container {
        max-width: 1800px;
        margin: 0 auto;
        padding: 20px;
    }

    .page-title {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 10px;
        background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .subtitle {
        color: #94a3b8;
        margin-bottom: 30px;
        font-size: 0.9rem;
    }

    /* Stats Cards */
    .stats-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 20px;
        margin-bottom: 30px;
    }

    .stat-card {
        background: rgba(30, 41, 59, 0.6);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 12px;
        padding: 20px;
        transition: all 0.3s ease;
    }

    .stat-card:hover {
        transform: translateY(-2px);
        border-color: rgba(59, 130, 246, 0.3);
    }

    .stat-label {
        color: #94a3b8;
        font-size: 0.875rem;
        margin-bottom: 5px;
    }

    .stat-value {
        font-size: 1.875rem;
        font-weight: 700;
    }

    .positive {
        color: #10b981;
    }

    .negative {
        color: #ef4444;
    }

    .neutral {
        color: #60a5fa;
    }

    /* Tables */
    .table-container {
        background: rgba(30, 41, 59, 0.4);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(148, 163, 184, 0.1);
        border-radius: 12px;
        overflow: hidden;
        margin-bottom: 30px;
    }

    .table-header {
        background: rgba(30, 41, 59, 0.8);
        padding: 15px 20px;
        border-bottom: 1px solid rgba(148, 163, 184, 0.1);
    }

    .table-title {
        font-size: 1.25rem;
        font-weight: 600;
        color: #e2e8f0;
    }

    table {
        width: 100%;
        border-collapse: collapse;
    }

    thead th {
        text-align: left;
        padding: 12px 20px;
        font-weight: 600;
        color: #94a3b8;
        font-size: 0.875rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        background: rgba(30, 41, 59, 0.5);
    }

    tbody td {
        padding: 12px 20px;
        border-top: 1px solid rgba(148, 163, 184, 0.05);
        font-size: 0.9rem;
    }

    tbody tr:hover {
        background: rgba(59, 130, 246, 0.05);
    }

    /* Alert Boxes */
    .alert {
        padding: 15px 20px;
        border-radius: 8px;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .alert-panic {
        background: rgba(239, 68, 68, 0.1);
        border: 1px solid rgba(239, 68, 68, 0.3);
        color: #fca5a5;
    }

    .alert-caution {
        background: rgba(245, 158, 11, 0.1);
        border: 1px solid rgba(245, 158, 11, 0.3);
        color: #fcd34d;
    }

    .alert-normal {
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.3);
        color: #6ee7b7;
    }

    /* Badges */
    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
    }

    .badge-strategy {
        background: rgba(139, 92, 246, 0.2);
        color: #a78bfa;
    }

    .badge-disabled {
        background: rgba(239, 68, 68, 0.2);
        color: #fca5a5;
    }

    .badge-cooldown {
        background: rgba(245, 158, 11, 0.2);
        color: #fcd34d;
    }

    /* Loading states */
    .loading {
        display: inline-block;
        width: 20px;
        height: 20px;
        border: 3px solid rgba(59, 130, 246, 0.2);
        border-radius: 50%;
        border-top-color: #3b82f6;
        animation: spin 1s ease-in-out infinite;
    }

    @keyframes spin {
        to { transform: rotate(360deg); }
    }

    /* Refresh indicator */
    .refresh-indicator {
        position: fixed;
        top: 80px;
        right: 20px;
        background: rgba(30, 41, 59, 0.9);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 8px;
        padding: 10px 16px;
        font-size: 0.875rem;
        color: #94a3b8;
    }

    .refresh-indicator.updating {
        border-color: #3b82f6;
        color: #60a5fa;
    }
"""

BASE_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - Crypto Trading Dashboard</title>
    <style>
        {{ base_css }}
        {{ page_css }}
    </style>
</head>
<body>
    <!-- Navigation -->
    <nav class="nav-container">
        <div class="nav-wrapper">
            <div class="nav-brand">
                🚀 Crypto Tracker v3
            </div>
            <div class="nav-links">
                <a href="/" class="nav-link {{ 'active' if active_page == 'paper_trading' else '' }}">
                    📊 Paper Trading
                </a>
                <a href="/strategies" class="nav-link {{ 'active' if active_page == 'strategies' else '' }}">
                    🎯 Strategies
                </a>
                <a href="/market" class="nav-link {{ 'active' if active_page == 'market' else '' }}">
                    🌍 Market
                </a>
            </div>
        </div>
    </nav>

    <!-- Page Content -->
    <div class="container">
        {{ content }}
    </div>

    <!-- Refresh Indicator -->
    <div class="refresh-indicator" id="refreshIndicator">
        <span id="refreshText">Auto-refresh: ON</span>
        <span id="refreshCountdown"></span>
    </div>

    <!-- Scripts -->
    <script>
        // Global refresh management
        let refreshInterval = 10000; // 10 seconds
        let countdown = refreshInterval / 1000;

        function updateCountdown() {
            countdown--;
            if (countdown <= 0) {
                countdown = refreshInterval / 1000;
                document.getElementById('refreshIndicator').classList.add('updating');
                setTimeout(() => {
                    document.getElementById('refreshIndicator').classList.remove('updating');
                }, 1000);
            }
            document.getElementById('refreshCountdown').innerText = `(${countdown}s)`;
        }

        setInterval(updateCountdown, 1000);
    </script>
    {{ page_scripts }}
</body>
</html>
"""

# Paper Trading Page Template
PAPER_TRADING_TEMPLATE = r"""
<h1 class="page-title">Paper Trading Dashboard</h1>
<p class="subtitle">Live paper trading performance and positions</p>

<!-- Portfolio Stats -->
<div class="stats-container" id="portfolioStats">
    <div class="stat-card">
        <div class="stat-label">Current Balance</div>
        <div class="stat-value neutral" id="currentBalance">Loading...</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Total P&L</div>
        <div class="stat-value" id="totalPnl">Loading...</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Win Rate</div>
        <div class="stat-value" id="winRate">Loading...</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Open Positions</div>
        <div class="stat-value neutral" id="openPositions">Loading...</div>
    </div>
</div>

<!-- Open Positions Table -->
<div class="table-container">
    <div class="table-header">
        <h2 class="table-title">Open Positions</h2>
    </div>
    <table>
        <thead>
            <tr>
                <th>Symbol</th>
                <th>Strategy</th>
                <th>Entry Price</th>
                <th>Current Price</th>
                <th>P&L %</th>
                <th>P&L $</th>
                <th>Duration</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody id="openPositionsTable">
            <tr><td colspan="8" style="text-align: center;">Loading positions...</td></tr>
        </tbody>
    </table>
</div>

<!-- Recent Trades Table -->
<div class="table-container">
    <div class="table-header">
        <h2 class="table-title">Recent Closed Trades</h2>
    </div>
    <table>
        <thead>
            <tr>
                <th>Symbol</th>
                <th>Strategy</th>
                <th>Entry</th>
                <th>Exit</th>
                <th>P&L %</th>
                <th>P&L $</th>
                <th>Exit Reason</th>
                <th>Duration</th>
            </tr>
        </thead>
        <tbody id="closedTradesTable">
            <tr><td colspan="8" style="text-align: center;">Loading trades...</td></tr>
        </tbody>
    </table>
</div>
"""

# Strategies Page Template
STRATEGIES_TEMPLATE = r"""
<h1 class="page-title">Trading Strategies</h1>
<p class="subtitle">Active strategies and current market signals</p>

<!-- Strategy Status Grid -->
<div class="stats-container" id="strategyStats">
    <div class="stat-card">
        <div class="stat-label">DCA Strategy</div>
        <div class="stat-value" id="dcaStatus">
            <span class="badge badge-strategy">ACTIVE</span>
        </div>
    </div>
    <div class="stat-card">
        <div class="stat-label">SWING Strategy</div>
        <div class="stat-value" id="swingStatus">
            <span class="badge badge-strategy">ACTIVE</span>
        </div>
    </div>
    <div class="stat-card">
        <div class="stat-label">CHANNEL Strategy</div>
        <div class="stat-value" id="channelStatus">
            <span class="badge badge-strategy">ACTIVE</span>
        </div>
    </div>
</div>

<!-- Current Signals -->
<div class="table-container">
    <div class="table-header">
        <h2 class="table-title">Current Strategy Signals</h2>
    </div>
    <table>
        <thead>
            <tr>
                <th>Strategy</th>
                <th>Symbol</th>
                <th>Signal Strength</th>
                <th>Confidence</th>
                <th>Current Price</th>
                <th>Target</th>
                <th>Notes</th>
            </tr>
        </thead>
        <tbody id="strategySignalsTable">
            <tr><td colspan="7" style="text-align: center;">Loading signals...</td></tr>
        </tbody>
    </table>
</div>

<!-- Strategy Guide -->
<div class="table-container">
    <div class="table-header">
        <h2 class="table-title">Strategy Guide</h2>
    </div>
    <div style="padding: 20px;">
        <h3 style="color: #60a5fa; margin-bottom: 15px;">DCA (Dollar Cost Averaging)</h3>
        <p style="margin-bottom: 20px; color: #94a3b8;">
            Buys on significant dips to capture oversold conditions.
            Triggers when price drops 5%+ from recent highs with RSI < 30.
        </p>

        <h3 style="color: #60a5fa; margin-bottom: 15px;">SWING Trading</h3>
        <p style="margin-bottom: 20px; color: #94a3b8;">
            Captures momentum breakouts. Enters when price breaks above resistance
            with strong volume confirmation and RSI between 50-70.
        </p>

        <h3 style="color: #60a5fa; margin-bottom: 15px;">CHANNEL Trading</h3>
        <p style="margin-bottom: 20px; color: #94a3b8;">
            Trades within established price channels. Buys near support levels
            when price is in lower 30% of channel range. Most sensitive to volatility.
        </p>
    </div>
</div>
"""

# Market Page Template
MARKET_TEMPLATE = r"""
<h1 class="page-title">Market Analysis & Protection</h1>
<p class="subtitle">Real-time market conditions and protection status</p>

<!-- Market Protection Alert -->
<div id="regimeAlert"></div>

<!-- Market Protection Stats -->
<div class="stats-container">
    <div class="stat-card">
        <div class="stat-label">Market Regime</div>
        <div class="stat-value" id="marketRegime">Loading...</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">24h Volatility</div>
        <div class="stat-value" id="volatility24h">Loading...</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">BTC 24h Change</div>
        <div class="stat-value" id="btc24hChange">Loading...</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Protected Symbols</div>
        <div class="stat-value" id="protectedSymbols">Loading...</div>
    </div>
</div>

<!-- Disabled Strategies -->
<div class="table-container" id="disabledStrategiesContainer" style="display: none;">
    <div class="table-header">
        <h2 class="table-title">⚠️ Disabled Strategies</h2>
    </div>
    <table>
        <thead>
            <tr>
                <th>Strategy</th>
                <th>Reason</th>
                <th>Disabled At</th>
                <th>Re-enable At</th>
                <th>Time Remaining</th>
            </tr>
        </thead>
        <tbody id="disabledStrategiesTable">
        </tbody>
    </table>
</div>

<!-- Symbols on Cooldown -->
<div class="table-container" id="cooldownContainer" style="display: none;">
    <div class="table-header">
        <h2 class="table-title">🔒 Symbols on Cooldown</h2>
    </div>
    <table>
        <thead>
            <tr>
                <th>Symbol</th>
                <th>Reason</th>
                <th>Consecutive Stops</th>
                <th>Cooldown Until</th>
                <th>Time Remaining</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody id="cooldownTable">
        </tbody>
    </table>
</div>

<!-- Market Summary -->
<div class="table-container">
    <div class="table-header">
        <h2 class="table-title">Market Summary</h2>
    </div>
    <div style="padding: 20px;">
        <div id="marketSummaryContent">
            <p style="color: #94a3b8;">Loading market analysis...</p>
        </div>
    </div>
</div>

<!-- Top Movers -->
<div class="table-container">
    <div class="table-header">
        <h2 class="table-title">Top Market Movers (24h)</h2>
    </div>
    <table>
        <thead>
            <tr>
                <th>Symbol</th>
                <th>Price</th>
                <th>24h Change</th>
                <th>Volume</th>
                <th>Market Cap Tier</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody id="topMoversTable">
            <tr><td colspan="6" style="text-align: center;">Loading market data...</td></tr>
        </tbody>
    </table>
</div>
"""

# JavaScript for Paper Trading page
PAPER_TRADING_SCRIPTS = r"""
<script>
async function fetchTrades() {
    try {
        const response = await fetch('/api/trades');
        const data = await response.json();

        // Update portfolio stats
        document.getElementById('currentBalance').textContent =
            `$${(data.stats.starting_capital + data.stats.total_pnl_dollar).toFixed(2)}`;

        const pnlElement = document.getElementById('totalPnl');
        pnlElement.textContent = `$${data.stats.total_pnl_dollar.toFixed(2)}`;
        pnlElement.className = `stat-value ${data.stats.total_pnl_dollar >= 0 ? 'positive' : 'negative'}`;

        const winRateElement = document.getElementById('winRate');
        winRateElement.textContent = `${data.stats.win_rate.toFixed(1)}%`;
        winRateElement.className = `stat-value ${data.stats.win_rate >= 50 ? 'positive' : 'negative'}`;

        document.getElementById('openPositions').textContent = data.stats.open_count;

        // Update open positions table
        const openTable = document.getElementById('openPositionsTable');
        if (data.open_trades && data.open_trades.length > 0) {
            openTable.innerHTML = data.open_trades.map(trade => `
                <tr>
                    <td style="font-weight: 600;">${trade.symbol}</td>
                    <td><span class="badge badge-strategy">${trade.strategy}</span></td>
                    <td>$${trade.entry_price.toFixed(4)}</td>
                    <td>$${trade.current_price ? trade.current_price.toFixed(4) : 'N/A'}</td>
                    <td class="${trade.unrealized_pnl_pct >= 0 ? 'positive' : 'negative'}">
                        ${trade.unrealized_pnl_pct.toFixed(2)}%
                    </td>
                    <td class="${trade.unrealized_pnl >= 0 ? 'positive' : 'negative'}">
                        $${trade.unrealized_pnl.toFixed(2)}
                    </td>
                    <td>${trade.hold_time}</td>
                    <td>${trade.exit_strategy || 'HOLDING'}</td>
                </tr>
            `).join('');
        } else {
            openTable.innerHTML = '<tr><td colspan="8" style="text-align: center;">No open positions</td></tr>';
        }

        // Update closed trades table
        const closedTable = document.getElementById('closedTradesTable');
        const closedTrades = data.trades.filter(t => t.status === 'closed').slice(0, 10);

        if (closedTrades.length > 0) {
            closedTable.innerHTML = closedTrades.map(trade => `
                <tr>
                    <td style="font-weight: 600;">${trade.symbol}</td>
                    <td><span class="badge badge-strategy">${trade.strategy}</span></td>
                    <td>$${trade.entry_price.toFixed(4)}</td>
                    <td>$${trade.exit_price.toFixed(4)}</td>
                    <td class="${trade.pnl_pct >= 0 ? 'positive' : 'negative'}">
                        ${trade.pnl_pct.toFixed(2)}%
                    </td>
                    <td class="${trade.pnl >= 0 ? 'positive' : 'negative'}">
                        $${trade.pnl.toFixed(2)}
                    </td>
                    <td>${trade.exit_reason || 'manual'}</td>
                    <td>${trade.hold_time}</td>
                </tr>
            `).join('');
        } else {
            closedTable.innerHTML = '<tr><td colspan="8" style="text-align: center;">No closed trades yet</td></tr>';
        }

    } catch (error) {
        console.error('Error fetching trades:', error);
    }
}

// Initial load and refresh
fetchTrades();
setInterval(fetchTrades, 10000); // Refresh every 10 seconds
</script>
"""

# JavaScript for Strategies page
STRATEGIES_SCRIPTS = r"""
<script>
async function fetchStrategyStatus() {
    try {
        const response = await fetch('/api/strategy-status');
        const data = await response.json();

        // Update strategy signals table
        const signalsTable = document.getElementById('strategySignalsTable');
        const allSignals = [];

        // Process each strategy
        ['dca', 'swing', 'channel'].forEach(strategy => {
            if (data[strategy] && data[strategy].candidates) {
                data[strategy].candidates.forEach(candidate => {
                    allSignals.push({
                        strategy: strategy.toUpperCase(),
                        symbol: candidate.symbol,
                        strength: candidate.signal_strength || candidate.drop_pct || candidate.breakout_pct || 0,
                        confidence: candidate.confidence || 0,
                        price: candidate.current_price,
                        target: candidate.target_price || 0,
                        notes: candidate.reason || ''
                    });
                });
            }
        });

        if (allSignals.length > 0) {
            // Sort by confidence
            allSignals.sort((a, b) => b.confidence - a.confidence);

            signalsTable.innerHTML = allSignals.slice(0, 20).map(signal => `
                <tr>
                    <td><span class="badge badge-strategy">${signal.strategy}</span></td>
                    <td style="font-weight: 600;">${signal.symbol}</td>
                    <td>${signal.strength.toFixed(2)}%</td>
                    <td class="${signal.confidence >= 0.7 ? 'positive' : signal.confidence >= 0.5 ? 'neutral' : 'negative'}">
                        ${(signal.confidence * 100).toFixed(1)}%
                    </td>
                    <td>$${signal.price ? signal.price.toFixed(4) : 'N/A'}</td>
                    <td>${signal.target ? `$${signal.target.toFixed(4)}` : 'N/A'}</td>
                    <td style="font-size: 0.85rem; color: #94a3b8;">${signal.notes}</td>
                </tr>
            `).join('');
        } else {
            signalsTable.innerHTML = '<tr><td colspan="7" style="text-align: center;">No active signals</td></tr>';
        }

        // Check if strategies are disabled (from market protection)
        checkStrategyStatus();

    } catch (error) {
        console.error('Error fetching strategy status:', error);
    }
}

async function checkStrategyStatus() {
    try {
        const response = await fetch('/api/market-protection');
        const data = await response.json();

        // Update strategy status badges
        ['dca', 'swing', 'channel'].forEach(strategy => {
            const statusElement = document.getElementById(`${strategy}Status`);
            const isDisabled = data.disabled_strategies.includes(strategy.toUpperCase());

            if (isDisabled) {
                statusElement.innerHTML = '<span class="badge badge-disabled">DISABLED</span>';
            } else {
                statusElement.innerHTML = '<span class="badge badge-strategy">ACTIVE</span>';
            }
        });

    } catch (error) {
        console.error('Error checking strategy status:', error);
    }
}

// Initial load and refresh
fetchStrategyStatus();
setInterval(fetchStrategyStatus, 30000); // Refresh every 30 seconds
</script>
"""

# JavaScript for Market page
MARKET_SCRIPTS = r"""
<script>
async function fetchMarketProtection() {
    try {
        const response = await fetch('/api/market-protection');
        const data = await response.json();

        // Update regime alert
        const alertDiv = document.getElementById('regimeAlert');
        if (data.regime === 'PANIC') {
            alertDiv.innerHTML = `
                <div class="alert alert-panic">
                    🚨 <strong>PANIC MODE ACTIVE</strong> - All trading suspended due to extreme market conditions
                </div>
            `;
        } else if (data.regime === 'CAUTION') {
            alertDiv.innerHTML = `
                <div class="alert alert-caution">
                    ⚠️ <strong>CAUTION MODE</strong> - Trading restricted due to high volatility
                </div>
            `;
        } else {
            alertDiv.innerHTML = `
                <div class="alert alert-normal">
                    ✅ <strong>NORMAL MARKET</strong> - All systems operational
                </div>
            `;
        }

        // Update stats
        document.getElementById('marketRegime').innerHTML =
            `<span class="badge ${data.regime === 'PANIC' ? 'badge-disabled' : data.regime === 'CAUTION' ? 'badge-cooldown' : 'badge-strategy'}">${data.regime}</span>`;

        const volatilityElement = document.getElementById('volatility24h');
        volatilityElement.textContent = `${data.volatility_24h.toFixed(2)}%`;
        volatilityElement.className = `stat-value ${data.volatility_24h > 10 ? 'negative' : data.volatility_24h > 7 ? 'neutral' : 'positive'}`;

        const btcElement = document.getElementById('btc24hChange');
        btcElement.textContent = `${data.btc_24h_change.toFixed(2)}%`;
        btcElement.className = `stat-value ${data.btc_24h_change >= 0 ? 'positive' : 'negative'}`;

        const protectedCount = data.symbols_on_cooldown.length + data.symbols_banned.length;
        document.getElementById('protectedSymbols').textContent = protectedCount;

        // Update disabled strategies table
        if (data.disabled_strategies && data.disabled_strategies.length > 0) {
            document.getElementById('disabledStrategiesContainer').style.display = 'block';
            const disabledTable = document.getElementById('disabledStrategiesTable');
            disabledTable.innerHTML = data.disabled_strategies.map(strategy => {
                const info = data.strategy_info[strategy] || {};
                return `
                    <tr>
                        <td><span class="badge badge-disabled">${strategy}</span></td>
                        <td>${info.reason || 'High volatility'}</td>
                        <td>${info.disabled_at || 'N/A'}</td>
                        <td>${info.reenable_at || 'When volatility < 6%'}</td>
                        <td>${info.time_remaining || 'N/A'}</td>
                    </tr>
                `;
            }).join('');
        } else {
            document.getElementById('disabledStrategiesContainer').style.display = 'none';
        }

        // Update cooldown table
        const cooldownSymbols = [...data.symbols_on_cooldown, ...data.symbols_banned];
        if (cooldownSymbols.length > 0) {
            document.getElementById('cooldownContainer').style.display = 'block';
            const cooldownTable = document.getElementById('cooldownTable');
            cooldownTable.innerHTML = cooldownSymbols.map(item => `
                <tr>
                    <td style="font-weight: 600;">${item.symbol}</td>
                    <td>${item.reason}</td>
                    <td>${item.consecutive_stops || 0}</td>
                    <td>${item.cooldown_until}</td>
                    <td>${item.time_remaining}</td>
                    <td><span class="badge ${item.status === 'BANNED' ? 'badge-disabled' : 'badge-cooldown'}">${item.status}</span></td>
                </tr>
            `).join('');
        } else {
            document.getElementById('cooldownContainer').style.display = 'none';
        }

    } catch (error) {
        console.error('Error fetching market protection:', error);
    }
}

async function fetchMarketData() {
    try {
        const response = await fetch('/api/market-summary');
        const data = await response.json();

        // Update market summary
        const summaryDiv = document.getElementById('marketSummaryContent');
        summaryDiv.innerHTML = `
            <h3 style="color: #60a5fa; margin-bottom: 10px;">Market Condition: ${data.condition}</h3>
            <p style="color: #94a3b8; margin-bottom: 10px;">Best Strategy: <strong>${data.best_strategy}</strong></p>
            <p style="color: #94a3b8;">${data.notes}</p>
        `;

        // Update top movers table
        if (data.top_movers && data.top_movers.length > 0) {
            const moversTable = document.getElementById('topMoversTable');
            moversTable.innerHTML = data.top_movers.map(mover => `
                <tr>
                    <td style="font-weight: 600;">${mover.symbol}</td>
                    <td>$${mover.price.toFixed(4)}</td>
                    <td class="${mover.change_24h >= 0 ? 'positive' : 'negative'}">
                        ${mover.change_24h.toFixed(2)}%
                    </td>
                    <td>$${(mover.volume / 1000000).toFixed(2)}M</td>
                    <td>${mover.tier}</td>
                    <td>${mover.tradeable ? '✅' : '🔒'}</td>
                </tr>
            `).join('');
        }

    } catch (error) {
        console.error('Error fetching market data:', error);
    }
}

// Initial load and refresh
fetchMarketProtection();
fetchMarketData();
setInterval(fetchMarketProtection, 10000); // Refresh every 10 seconds
setInterval(fetchMarketData, 60000); // Refresh every minute
</script>
"""


@app.route("/")
def paper_trading():
    """Paper Trading page (default homepage)"""
    return render_template_string(
        BASE_TEMPLATE,
        title="Paper Trading",
        active_page="paper_trading",
        base_css=BASE_CSS,
        page_css="",
        content=PAPER_TRADING_TEMPLATE,
        page_scripts=PAPER_TRADING_SCRIPTS,
    )


@app.route("/strategies")
def strategies():
    """Strategies page"""
    return render_template_string(
        BASE_TEMPLATE,
        title="Strategies",
        active_page="strategies",
        base_css=BASE_CSS,
        page_css="",
        content=STRATEGIES_TEMPLATE,
        page_scripts=STRATEGIES_SCRIPTS,
    )


@app.route("/market")
def market():
    """Market analysis and protection page"""
    return render_template_string(
        BASE_TEMPLATE,
        title="Market Analysis",
        active_page="market",
        base_css=BASE_CSS,
        page_css="",
        content=MARKET_TEMPLATE,
        page_scripts=MARKET_SCRIPTS,
    )


@app.route("/api/market-protection")
def get_market_protection():
    """API endpoint for market protection status"""
    try:
        # Get regime stats
        regime_stats = regime_detector.get_regime_stats()

        # Get trade limiter stats
        limiter_stats = trade_limiter.get_limiter_stats()

        # Format response
        response = {
            "regime": regime_stats["current_regime"],
            "btc_1h_change": regime_stats.get("btc_1h_change", 0) or 0,
            "btc_4h_change": regime_stats.get("btc_4h_change", 0) or 0,
            "btc_24h_change": regime_stats.get("btc_24h_change", 0) or 0,
            "volatility_24h": regime_stats.get("volatility_24h", 0) or 0,
            "volatility_smoothed": regime_stats.get("volatility_smoothed", 0) or 0,
            "disabled_strategies": list(regime_stats.get("disabled_strategies", [])),
            "strategy_info": {},
            "symbols_on_cooldown": [],
            "symbols_banned": [],
        }

        # Add strategy disable info
        for strategy in response["disabled_strategies"]:
            reenable_time = regime_stats.get("strategy_reenable_times", {}).get(
                strategy
            )
            if reenable_time:
                time_remaining = (reenable_time - datetime.now()).total_seconds()
                if time_remaining > 0:
                    hours = int(time_remaining // 3600)
                    minutes = int((time_remaining % 3600) // 60)
                    response["strategy_info"][strategy] = {
                        "reason": f"Volatility > {regime_detector.strategy_volatility_limits.get(strategy, 0)}%",
                        "disabled_at": (reenable_time - timedelta(hours=2)).strftime(
                            "%H:%M"
                        ),
                        "reenable_at": reenable_time.strftime("%H:%M"),
                        "time_remaining": f"{hours}h {minutes}m",
                    }

        # Add cooldown symbols
        for symbol, until in limiter_stats["symbols_on_cooldown"].items():
            time_remaining = (until - datetime.now()).total_seconds()
            if time_remaining > 0:
                hours = int(time_remaining // 3600)
                minutes = int((time_remaining % 3600) // 60)
                response["symbols_on_cooldown"].append(
                    {
                        "symbol": symbol,
                        "reason": "Stop loss cooldown",
                        "cooldown_until": until.strftime("%H:%M"),
                        "time_remaining": f"{hours}h {minutes}m",
                        "status": "COOLDOWN",
                        "consecutive_stops": limiter_stats.get(
                            "consecutive_stops", {}
                        ).get(symbol, 0),
                    }
                )

        # Add banned symbols
        for symbol in limiter_stats["symbols_banned"]:
            response["symbols_banned"].append(
                {
                    "symbol": symbol,
                    "reason": "3+ consecutive stops",
                    "cooldown_until": "Manual reset required",
                    "time_remaining": "∞",
                    "status": "BANNED",
                    "consecutive_stops": 3,
                }
            )

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error getting market protection status: {e}")
        return jsonify(
            {
                "regime": "NORMAL",
                "btc_24h_change": 0,
                "volatility_24h": 0,
                "disabled_strategies": [],
                "symbols_on_cooldown": [],
                "symbols_banned": [],
                "error": str(e),
            }
        )


@app.route("/api/market-summary")
def get_market_summary():
    """API endpoint for market summary data"""
    try:
        db = SupabaseClient()

        # Try to get from cache first
        try:
            cache_result = (
                db.client.table("strategy_cache")
                .select("*")
                .eq("cache_key", "market_summary")
                .single()
                .execute()
            )

            if cache_result.data:
                summary = cache_result.data.get("cache_value", {})
                return jsonify(
                    {
                        "condition": summary.get("condition", "NORMAL"),
                        "best_strategy": summary.get("best_strategy", "WAIT"),
                        "notes": summary.get("notes", ""),
                        "top_movers": [],  # Would need separate query for this
                    }
                )
        except:
            pass

        return jsonify(
            {
                "condition": "CALCULATING",
                "best_strategy": "WAIT",
                "notes": "Market data being analyzed...",
                "top_movers": [],
            }
        )

    except Exception as e:
        logger.error(f"Error getting market summary: {e}")
        return jsonify(
            {
                "condition": "ERROR",
                "best_strategy": "WAIT",
                "notes": str(e),
                "top_movers": [],
            }
        )


# Copy over the existing API endpoints from the original dashboard
@app.route("/api/trades")
def get_trades():
    """API endpoint to get current trades data - using trade_group_id for proper grouping"""
    from datetime import datetime, timezone

    try:
        db = SupabaseClient()

        # Get all trades
        result = (
            db.client.table("paper_trades")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )

        trades_data = []
        open_trades = []

        # Initialize portfolio metrics
        STARTING_CAPITAL = 10000.0  # Default starting capital for paper trading

        stats = {
            "open_count": 0,
            "closed_count": 0,
            "win_count": 0,
            "loss_count": 0,
            "win_rate": 0,
            "total_pnl": 0,
            "total_pnl_dollar": 0,
            "starting_capital": STARTING_CAPITAL,
        }

        if result.data:
            # Get current prices
            symbols = list(
                set(trade["symbol"] for trade in result.data if trade["symbol"])
            )
            current_prices = {}

            for symbol in symbols:
                try:
                    price_result = (
                        db.client.table("ohlc_data")
                        .select("close")
                        .eq("symbol", symbol)
                        .order("timestamp", desc=True)
                        .limit(1)
                        .execute()
                    )

                    if price_result.data:
                        current_prices[symbol] = float(price_result.data[0]["close"])
                except Exception:
                    pass

            # Group trades by trade_group_id
            trades_by_group = {}

            for trade in result.data:
                group_id = trade.get("trade_group_id")

                if group_id:
                    if group_id not in trades_by_group:
                        trades_by_group[group_id] = {
                            "buys": [],
                            "sells": [],
                            "symbol": trade["symbol"],
                            "strategy": trade.get("strategy_name", "N/A"),
                        }

                    if trade["side"] == "BUY":
                        trades_by_group[group_id]["buys"].append(trade)
                    else:
                        trades_by_group[group_id]["sells"].append(trade)

            # Process grouped trades
            for group_id, group_data in trades_by_group.items():
                symbol = group_data["symbol"]
                strategy = group_data["strategy"]
                current_price = current_prices.get(symbol)

                # Sort trades by created_at
                group_data["buys"].sort(key=lambda x: x["created_at"])
                group_data["sells"].sort(key=lambda x: x["created_at"])

                # Calculate aggregated entry data for multiple BUYs (DCA)
                if group_data["buys"]:
                    total_cost = 0
                    total_amount = 0
                    earliest_buy = None

                    for buy in group_data["buys"]:
                        cost = float(buy["position_size"])
                        amount = float(buy["amount"])
                        total_cost += cost
                        total_amount += amount
                        if not earliest_buy:
                            earliest_buy = buy

                    avg_entry_price = (
                        total_cost / total_amount if total_amount > 0 else 0
                    )

                    # Check if position is closed
                    is_closed = len(group_data["sells"]) > 0

                    if is_closed and group_data["sells"]:
                        # Closed position
                        exit_trade = group_data["sells"][-1]
                        exit_price = float(exit_trade["price"])
                        pnl = (exit_price - avg_entry_price) * total_amount
                        pnl_pct = (
                            ((exit_price - avg_entry_price) / avg_entry_price * 100)
                            if avg_entry_price > 0
                            else 0
                        )

                        stats["closed_count"] += 1
                        stats["total_pnl_dollar"] += pnl

                        if pnl > 0:
                            stats["win_count"] += 1

                        # Calculate hold time
                        entry_time = datetime.fromisoformat(
                            earliest_buy["created_at"].replace("Z", "+00:00")
                        )
                        exit_time = datetime.fromisoformat(
                            exit_trade["created_at"].replace("Z", "+00:00")
                        )
                        hold_duration = exit_time - entry_time
                        hours = int(hold_duration.total_seconds() / 3600)
                        minutes = int((hold_duration.total_seconds() % 3600) / 60)
                        hold_time = f"{hours}h {minutes}m"

                        trades_data.append(
                            {
                                "symbol": symbol,
                                "strategy": strategy,
                                "status": "closed",
                                "entry_price": avg_entry_price,
                                "exit_price": exit_price,
                                "pnl": pnl,
                                "pnl_pct": pnl_pct,
                                "hold_time": hold_time,
                                "exit_reason": exit_trade.get("exit_reason", "manual"),
                            }
                        )
                    else:
                        # Open position
                        stats["open_count"] += 1

                        if current_price:
                            unrealized_pnl = (
                                current_price - avg_entry_price
                            ) * total_amount
                            unrealized_pnl_pct = (
                                (
                                    (current_price - avg_entry_price)
                                    / avg_entry_price
                                    * 100
                                )
                                if avg_entry_price > 0
                                else 0
                            )
                        else:
                            unrealized_pnl = 0
                            unrealized_pnl_pct = 0

                        # Calculate hold time
                        entry_time = datetime.fromisoformat(
                            earliest_buy["created_at"].replace("Z", "+00:00")
                        )
                        hold_duration = datetime.now(timezone.utc) - entry_time
                        hours = int(hold_duration.total_seconds() / 3600)
                        minutes = int((hold_duration.total_seconds() % 3600) / 60)
                        hold_time = f"{hours}h {minutes}m"

                        open_trades.append(
                            {
                                "symbol": symbol,
                                "strategy": strategy,
                                "entry_price": avg_entry_price,
                                "current_price": current_price,
                                "unrealized_pnl": unrealized_pnl,
                                "unrealized_pnl_pct": unrealized_pnl_pct,
                                "hold_time": hold_time,
                                "position_size": total_cost,
                            }
                        )

        # Calculate win rate
        if stats["closed_count"] > 0:
            stats["win_rate"] = (stats["win_count"] / stats["closed_count"]) * 100
            stats["loss_count"] = stats["closed_count"] - stats["win_count"]

        return jsonify(
            {"trades": trades_data, "open_trades": open_trades, "stats": stats}
        )

    except Exception as e:
        logger.error(f"Error getting trades: {e}")
        return jsonify({"trades": [], "open_trades": [], "stats": {}, "error": str(e)})


@app.route("/api/strategy-status")
def get_strategy_status():
    """Get current strategy status from cache or calculate fresh"""
    try:
        db = SupabaseClient()
        strategy_status = {}

        # Try to get from cache first
        try:
            # Get DCA candidates
            dca_result = (
                db.client.table("strategy_cache")
                .select("*")
                .eq("cache_key", "dca_candidates")
                .single()
                .execute()
            )

            if dca_result.data:
                strategy_status["dca"] = {
                    "name": "DCA",
                    "thresholds": dca_result.data.get("cache_value", {}).get(
                        "thresholds", {}
                    ),
                    "candidates": dca_result.data.get("cache_value", {}).get(
                        "candidates", []
                    )[:10],
                }

            # Get Swing candidates
            swing_result = (
                db.client.table("strategy_cache")
                .select("*")
                .eq("cache_key", "swing_candidates")
                .single()
                .execute()
            )

            if swing_result.data:
                strategy_status["swing"] = {
                    "name": "SWING",
                    "thresholds": swing_result.data.get("cache_value", {}).get(
                        "thresholds", {}
                    ),
                    "candidates": swing_result.data.get("cache_value", {}).get(
                        "candidates", []
                    )[:10],
                }

            # Get Channel candidates
            channel_result = (
                db.client.table("strategy_cache")
                .select("*")
                .eq("cache_key", "channel_candidates")
                .single()
                .execute()
            )

            if channel_result.data:
                strategy_status["channel"] = {
                    "name": "CHANNEL",
                    "thresholds": channel_result.data.get("cache_value", {}).get(
                        "thresholds", {}
                    ),
                    "candidates": channel_result.data.get("cache_value", {}).get(
                        "candidates", []
                    )[:10],
                }

        except Exception as e:
            logger.warning(f"Cache not ready yet: {e}")

        return jsonify(strategy_status)

    except Exception as e:
        logger.error(f"Error getting strategy status: {e}")
        return jsonify({})


if __name__ == "__main__":
    import os

    # Get port from Railway or default to 8080 for local
    port = int(os.environ.get("PORT", 8080))

    print("\n" + "=" * 60)
    print("🚀 STARTING ENHANCED MULTI-PAGE DASHBOARD")
    print("=" * 60)

    if os.environ.get("RAILWAY_ENVIRONMENT"):
        print(f"\n📊 Dashboard running on Railway (port {port})")
        print("🌐 Access via your Railway public URL")
    else:
        print(f"\n📊 Dashboard URL: http://localhost:{port}")
        print("📄 Pages available:")
        print("   - Paper Trading: http://localhost:{port}/")
        print("   - Strategies: http://localhost:{port}/strategies")
        print("   - Market: http://localhost:{port}/market")

    print("\n✅ Dashboard server starting...")
    print("=" * 60 + "\n")

    # Run the Flask app
    app.run(host="0.0.0.0", port=port, debug=False)
