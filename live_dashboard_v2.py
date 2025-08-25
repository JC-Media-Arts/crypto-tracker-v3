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
        {{ base_css|safe }}
        {{ page_css|safe }}
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
        {{ content|safe }}
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
    {{ page_scripts|safe }}
</body>
</html>
"""

# Paper Trading Page Template
PAPER_TRADING_TEMPLATE = r"""
<h1 class="page-title">Paper Trading Dashboard</h1>
<p class="subtitle">Live paper trading performance and positions</p>

<!-- Engine Status Indicator -->
<div id="engineStatus" style="position: fixed; top: 80px; right: 200px; display: flex; align-items: center; gap: 8px; background: rgba(30, 41, 59, 0.9); padding: 8px 16px; border-radius: 8px; border: 1px solid rgba(148, 163, 184, 0.2);">
    <div id="statusLight" style="width: 12px; height: 12px; border-radius: 50%; background: #fbbf24;"></div>
    <span id="statusText" style="font-size: 0.875rem; color: #94a3b8;">Checking...</span>
</div>

<!-- Trade Filter -->
<div style="display: flex; justify-content: center; gap: 20px; margin-bottom: 25px; padding: 15px; background: rgba(30, 41, 59, 0.5); backdrop-filter: blur(10px); border: 1px solid rgba(148, 163, 184, 0.1); border-radius: 12px;">
    <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
        <input type="radio" name="tradeFilter" value="open" id="filterOpen" checked>
        <span style="color: #e2e8f0;">Open Trades Only</span>
    </label>
    <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
        <input type="radio" name="tradeFilter" value="all" id="filterAll">
        <span style="color: #e2e8f0;">Open & Closed Trades</span>
    </label>
    <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
        <input type="radio" name="tradeFilter" value="closed" id="filterClosed">
        <span style="color: #e2e8f0;">Closed Trades Only</span>
    </label>
</div>

<!-- Portfolio Stats -->
<div class="stats-container" id="portfolioStats">
    <div class="stat-card">
        <div class="stat-label">Current Balance</div>
        <div class="stat-value neutral" id="currentBalance">Loading...</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Total Investment</div>
        <div class="stat-value neutral" id="totalInvestment">Loading...</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Total P&L $</div>
        <div class="stat-value" id="totalPnl">Loading...</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Total P&L %</div>
        <div class="stat-value" id="totalPnlPct">Loading...</div>
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
                <th>Amount</th>
                <th>Entry Price</th>
                <th>DCA Status</th>
                <th>Current Price</th>
                <th>P&L %</th>
                <th>P&L $</th>
                <th>Duration</th>
                <th>SL</th>
                <th>TP</th>
                <th>TS</th>
                <th>Exit Reason</th>
            </tr>
        </thead>
        <tbody id="openPositionsTable">
            <tr><td colspan="13" style="text-align: center;">Loading positions...</td></tr>
        </tbody>
    </table>
</div>

<!-- Closed Trades Table (Hidden by default, shown based on filter) -->
<div class="table-container" id="closedTradesContainer" style="display: none;">
    <div class="table-header">
        <h2 class="table-title">Closed Trades</h2>
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
                <th>Readiness</th>
                <th>Confidence</th>
                <th>Current Price</th>
                <th>Status</th>
                <th>Details</th>
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
        <div class="stat-label">Protection Level</div>
        <div class="stat-value" id="marketRegime">Loading...</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Market Volatility</div>
        <div class="stat-value" id="volatility24h">Loading...</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">BTC Movement</div>
        <div class="stat-value" id="btc24hChange">Loading...</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Symbols on Cooldown</div>
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

<!-- Trading Sentiment -->
<div class="table-container">
    <div class="table-header">
        <h2 class="table-title">Trading Sentiment</h2>
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
                <th>Readiness</th>
                <th>Volume</th>
                <th>Type</th>
                <th>Signal</th>
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
let allTradesData = { open_trades: [], trades: [], stats: {} };
let currentFilter = 'open';

async function checkEngineStatus() {
    try {
        const response = await fetch('/api/engine-status');
        const data = await response.json();

        const statusLight = document.getElementById('statusLight');
        const statusText = document.getElementById('statusText');

        if (data.running) {
            statusLight.style.background = '#10b981'; // green
            statusText.textContent = 'Paper Trading Active';
            statusText.style.color = '#10b981';
        } else {
            statusLight.style.background = '#ef4444'; // red
            statusText.textContent = 'Paper Trading Stopped';
            statusText.style.color = '#ef4444';
        }
    } catch (error) {
        const statusLight = document.getElementById('statusLight');
        const statusText = document.getElementById('statusText');
        statusLight.style.background = '#fbbf24'; // yellow
        statusText.textContent = 'Status Unknown';
        statusText.style.color = '#fbbf24';
    }
}

async function fetchTrades() {
    try {
        const response = await fetch('/api/trades');
        const data = await response.json();
        allTradesData = data;

        // Always update constant stats
        document.getElementById('currentBalance').textContent =
            `$${(data.stats.starting_capital + data.stats.total_pnl_dollar).toFixed(2)}`;

        document.getElementById('totalInvestment').textContent =
            `$${data.stats.starting_capital.toFixed(2)}`;

        document.getElementById('openPositions').textContent = data.stats.open_count;

        // Update filtered view
        updateFilteredView();
    } catch (error) {
        console.error('Error fetching trades:', error);
    }
}

function updateFilteredView() {
    const data = allTradesData;
    const openTable = document.getElementById('openPositionsTable');
    const closedTable = document.getElementById('closedTradesTable');

    // Calculate stats based on filter
    let filteredPnl = 0;
    let winCount = 0;
    let lossCount = 0;
    let totalTrades = 0;

    if (currentFilter === 'open' || currentFilter === 'all') {
        // Show open positions
        if (data.open_trades && data.open_trades.length > 0) {
            openTable.innerHTML = data.open_trades.map(trade => `
                <tr>
                    <td style="font-weight: 600;">${trade.symbol}</td>
                    <td><span class="badge badge-strategy">${trade.strategy}</span></td>
                    <td>${trade.amount ? trade.amount.toFixed(6) : 'N/A'}</td>
                    <td>$${trade.entry_price.toFixed(4)}</td>
                    <td>${trade.dca_status || '-'}</td>
                    <td>$${trade.current_price ? trade.current_price.toFixed(4) : 'N/A'}</td>
                    <td class="${trade.unrealized_pnl_pct >= 0 ? 'positive' : 'negative'}">
                        ${trade.unrealized_pnl_pct.toFixed(2)}%
                    </td>
                    <td class="${trade.unrealized_pnl >= 0 ? 'positive' : 'negative'}">
                        $${trade.unrealized_pnl.toFixed(2)}
                    </td>
                    <td>${trade.hold_time}</td>
                    <td>${trade.sl_display || '<span style="color: #6b7280;">Not Set</span>'}</td>
                    <td>${trade.tp_display || '<span style="color: #6b7280;">Not Set</span>'}</td>
                    <td>${trade.ts_display || '<span style="color: #6b7280;">Not Set</span>'}</td>
                    <td>${trade.exit_reason || '—'}</td>
                </tr>
            `).join('');

            // Add unrealized P&L to stats if showing open
            data.open_trades.forEach(trade => {
                filteredPnl += trade.unrealized_pnl || 0;
            });
        } else {
            openTable.innerHTML = '<tr><td colspan="13" style="text-align: center;">No open positions</td></tr>';
        }
        document.getElementById('openPositionsTable').parentElement.style.display = 'block';
    } else {
        document.getElementById('openPositionsTable').parentElement.style.display = 'none';
    }

    if (currentFilter === 'closed' || currentFilter === 'all') {
        // Show closed trades
        const closedTrades = data.trades ? data.trades.filter(t => t.status === 'closed') : [];

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

            // Calculate stats for closed trades
            closedTrades.forEach(trade => {
                filteredPnl += trade.pnl || 0;
                totalTrades++;
                if (trade.pnl > 0) winCount++;
                else lossCount++;
            });
        } else {
            closedTable.innerHTML = '<tr><td colspan="8" style="text-align: center;">No closed trades yet</td></tr>';
        }
        document.getElementById('closedTradesContainer').style.display = 'block';
    } else {
        document.getElementById('closedTradesContainer').style.display = 'none';
    }

    // Update dynamic stats based on filter
    const pnlElement = document.getElementById('totalPnl');
    const pnlToShow = currentFilter === 'open' ? filteredPnl :
                      currentFilter === 'closed' ? filteredPnl :
                      data.stats.total_pnl_dollar + (filteredPnl || 0);
    pnlElement.textContent = `$${pnlToShow.toFixed(2)}`;
    pnlElement.className = `stat-value ${pnlToShow >= 0 ? 'positive' : 'negative'}`;

    // Calculate P&L %
    const pnlPctElement = document.getElementById('totalPnlPct');
    const pnlPct = (pnlToShow / data.stats.starting_capital) * 100;
    pnlPctElement.textContent = `${pnlPct.toFixed(2)}%`;
    pnlPctElement.className = `stat-value ${pnlPct >= 0 ? 'positive' : 'negative'}`;

    // Update win rate based on filter
    const winRateElement = document.getElementById('winRate');
    let winRate = 0;
    if (currentFilter === 'closed' && totalTrades > 0) {
        winRate = (winCount / totalTrades) * 100;
    } else if (currentFilter === 'all') {
        winRate = data.stats.win_rate || 0;
    } else if (currentFilter === 'open') {
        winRate = 0; // No win rate for open positions
    }
    winRateElement.textContent = `${winRate.toFixed(1)}%`;
    winRateElement.className = `stat-value ${winRate >= 50 ? 'positive' : winRate > 0 ? 'neutral' : ''}`;
}

// Add event listeners for filters
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('input[name="tradeFilter"]').forEach(radio => {
        radio.addEventListener('change', function() {
            currentFilter = this.value;
            updateFilteredView();
        });
    });

    // Initial load
    fetchTrades();
    checkEngineStatus();

    // Set up refresh intervals
    setInterval(fetchTrades, 10000); // Refresh trades every 10 seconds
    setInterval(checkEngineStatus, 30000); // Check engine status every 30 seconds
});
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
                    // Parse readiness percentage
                    const readinessValue = parseFloat(candidate.readiness) || 0;

                    allSignals.push({
                        strategy: strategy.toUpperCase(),
                        symbol: candidate.symbol,
                        strength: readinessValue,  // Use readiness as strength
                        confidence: readinessValue / 100,  // Convert to 0-1 scale
                        price: candidate.price || 0,
                        status: candidate.status || '',
                        notes: candidate.details || ''
                    });
                });
            }
        });

        if (allSignals.length > 0) {
            // Sort by readiness/strength
            allSignals.sort((a, b) => b.strength - a.strength);

            signalsTable.innerHTML = allSignals.slice(0, 20).map(signal => `
                <tr>
                    <td><span class="badge badge-strategy">${signal.strategy}</span></td>
                    <td style="font-weight: 600;">${signal.symbol}</td>
                    <td>${signal.strength.toFixed(1)}%</td>
                    <td class="${signal.confidence >= 0.7 ? 'positive' : signal.confidence >= 0.5 ? 'neutral' : 'negative'}">
                        ${(signal.confidence * 100).toFixed(1)}%
                    </td>
                    <td>$${signal.price ? signal.price.toFixed(4) : 'N/A'}</td>
                    <td>${signal.status}</td>
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

        // Update trading sentiment
        const summaryDiv = document.getElementById('marketSummaryContent');
        let conditionColor = '#60a5fa';
        let conditionIcon = '📊';
        if (data.condition === 'BULLISH') {
            conditionColor = '#10b981';
            conditionIcon = '📈';
        } else if (data.condition === 'BEARISH') {
            conditionColor = '#ef4444';
            conditionIcon = '📉';
        }

        summaryDiv.innerHTML = `
            <h3 style="color: ${conditionColor}; margin-bottom: 10px;">${conditionIcon} Trading Condition: ${data.condition}</h3>
            <p style="color: #94a3b8; margin-bottom: 10px;">Recommended Strategy: <strong style="color: #60a5fa;">${data.best_strategy}</strong></p>
            <p style="color: #94a3b8; font-size: 0.9rem;">${data.notes}</p>
        `;

        // Update top movers table
        if (data.top_movers && data.top_movers.length > 0) {
            const moversTable = document.getElementById('topMoversTable');
            moversTable.innerHTML = data.top_movers.map(mover => `
                <tr>
                    <td style="font-weight: 600;">${mover.symbol}</td>
                    <td>$${mover.price ? mover.price.toFixed(4) : 'N/A'}</td>
                    <td class="positive">
                        ${mover.change_24h}%
                    </td>
                    <td>${mover.volume}</td>
                    <td>${mover.market_cap}</td>
                    <td>${mover.status}</td>
                </tr>
            `).join('');
        } else {
            document.getElementById('topMoversTable').innerHTML = '<tr><td colspan="6" style="text-align: center;">No active market movers</td></tr>';
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


@app.route("/api/engine-status")
def get_engine_status():
    """Check if paper trading engine is running"""
    try:
        # If running on Railway, check database for recent activity
        if os.environ.get("RAILWAY_ENVIRONMENT"):
            # Check for recent trades or scan history entries (within last 30 minutes)
            db = SupabaseClient()
            thirty_minutes_ago = (
                datetime.now(timezone.utc) - timedelta(minutes=30)
            ).isoformat()

            # Check for recent scan history (paper trading logs scans frequently)
            result = (
                db.client.table("scan_history")
                .select("timestamp")
                .gte("timestamp", thirty_minutes_ago)
                .limit(1)
                .execute()
            )

            # If we have recent scans, paper trading is running
            paper_trading_running = bool(result.data)

            # Also check for recent trades as backup
            if not paper_trading_running:
                trade_result = (
                    db.client.table("paper_trades")
                    .select("created_at")
                    .gte("created_at", thirty_minutes_ago)
                    .limit(1)
                    .execute()
                )
                paper_trading_running = bool(trade_result.data)

            return jsonify({"running": paper_trading_running, "source": "railway"})
        else:
            # Local check - look for process
            import subprocess

            result = subprocess.run(
                ["pgrep", "-f", "run_paper_trading"], capture_output=True, text=True
            )
            is_running = bool(result.stdout.strip())

            return jsonify(
                {
                    "running": is_running,
                    "pid": result.stdout.strip() if is_running else None,
                }
            )
    except Exception as e:
        logger.error(f"Error checking engine status: {e}")
        return jsonify({"running": False, "error": str(e)})


@app.route("/api/market-protection")
def get_market_protection():
    """API endpoint for market protection status"""
    try:
        # Get regime stats
        regime_stats = regime_detector.get_regime_stats()

        # Get trade limiter stats
        limiter_stats = trade_limiter.get_limiter_stats()

        # Try to get actual BTC data from database
        btc_24h_change = 0
        volatility = 0
        try:
            db = SupabaseClient()

            # Get recent BTC price data
            now = datetime.now()
            yesterday = now - timedelta(days=1)

            btc_data = (
                db.client.table("ohlc_data")
                .select("close, timestamp")
                .eq("symbol", "BTC")
                .gte("timestamp", yesterday.isoformat())
                .order("timestamp", desc=True)
                .limit(100)
                .execute()
            )

            if btc_data.data and len(btc_data.data) > 1:
                latest_price = btc_data.data[0].get("close", 0)
                oldest_price = btc_data.data[-1].get("close", 0)
                if oldest_price > 0:
                    btc_24h_change = (
                        (latest_price - oldest_price) / oldest_price
                    ) * 100

                # Calculate volatility from price range
                prices = [
                    d.get("close", 0) for d in btc_data.data if d.get("close", 0) > 0
                ]
                if len(prices) > 1:
                    volatility = ((max(prices) - min(prices)) / min(prices)) * 100

        except Exception as e:
            logger.debug(f"Could not get BTC data: {e}")

        # Format response
        response = {
            "regime": regime_stats["current_regime"],
            "btc_1h_change": regime_stats.get("btc_1h_change", 0) or 0,
            "btc_4h_change": regime_stats.get("btc_4h_change", 0) or 0,
            "btc_24h_change": btc_24h_change,
            "volatility_24h": volatility,
            "volatility_smoothed": regime_stats.get("volatility_smoothed", volatility)
            or volatility,
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

        # Add cooldown symbols (they come as a list of dicts)
        cooldown_symbols = limiter_stats.get("symbols_on_cooldown", [])
        if isinstance(cooldown_symbols, list):
            for item in cooldown_symbols:
                if isinstance(item, dict):
                    response["symbols_on_cooldown"].append(
                        {
                            "symbol": item.get("symbol", "Unknown"),
                            "reason": item.get("reason", "Stop loss cooldown"),
                            "cooldown_until": "Active",
                            "time_remaining": "Check limiter",
                            "status": "COOLDOWN",
                            "consecutive_stops": item.get("consecutive_stops", 0),
                        }
                    )

        # Add banned symbols (they also come as a list of dicts)
        banned_symbols = limiter_stats.get("symbols_banned", [])
        if isinstance(banned_symbols, list):
            for item in banned_symbols:
                if isinstance(item, dict):
                    response["symbols_banned"].append(
                        {
                            "symbol": item.get("symbol", "Unknown"),
                            "reason": item.get("reason", "3+ consecutive stops"),
                            "cooldown_until": "Manual reset required",
                            "time_remaining": "∞",
                            "status": "BANNED",
                            "consecutive_stops": item.get("consecutive_stops", 3),
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

        # Get top movers from strategy cache
        top_movers = []
        try:
            # Get top gainers from strategy status cache
            gainers = (
                db.client.table("strategy_status_cache")
                .select("symbol, current_price, readiness, status, strategy_name")
                .gte("readiness", 70)
                .order("readiness", desc=True)
                .limit(5)
                .execute()
            )

            if gainers.data:
                for item in gainers.data:
                    top_movers.append(
                        {
                            "symbol": item.get("symbol"),
                            "price": item.get("current_price", 0),
                            "change_24h": f"{item.get('readiness', 0):.1f}",  # Use readiness as proxy for momentum
                            "volume": "N/A",
                            "market_cap": "CRYPTO",
                            "status": item.get("status", ""),
                            "strategy": item.get("strategy_name", ""),
                        }
                    )
        except Exception as e:
            logger.debug(f"Could not get top movers: {e}")

        # Determine overall market condition
        condition = "NORMAL"
        best_strategy = "WAIT"
        total_symbols = len(top_movers)

        if total_symbols > 0:
            # If we have high readiness scores, market might be good
            avg_readiness = sum(float(m["change_24h"]) for m in top_movers) / len(
                top_movers
            )
            if avg_readiness > 80:
                condition = "BULLISH"
                best_strategy = "SWING"
            elif avg_readiness > 70:
                condition = "NORMAL"
                best_strategy = "DCA"

        return jsonify(
            {
                "condition": condition,
                "best_strategy": best_strategy,
                "notes": f"Monitoring {total_symbols} active signals",
                "top_movers": top_movers,
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
                        # Calculate position size from price and amount
                        price = float(buy.get("price", 0))
                        amount = float(buy.get("amount", 0))
                        cost = price * amount  # Calculate position size in USD
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

                        # Get additional fields from the first buy trade
                        stop_loss = earliest_buy.get("stop_loss")
                        take_profit = earliest_buy.get("take_profit")
                        trailing_stop = earliest_buy.get("trailing_stop_pct")

                        # Calculate SL/TP/TS displays
                        sl_display = None
                        tp_display = None
                        ts_display = None

                        if stop_loss:
                            sl_price = float(stop_loss)
                            sl_pnl = (
                                (sl_price - avg_entry_price) / avg_entry_price
                            ) * 100
                            sl_display = f"{unrealized_pnl_pct:.1f}% / {sl_pnl:.1f}%"

                        if take_profit:
                            tp_price = float(take_profit)
                            tp_pnl = (
                                (tp_price - avg_entry_price) / avg_entry_price
                            ) * 100
                            tp_display = f"{unrealized_pnl_pct:.1f}% / {tp_pnl:.1f}%"

                        if trailing_stop:
                            ts_pct = float(trailing_stop) * 100
                            if take_profit:
                                tp_price = float(take_profit)
                                tp_pnl = (
                                    (tp_price - avg_entry_price) / avg_entry_price
                                ) * 100
                                if unrealized_pnl_pct >= tp_pnl:
                                    ts_display = f"🟢 Active: {unrealized_pnl_pct:.1f}% / -{ts_pct:.1f}%"
                                else:
                                    ts_display = (
                                        f"⚪ Inactive (activates at TP: {tp_pnl:.1f}%)"
                                    )

                        # Determine DCA status
                        dca_status = (
                            "Single"
                            if len(group_data["buys"]) == 1
                            else f"DCA x{len(group_data['buys'])}"
                        )

                        open_trades.append(
                            {
                                "symbol": symbol,
                                "strategy": strategy,
                                "amount": total_amount,
                                "entry_price": avg_entry_price,
                                "dca_status": dca_status,
                                "current_price": current_price,
                                "unrealized_pnl": unrealized_pnl,
                                "unrealized_pnl_pct": unrealized_pnl_pct,
                                "hold_time": hold_time,
                                "sl_display": sl_display,
                                "tp_display": tp_display,
                                "ts_display": ts_display,
                                "position_size": total_cost,
                                "exit_reason": "",  # Open positions don't have exit reason
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
            # Get candidates by strategy name (readiness > 70 means ready)
            dca_results = (
                db.client.table("strategy_status_cache")
                .select("*")
                .eq("strategy_name", "DCA")
                .gte("readiness", 70)  # Readiness score >= 70 means ready
                .order("readiness", desc=True)
                .limit(10)
                .execute()
            )

            if dca_results.data:
                strategy_status["dca"] = {
                    "name": "DCA",
                    "thresholds": {},
                    "candidates": [
                        {
                            "symbol": item.get("symbol"),
                            "price": item.get("current_price", 0),
                            "readiness": f"{item.get('readiness', 0):.1f}%",
                            "status": item.get("status", ""),
                            "details": item.get("details", {}),
                        }
                        for item in dca_results.data
                    ],
                }

            # Get Swing candidates
            swing_results = (
                db.client.table("strategy_status_cache")
                .select("*")
                .eq("strategy_name", "SWING")
                .gte("readiness", 70)  # Readiness score >= 70 means ready
                .order("readiness", desc=True)
                .limit(10)
                .execute()
            )

            if swing_results.data:
                strategy_status["swing"] = {
                    "name": "SWING",
                    "thresholds": {},
                    "candidates": [
                        {
                            "symbol": item.get("symbol"),
                            "price": item.get("current_price", 0),
                            "readiness": f"{item.get('readiness', 0):.1f}%",
                            "status": item.get("status", ""),
                            "details": item.get("details", {}),
                        }
                        for item in swing_results.data
                    ],
                }

            # Get Channel candidates
            channel_results = (
                db.client.table("strategy_status_cache")
                .select("*")
                .eq("strategy_name", "CHANNEL")
                .gte("readiness", 70)  # Readiness score >= 70 means ready
                .order("readiness", desc=True)
                .limit(10)
                .execute()
            )

            if channel_results.data:
                strategy_status["channel"] = {
                    "name": "CHANNEL",
                    "thresholds": {},
                    "candidates": [
                        {
                            "symbol": item.get("symbol"),
                            "price": item.get("current_price", 0),
                            "readiness": f"{item.get('readiness', 0):.1f}%",
                            "status": item.get("status", ""),
                            "details": item.get("details", {}),
                        }
                        for item in channel_results.data
                    ],
                }

        except Exception as e:
            logger.warning(f"Cache not ready yet: {e}")

        return jsonify(strategy_status)

    except Exception as e:
        logger.error(f"Error getting strategy status: {e}")
        return jsonify({})


if __name__ == "__main__":
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
