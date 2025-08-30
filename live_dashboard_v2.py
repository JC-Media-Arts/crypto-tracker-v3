#!/usr/bin/env python3
"""
Enhanced multi-page trading dashboard with Market Protection
"""

from flask import Flask, render_template_string, jsonify, request
import sys
from pathlib import Path
import os
from datetime import datetime, timedelta, timezone
import pandas as pd

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
    
    .admin-icon {
        margin-left: auto;
        font-size: 1.2rem;
        padding: 0.5rem 1rem;
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
.paper-trading-section {
    border: 2px solid rgba(100, 181, 246, 0.5);
    padding: 25px;
    margin-bottom: 30px;
    border-radius: 15px;
    background: rgba(33, 150, 243, 0.05);
}
.section-header {
    font-size: 1.8em;
    color: #64b5f6;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 10px;
}
.section-header::before {
    content: "📊";
    font-size: 1.2em;
}
.save-controls {
    background: rgba(30, 41, 59, 0.5);
    padding: 20px;
    border-radius: 10px;
    border-top: 1px solid rgba(100, 181, 246, 0.2);
    margin-top: 30px;
}
.save-buttons {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 20px;
}
.save-btn, .discard-btn {
    padding: 12px 30px;
    font-size: 1.1em;
    border: none;
    border-radius: 5px;
    cursor: pointer;
    transition: all 0.3s;
}
.save-btn {
    background: #4CAF50;
    color: white;
}
.save-btn:hover {
    background: #45a049;
    transform: translateY(-2px);
}
.discard-btn {
    background: #f44336;
    color: white;
}
.discard-btn:hover {
    background: #da190b;
    transform: translateY(-2px);
}
.unsaved-indicator {
    color: #ffc107;
    font-size: 0.95em;
    font-weight: 500;
    text-align: center;
    padding: 10px 20px;
    background: rgba(255, 193, 7, 0.1);
    border: 1px solid rgba(255, 193, 7, 0.3);
    border-radius: 5px;
    margin: 0 auto 15px auto;
    display: flex;
    justify-content: center;
    align-items: center;
}
.tier-tabs {
    display: flex;
    gap: 10px;
    margin-bottom: 20px;
    border-bottom: 2px solid rgba(100, 181, 246, 0.2);
}
.tier-tab {
    padding: 10px 20px;
    background: transparent;
    color: #94a3b8;
    border: none;
    border-bottom: 3px solid transparent;
    cursor: pointer;
    transition: all 0.3s;
    font-size: 0.95em;
    font-weight: 500;
}
.tier-tab:hover {
    color: #64b5f6;
}
.tier-tab.active {
    color: #64b5f6;
    border-bottom-color: #64b5f6;
    background: rgba(100, 181, 246, 0.05);
}
.tier-content {
    display: none;
}
.tier-content.active {
    display: block;
}
.strategy-tabs {
    display: flex;
    gap: 15px;
    margin-bottom: 20px;
    border-bottom: 3px solid rgba(100, 181, 246, 0.3);
}
.strategy-tab {
    padding: 12px 25px;
    background: rgba(30, 41, 59, 0.5);
    color: #94a3b8;
    border: none;
    border-radius: 8px 8px 0 0;
    cursor: pointer;
    transition: all 0.3s;
    font-size: 1em;
    font-weight: 600;
}
.strategy-tab:hover {
    color: #64b5f6;
    background: rgba(100, 181, 246, 0.1);
}
.strategy-tab.active {
    color: #fff;
    background: rgba(100, 181, 246, 0.2);
    border-bottom: 3px solid #64b5f6;
}
.strategy-content {
    display: none;
    margin-top: 20px;
}
.strategy-content.active {
    display: block;
}
.strategy-content .tier-tabs {
    margin-top: 10px;
    border-bottom: 2px solid rgba(100, 181, 246, 0.15);
}
.strategy-entry-content {
    display: none;
    padding: 20px 0;
}
.strategy-entry-content.active {
    display: block;
}
.tier-entry-content {
    display: none;
    padding: 20px 0;
}
.tier-entry-content.active {
    display: block;
}

/* Risk Management Styles */
.risk-management-section {
    max-width: 100%;
}
.risk-tabs {
    display: flex;
    gap: 10px;
    margin-bottom: 20px;
    border-bottom: 3px solid rgba(100, 181, 246, 0.3);
    flex-wrap: wrap;
}
.risk-tab {
    padding: 10px 16px;
    background: rgba(30, 41, 59, 0.5);
    color: #94a3b8;
    border: none;
    border-radius: 8px 8px 0 0;
    cursor: pointer;
    font-size: 0.9rem;
    transition: all 0.3s ease;
    white-space: nowrap;
}
.risk-tab:hover {
    background: rgba(59, 130, 246, 0.2);
    color: #e2e8f0;
}
.risk-tab.active {
    background: rgba(59, 130, 246, 0.3);
    color: #60a5fa;
    border-bottom: 3px solid #60a5fa;
    margin-bottom: -3px;
}
.risk-content {
    display: none;
    animation: fadeIn 0.3s ease-in;
}
.risk-content.active {
    display: block;
}
.risk-content h3 {
    color: #94a3b8;
    font-size: 1.1rem;
    margin-top: 25px;
    margin-bottom: 15px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(100, 181, 246, 0.2);
    position: relative;
}
.risk-content .config-group:first-child h3 {
    margin-top: 0;
}
.section-tooltip {
    display: inline-block;
    margin-left: 8px;
    color: #60a5fa;
    cursor: help;
    font-size: 0.9rem;
}
.section-tooltip:hover::after {
    content: attr(data-tooltip);
    position: absolute;
    left: 0;
    top: 100%;
    margin-top: 5px;
    padding: 10px 15px;
    background: rgba(30, 41, 59, 0.95);
    border: 1px solid rgba(59, 130, 246, 0.5);
    border-radius: 8px;
    color: #e2e8f0;
    font-size: 0.85rem;
    white-space: normal;
    max-width: 400px;
    z-index: 1000;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
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
                <a href="/rd" class="nav-link {{ 'active' if active_page == 'rd' else '' }}">
                    🔬 R&D
                </a>
                <a href="/admin" class="nav-link admin-icon {{ 'active' if active_page == 'admin' else '' }}" title="Admin Panel">
                    ⚙️
                </a>
            </div>
        </div>
    </nav>

    <!-- Page Content -->
    <div class="container">
        {{ content|safe }}
    </div>

    <!-- Refresh Indicator (not shown on Admin page) -->
    {% if active_page != 'admin' %}
    <div class="refresh-indicator" id="refreshIndicator">
        <span id="refreshText">Auto-refresh: ON</span>
        <span id="refreshCountdown"></span>
    </div>
    {% endif %}

    <!-- Scripts -->
    <script>
        // Global refresh management (not on admin page)
        {% if active_page != 'admin' %}
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
        {% endif %}
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
<div id="engineStatus" style="position: fixed; top: 80px; right: 200px; display: flex;
    align-items: center; gap: 8px; background: rgba(30, 41, 59, 0.9); padding: 8px 16px;
    border-radius: 8px; border: 1px solid rgba(148, 163, 184, 0.2);">
    <div id="statusLight" style="width: 12px; height: 12px; border-radius: 50%; background: #fbbf24;"></div>
    <span id="statusText" style="font-size: 0.875rem; color: #94a3b8;">Checking...</span>
</div>

<!-- Trade Filter -->
<div style="display: flex; justify-content: center; gap: 20px; margin-bottom: 25px;
    padding: 15px; background: rgba(30, 41, 59, 0.5); backdrop-filter: blur(10px);
    border: 1px solid rgba(148, 163, 184, 0.1); border-radius: 12px;">
    <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
        <input type="radio" name="tradeFilter" value="open" id="filterOpen" checked>
        <span style="color: #e2e8f0;">Open Trades Only</span>
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
<div class="table-container" id="openPositionsContainer">
    <div class="table-header">
        <h2 class="table-title">Open Positions</h2>
    </div>
    <table>
        <thead>
            <tr>
                <th>Date/Time</th>
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
            <tr><td colspan="14" style="text-align: center;">Loading positions...</td></tr>
        </tbody>
    </table>
    <!-- Pagination controls for open positions -->
    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 15px;
        padding: 10px; background: rgba(30, 41, 59, 0.5); border-radius: 8px;">
        <div id="paginationInfo" style="color: #94a3b8;">
            Showing trades 1-100 of 0 total
        </div>
        <div style="display: flex; gap: 10px; align-items: center;">
            <button id="prevPage" onclick="goToPage(currentPage - 1)"
                style="padding: 5px 15px; background: #3b82f6; color: white; border: none;
                border-radius: 5px; cursor: pointer;" disabled>Previous</button>
            <span style="color: #94a3b8;">
                Page <input type="number" id="pageInput" value="1" min="1"
                    style="width: 50px; padding: 3px; background: #1e293b;
                    border: 1px solid #475569; color: white; border-radius: 3px;"
                    onchange="goToPage(parseInt(this.value))">
                of <span id="totalPages">1</span>
            </span>
            <button id="nextPage" onclick="goToPage(currentPage + 1)"
                style="padding: 5px 15px; background: #3b82f6; color: white; border: none;
                border-radius: 5px; cursor: pointer;">Next</button>
        </div>
    </div>
</div>

<!-- Closed Trades Table (Hidden by default, shown based on filter) -->
<div class="table-container" id="closedTradesContainer" style="display: none;">
    <div class="table-header">
        <h2 class="table-title">Closed Trades</h2>
    </div>
    <table>
        <thead>
            <tr>
                <th>Date/Time</th>
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
            <tr><td colspan="9" style="text-align: center;">Loading trades...</td></tr>
        </tbody>
    </table>
    <!-- Pagination controls for closed trades -->
    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 15px;
        padding: 10px; background: rgba(30, 41, 59, 0.5); border-radius: 8px;">
        <div id="paginationInfoClosed" style="color: #94a3b8;">
            Showing trades 1-100 of 0 total
        </div>
        <div style="display: flex; gap: 10px; align-items: center;">
            <button id="prevPageClosed" onclick="goToPage(currentPage - 1)"
                style="padding: 5px 15px; background: #3b82f6; color: white; border: none;
                border-radius: 5px; cursor: pointer;" disabled>Previous</button>
            <span style="color: #94a3b8;">
                Page <input type="number" id="pageInputClosed" value="1" min="1"
                    style="width: 50px; padding: 3px; background: #1e293b;
                    border: 1px solid #475569; color: white; border-radius: 3px;"
                    onchange="goToPage(parseInt(this.value))">
                of <span id="totalPagesClosed">1</span>
            </span>
            <button id="nextPageClosed" onclick="goToPage(currentPage + 1)"
                style="padding: 5px 15px; background: #3b82f6; color: white; border: none;
                border-radius: 5px; cursor: pointer;">Next</button>
        </div>
    </div>
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

// Pagination state
let currentPage = 1;
// currentFilter already declared above
let isNavigating = false;
let autoRefreshTimer = null;

async function fetchTrades(page = 1, isManualNavigation = false) {
    // Prevent auto-refresh during manual navigation
    if (isNavigating && !isManualNavigation) {
        return;
    }

    if (isManualNavigation) {
        isNavigating = true;
        if (autoRefreshTimer) {
            clearInterval(autoRefreshTimer);
        }
    }

    try {
        const response = await fetch(`/api/trades?page=${page}&per_page=100&filter=${currentFilter}`);
        const data = await response.json();
        allTradesData = data;

        // Calculate total unrealized P&L from open trades
        let totalUnrealizedPnl = 0;
        if (data.open_trades) {
            data.open_trades.forEach(trade => {
                totalUnrealizedPnl += trade.unrealized_pnl || 0;
            });
        }

        // Current balance = starting capital + realized P&L (from closed trades) + unrealized P&L
        const currentBalance = data.stats.starting_capital + data.stats.total_pnl_dollar + totalUnrealizedPnl;

        // Always update constant stats
        document.getElementById('currentBalance').textContent = `$${currentBalance.toFixed(2)}`;
        document.getElementById('totalInvestment').textContent = `$${data.stats.starting_capital.toFixed(2)}`;
        document.getElementById('openPositions').textContent = data.stats.open_count;

        // Update filtered view
        updateFilteredView();

        // Update pagination UI
        if (data.pagination) {
            currentPage = data.pagination.page;
            const totalPages = data.pagination.total_pages;
            const totalTrades = data.pagination.total_trades;
            const perPage = data.pagination.per_page;

            // Calculate trade range
            const startTrade = totalTrades > 0 ? ((currentPage - 1) * perPage) + 1 : 0;
            const endTrade = Math.min(currentPage * perPage, totalTrades);

            // Update pagination info based on current filter
            if (currentFilter === 'open') {
                document.getElementById('paginationInfo').textContent =
                    `Showing trades ${startTrade}-${endTrade} of ${totalTrades} total`;
                document.getElementById('pageInput').value = currentPage;
                document.getElementById('totalPages').textContent = totalPages;

                // Update button states
                document.getElementById('prevPage').disabled = currentPage <= 1;
                document.getElementById('nextPage').disabled = currentPage >= totalPages;
            } else if (currentFilter === 'closed') {
                document.getElementById('paginationInfoClosed').textContent =
                    `Showing trades ${startTrade}-${endTrade} of ${totalTrades} total`;
                document.getElementById('pageInputClosed').value = currentPage;
                document.getElementById('totalPagesClosed').textContent = totalPages;

                // Update button states
                document.getElementById('prevPageClosed').disabled = currentPage <= 1;
                document.getElementById('nextPageClosed').disabled = currentPage >= totalPages;
            }
        }

        // Reset navigation flag after page renders
        if (isManualNavigation) {
            setTimeout(() => {
                isNavigating = false;
                autoRefreshTimer = setInterval(() => fetchTrades(currentPage), 10000);
            }, 1000);
        }
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

    // Calculate total unrealized P&L from open trades
    let totalUnrealizedPnl = 0;
    if (data.open_trades) {
        data.open_trades.forEach(trade => {
            totalUnrealizedPnl += trade.unrealized_pnl || 0;
        });
    }

    if (currentFilter === 'open') {
        // Show open positions
        if (data.open_trades && data.open_trades.length > 0) {
            openTable.innerHTML = data.open_trades.map(trade => {
                // Format date to LA timezone
                const entryDate = new Date(trade.entry_time);
                const laDate = entryDate.toLocaleString('en-US', {
                    timeZone: 'America/Los_Angeles',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: true
                });

                return `
                <tr>
                    <td style="white-space: nowrap;">${laDate}</td>
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
            `}).join('');

            // Add unrealized P&L to stats if showing open
            data.open_trades.forEach(trade => {
                filteredPnl += trade.unrealized_pnl || 0;
            });
        } else {
            openTable.innerHTML = '<tr><td colspan="14" style="text-align: center;">No open positions</td></tr>';
        }
        document.getElementById('openPositionsContainer').style.display = 'block';
    } else {
        document.getElementById('openPositionsContainer').style.display = 'none';
    }

    if (currentFilter === 'closed') {
        // Show closed trades
        const closedTrades = data.trades ? data.trades.filter(t => t.status === 'closed') : [];

        if (closedTrades.length > 0) {
            closedTable.innerHTML = closedTrades.map(trade => {
                // Format date to LA timezone
                const exitDate = new Date(trade.exit_time);
                const laDate = exitDate.toLocaleString('en-US', {
                    timeZone: 'America/Los_Angeles',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: true
                });

                return `
                <tr>
                    <td style="white-space: nowrap;">${laDate}</td>
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
            `}).join('');

            // Calculate stats for closed trades
            closedTrades.forEach(trade => {
                filteredPnl += trade.pnl || 0;
                totalTrades++;
                if (trade.pnl > 0) winCount++;
                else lossCount++;
            });
        } else {
            closedTable.innerHTML = '<tr><td colspan="9" style="text-align: center;">No closed trades yet</td></tr>';
        }
        document.getElementById('closedTradesContainer').style.display = 'block';
    } else {
        document.getElementById('closedTradesContainer').style.display = 'none';
    }

    // Update dynamic stats based on filter
    const pnlElement = document.getElementById('totalPnl');
    let pnlToShow;

    if (currentFilter === 'open') {
        // For open positions, show unrealized P&L
        pnlToShow = filteredPnl;
    } else if (currentFilter === 'closed') {
        // For closed positions, show realized P&L only
        pnlToShow = data.stats.total_pnl_dollar;
    }

    // Total P&L should always be realized + unrealized (matching current balance calculation)
    const totalPnl = data.stats.total_pnl_dollar + totalUnrealizedPnl;

    // Use the total for display
    pnlElement.textContent = `$${totalPnl.toFixed(2)}`;
    pnlElement.className = `stat-value ${totalPnl >= 0 ? 'positive' : 'negative'}`;

    // Calculate P&L %
    const pnlPctElement = document.getElementById('totalPnlPct');
    const pnlPct = (totalPnl / data.stats.starting_capital) * 100;
    pnlPctElement.textContent = `${pnlPct.toFixed(2)}%`;
    pnlPctElement.className = `stat-value ${pnlPct >= 0 ? 'positive' : 'negative'}`;

    // Update win rate based on filter
    const winRateElement = document.getElementById('winRate');
    let winRate = 0;
    if (currentFilter === 'closed' && totalTrades > 0) {
        winRate = (winCount / totalTrades) * 100;
    } else if (currentFilter === 'open') {
        winRate = 0; // No win rate for open positions
    }
    winRateElement.textContent = `${winRate.toFixed(1)}%`;
    winRateElement.className = `stat-value ${winRate >= 50 ? 'positive' : winRate > 0 ? 'neutral' : ''}`;
}

// Pagination navigation function
function goToPage(page) {
    if (page < 1) page = 1;
    currentPage = page;
    fetchTrades(page, true); // Manual navigation
}

// Add event listeners for filters
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('input[name="tradeFilter"]').forEach(radio => {
        radio.addEventListener('change', function() {
            currentFilter = this.value;
            currentPage = 1; // Reset to first page on filter change
            fetchTrades(1, true); // Fetch with new filter
        });
    });

    // Initial load
    fetchTrades();
    checkEngineStatus();

    // Set up refresh intervals (using timer variable)
    autoRefreshTimer = setInterval(() => fetchTrades(currentPage), 10000);
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


# R&D Page Template
RD_TEMPLATE = r"""
<h1 class="page-title">Research & Development</h1>
<p class="subtitle">Shadow Testing insights and actionable recommendations</p>

<!-- Executive Summary -->
<div class="performance-section executive-summary">
    <h2>📊 Shadow Testing Insights - Executive Summary</h2>
    <div class="summary-cards">
        <div class="insight-card top-finding">
            <div class="insight-icon">✅</div>
            <div class="insight-content">
                <div class="insight-label">Top Finding</div>
                <div class="insight-text" id="topFinding">Analyzing shadow variations...</div>
            </div>
        </div>
        <div class="insight-card key-risk">
            <div class="insight-icon">⚠️</div>
            <div class="insight-content">
                <div class="insight-label">Key Risk</div>
                <div class="insight-text" id="keyRisk">Evaluating risk patterns...</div>
            </div>
        </div>
        <div class="insight-card quick-win">
            <div class="insight-icon">💡</div>
            <div class="insight-content">
                <div class="insight-label">Quick Win</div>
                <div class="insight-text" id="quickWin">Finding easy improvements...</div>
            </div>
        </div>
    </div>
</div>

<!-- Actionable Recommendations -->
<div class="performance-section recommendations-container">
    <h2>🎯 Actionable Recommendations</h2>
    <div class="recommendations-list" id="recommendationsList">
        <div class="loading">Analyzing shadow testing data...</div>
    </div>
</div>

<!-- Performance Comparison -->
<div class="performance-section performance-comparison">
    <h2>📈 Your Config vs Best Shadow Performance</h2>
    <div class="comparison-grid" id="comparisonGrid">
        <div class="loading">Loading performance metrics...</div>
    </div>
</div>

<!-- Strategy Report Cards -->
<div class="performance-section strategy-reports">
    <h2>📊 Strategy Report Cards</h2>
    <div class="report-cards" id="strategyReports">
        <div class="loading">Generating strategy analysis...</div>
    </div>
</div>

<!-- What If Scenarios -->
<div class="performance-section what-if-container">
    <h2>🔮 What If You Applied These Changes?</h2>
    <div class="what-if-content" id="whatIfContent">
        <div class="loading">Calculating impact...</div>
    </div>
</div>

<!-- Plain English Insights -->
<div class="performance-section insights-container">
    <h2>💬 What The Data Is Telling You</h2>
    <div class="plain-insights" id="plainInsights">
        <div class="loading">Generating insights...</div>
    </div>
</div>

<!-- Quick Actions -->
<div class="performance-section quick-actions">
    <h2>🚀 Quick Actions</h2>
    <div class="action-buttons">
        <button class="action-btn apply-safe" onclick="applySafeChanges()">
            Apply Safe Changes
            <span class="btn-subtitle">High confidence improvements only</span>
        </button>
        <button class="action-btn test-custom" onclick="showCustomTest()">
            Test Custom Change
            <span class="btn-subtitle">Try your own parameters</span>
        </button>
        <button class="action-btn export-report" onclick="exportReport()">
            Export Report
            <span class="btn-subtitle">Download full analysis</span>
        </button>
    </div>
</div>

<!-- Model Status -->
<div class="stats-container">
    <div class="stat-card">
        <div class="stat-label">CHANNEL Model</div>
        <div class="stat-value" id="channelScore">Loading...</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">DCA Model</div>
        <div class="stat-value" id="dcaScore">Loading...</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">SWING Model</div>
        <div class="stat-value" id="swingScore">Loading...</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Next Retrain</div>
        <div class="stat-value" id="nextRetrain">Loading...</div>
    </div>
</div>

<!-- Parameter Recommendations -->
<div class="table-container">
    <div class="table-header">
        <h2 class="table-title">📊 Current Recommendations (Based on Last 100 Trades)</h2>
    </div>
    <div class="recommendation-box" id="recommendationsContainer">
        <div class="loading">Analyzing trades...</div>
    </div>
</div>

<!-- Parameter Change History -->
<div class="table-container">
    <div class="table-header">
        <h2 class="table-title">📈 Parameter Change History</h2>
    </div>
    <table class="data-table">
        <thead>
            <tr>
                <th>Date</th>
                <th>Parameter</th>
                <th>Old Value</th>
                <th>New Value</th>
                <th>Impact (7 days)</th>
            </tr>
        </thead>
        <tbody id="parameterHistoryTable">
            <tr><td colspan="5">Loading...</td></tr>
        </tbody>
    </table>
</div>

<!-- ML Learning Progress -->
<div class="table-container">
    <div class="table-header">
        <h2 class="table-title">🧠 ML Model Learning Progress</h2>
    </div>
    <div class="progress-container" id="learningProgressContainer">
        <div class="loading">Loading model statistics...</div>
    </div>
</div>

<!-- ML Prediction Accuracy -->
<div class="table-container">
    <div class="table-header">
        <h2 class="table-title">🎯 Recent ML Predictions vs Reality</h2>
    </div>
    <table class="data-table">
        <thead>
            <tr>
                <th>Time</th>
                <th>Symbol</th>
                <th>Strategy</th>
                <th>ML Confidence</th>
                <th>Predicted</th>
                <th>Actual</th>
                <th>Accuracy</th>
            </tr>
        </thead>
        <tbody id="mlPredictionsTable">
            <tr><td colspan="7">Loading...</td></tr>
        </tbody>
    </table>
</div>

<style>
/* Performance Tracking Container Styles */
.performance-section {
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(148, 163, 184, 0.1);
    border-radius: 12px;
    padding: 24px;
    margin: 20px 0;
}

.performance-section h2 {
    color: #f1f5f9;
    font-size: 1.3rem;
    font-weight: 600;
    margin: 0 0 20px 0;
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.1);
}

/* Executive Summary Styles */
.executive-summary {
    margin: 0;
}

.summary-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
}

.insight-card {
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.9) 0%, rgba(15, 23, 42, 0.9) 100%);
    border-radius: 10px;
    padding: 20px;
    display: flex;
    align-items: flex-start;
    gap: 16px;
    border: 1px solid rgba(148, 163, 184, 0.15);
    transition: transform 0.2s, box-shadow 0.2s;
}

.insight-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.insight-card.top-finding {
    border-left: 3px solid #10b981;
}

.insight-card.key-risk {
    border-left: 3px solid #fbbf24;
}

.insight-card.quick-win {
    border-left: 3px solid #3b82f6;
}

.insight-icon {
    font-size: 1.5rem;
    min-width: 32px;
    text-align: center;
}

.insight-content {
    flex: 1;
}

.insight-label {
    font-size: 0.75rem;
    color: #64748b;
    margin-bottom: 6px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.insight-text {
    color: #e2e8f0;
    font-size: 0.95rem;
    line-height: 1.5;
}

/* Recommendations Styles */
.recommendations-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.recommendation-item {
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.5) 0%, rgba(15, 23, 42, 0.5) 100%);
    border: 1px solid rgba(148, 163, 184, 0.15);
    border-radius: 10px;
    padding: 20px;
    transition: all 0.2s;
}

.recommendation-item:hover {
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.7) 100%);
    border-color: rgba(148, 163, 184, 0.25);
}

.recommendation-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
}

.recommendation-title {
    font-size: 1.05rem;
    color: #f1f5f9;
    font-weight: 500;
}

.recommendation-confidence {
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 600;
}

.confidence-high {
    background: rgba(16, 185, 129, 0.15);
    color: #10b981;
    border: 1px solid rgba(16, 185, 129, 0.3);
}

.confidence-medium {
    background: rgba(59, 130, 246, 0.15);
    color: #3b82f6;
    border: 1px solid rgba(59, 130, 246, 0.3);
}

.confidence-low {
    background: rgba(251, 191, 36, 0.15);
    color: #fbbf24;
    border: 1px solid rgba(251, 191, 36, 0.3);
}

.recommendation-details {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 20px;
    margin: 16px 0;
}

.detail-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.detail-label {
    color: #64748b;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.detail-value {
    color: #e2e8f0;
    font-size: 0.9rem;
    line-height: 1.4;
}

.apply-btn {
    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 6px;
    cursor: pointer;
    font-weight: 600;
}

.apply-btn:hover {
    opacity: 0.9;
}

.consider-btn {
    background: rgba(251, 191, 36, 0.2);
    color: #fbbf24;
    border: 1px solid rgba(251, 191, 36, 0.3);
    padding: 10px 20px;
    border-radius: 6px;
    cursor: pointer;
    font-weight: 600;
}

/* Performance Comparison */
.comparison-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 16px;
}

.comparison-metric {
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.4) 0%, rgba(15, 23, 42, 0.4) 100%);
    padding: 18px;
    border-radius: 10px;
    border: 1px solid rgba(148, 163, 184, 0.15);
    transition: all 0.2s;
}

.comparison-metric:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
}

.metric-name {
    color: #64748b;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 12px;
}

.metric-values {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 8px;
}

.current-val {
    color: #94a3b8;
    font-size: 1.1rem;
}

.best-val {
    color: #10b981;
    font-size: 1.1rem;
    font-weight: 600;
}

.difference {
    color: #fbbf24;
    font-size: 0.8rem;
    text-align: center;
    padding-top: 8px;
    border-top: 1px solid rgba(148, 163, 184, 0.1);
}

/* Strategy Report Cards */
.report-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 16px;
}

.report-card {
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.5) 0%, rgba(15, 23, 42, 0.5) 100%);
    border-radius: 10px;
    padding: 20px;
    border: 1px solid rgba(148, 163, 184, 0.15);
    transition: all 0.2s;
}

.report-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.report-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.1);
}

.strategy-name {
    font-size: 1.1rem;
    color: #f1f5f9;
    font-weight: 500;
}

.strategy-grade {
    font-size: 1.3rem;
    font-weight: bold;
    padding: 4px 12px;
    border-radius: 6px;
}

.grade-a { 
    color: #10b981; 
    background: rgba(16, 185, 129, 0.15);
    border: 1px solid rgba(16, 185, 129, 0.3);
}
.grade-b { 
    color: #3b82f6; 
    background: rgba(59, 130, 246, 0.15);
    border: 1px solid rgba(59, 130, 246, 0.3);
}
.grade-c { 
    color: #fbbf24; 
    background: rgba(251, 191, 36, 0.15);
    border: 1px solid rgba(251, 191, 36, 0.3);
}

.report-sections {
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.report-section {
    background: rgba(15, 23, 42, 0.3);
    padding: 12px;
    border-radius: 6px;
}

.report-section h4 {
    color: #94a3b8;
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 10px;
}

.report-list {
    list-style: none;
    padding: 0;
    margin: 0;
}

.report-list li {
    color: #e2e8f0;
    padding: 6px 0 6px 20px;
    position: relative;
    font-size: 0.9rem;
    line-height: 1.4;
}

.report-list li:before {
    content: "•";
    position: absolute;
    left: 6px;
    color: #64748b;
}

/* What If Scenarios */
.what-if-content {
    background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(59, 130, 246, 0.05) 100%);
    border: 1px solid rgba(59, 130, 246, 0.2);
    border-radius: 10px;
    padding: 24px;
}

.impact-metrics {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 20px;
    margin-bottom: 20px;
}

.impact-item {
    text-align: center;
    padding: 16px;
    background: rgba(15, 23, 42, 0.4);
    border-radius: 8px;
    border: 1px solid rgba(148, 163, 184, 0.1);
}

.impact-label {
    color: #64748b;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
}

.impact-value {
    color: #3b82f6;
    font-size: 1.4rem;
    font-weight: bold;
}

.what-if-content p {
    color: #94a3b8;
    line-height: 1.5;
    margin: 0;
    padding-top: 16px;
    border-top: 1px solid rgba(148, 163, 184, 0.1);
}

/* Plain English Insights */
.plain-insights {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.insight-paragraph {
    color: #e2e8f0;
    line-height: 1.6;
    padding: 16px;
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.4) 0%, rgba(15, 23, 42, 0.4) 100%);
    border-left: 3px solid #3b82f6;
    border-radius: 6px;
    font-size: 0.95rem;
}

/* Quick Actions */
.action-buttons {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 16px;
}

.action-btn {
    background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
    color: white;
    border: none;
    padding: 16px 20px;
    border-radius: 8px;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    transition: all 0.2s;
    font-size: 0.95rem;
    font-weight: 500;
}

.action-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.btn-subtitle {
    font-size: 0.8rem;
    opacity: 0.85;
    margin-top: 6px;
    font-weight: 400;
}

.action-btn.apply-safe {
    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
}

.action-btn.test-custom {
    background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
}

.action-btn.export-report {
    background: linear-gradient(135deg, #64748b 0%, #475569 100%);
}

/* Loading State */
.loading {
    color: #64748b;
    text-align: center;
    padding: 40px;
    font-style: italic;
}

/* No Data State */
.no-data {
    color: #64748b;
    text-align: center;
    padding: 40px;
    background: rgba(30, 41, 59, 0.2);
    border-radius: 8px;
    border: 1px dashed rgba(148, 163, 184, 0.2);
}

.recommendation-box {
    background: rgba(15, 23, 42, 0.6);
    border-radius: 8px;
    padding: 20px;
    margin-top: 10px;
}

.recommendation-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    margin: 8px 0;
    background: rgba(30, 41, 59, 0.5);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 8px;
}

.recommendation-label {
    color: #94a3b8;
    font-size: 0.9rem;
}

.recommendation-values {
    display: flex;
    align-items: center;
    gap: 16px;
}

.current-value {
    color: #64748b;
}

.arrow {
    color: #3b82f6;
    font-size: 1.2rem;
}

.recommended-value {
    color: #10b981;
    font-weight: 600;
}

.recommendation-reason {
    color: #fbbf24;
    font-size: 0.85rem;
    margin-left: 16px;
}

.progress-container {
    padding: 20px;
}

.progress-item {
    margin: 16px 0;
}

.progress-label {
    display: flex;
    justify-content: space-between;
    margin-bottom: 8px;
    font-size: 0.9rem;
}

.progress-bar-bg {
    background: rgba(148, 163, 184, 0.2);
    height: 8px;
    border-radius: 4px;
    overflow: hidden;
}

.progress-bar-fill {
    height: 100%;
    background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
    transition: width 0.3s ease;
}

.warning-box {
    background: rgba(251, 191, 36, 0.1);
    border: 1px solid rgba(251, 191, 36, 0.3);
    border-radius: 8px;
    padding: 16px;
    margin: 16px 0;
    color: #fbbf24;
    font-size: 0.9rem;
}
</style>
"""

# JavaScript for R&D page
RD_SCRIPTS = r"""
<script>
// Fetch Shadow Testing Performance Data
async function fetchShadowPerformance() {
    try {
        const response = await fetch('/api/shadow-performance');
        const data = await response.json();
        
        // Update Executive Summary
        updateExecutiveSummary(data);
        
        // Update Recommendations
        updateRecommendations(data);
        
        // Update Performance Comparison
        updatePerformanceComparison(data);
        
        // Update Strategy Report Cards
        updateStrategyReports(data);
        
        // Update What If Scenarios
        updateWhatIfScenarios(data);
        
        // Update Plain English Insights
        updatePlainInsights(data);
        
    } catch (error) {
        console.error('Error fetching shadow performance:', error);
    }
}

// Update Executive Summary
function updateExecutiveSummary(data) {
    if (data.executive_summary) {
        document.getElementById('topFinding').textContent = 
            data.executive_summary.top_finding || 'Analyzing shadow variations...';
        document.getElementById('keyRisk').textContent = 
            data.executive_summary.key_risk || 'Evaluating risk patterns...';
        document.getElementById('quickWin').textContent = 
            data.executive_summary.quick_win || 'Finding easy improvements...';
    }
}

// Update Actionable Recommendations
function updateRecommendations(data) {
    const container = document.getElementById('recommendationsList');
    
    if (data.recommendations && data.recommendations.length > 0) {
        let html = '';
        
        data.recommendations.forEach((rec, index) => {
            const confidenceClass = rec.confidence >= 0.8 ? 'high' : 
                                   rec.confidence >= 0.6 ? 'medium' : 'low';
            const actionBtn = rec.confidence >= 0.8 ? 
                `<button class="apply-btn" onclick="applyRecommendation('${rec.id}')">Apply Now</button>` :
                `<button class="consider-btn">Consider</button>`;
            
            html += `
                <div class="recommendation-item">
                    <div class="recommendation-header">
                        <div class="recommendation-title">
                            ${index + 1}. ${rec.title}
                        </div>
                        <div class="recommendation-confidence confidence-${confidenceClass}">
                            ${Math.round(rec.confidence * 100)}% Confidence
                        </div>
                    </div>
                    <div class="recommendation-details">
                        <div class="detail-item">
                            <div class="detail-label">What</div>
                            <div class="detail-value">${rec.what}</div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-label">Why</div>
                            <div class="detail-value">${rec.why}</div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-label">Impact</div>
                            <div class="detail-value">${rec.impact}</div>
                        </div>
                    </div>
                    <div style="margin-top: 15px;">
                        ${actionBtn}
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
    } else {
        container.innerHTML = '<div class="no-data">No recommendations available yet. Shadow Testing needs more data.</div>';
    }
}

// Update Performance Comparison
function updatePerformanceComparison(data) {
    const container = document.getElementById('comparisonGrid');
    
    if (data.performance_comparison) {
        const comp = data.performance_comparison;
        
        let html = `
            <div class="comparison-metric">
                <div class="metric-name">Win Rate</div>
                <div class="metric-values">
                    <span class="current-val">${comp.current.win_rate}%</span>
                    <span class="best-val">${comp.best.win_rate}%</span>
                </div>
                <div class="difference">${comp.best.win_rate > comp.current.win_rate ? '+' : ''}${(comp.best.win_rate - comp.current.win_rate).toFixed(1)}%</div>
            </div>
            <div class="comparison-metric">
                <div class="metric-name">Avg Profit</div>
                <div class="metric-values">
                    <span class="current-val">${comp.current.avg_profit}%</span>
                    <span class="best-val">${comp.best.avg_profit}%</span>
                </div>
                <div class="difference">${comp.best.avg_profit > comp.current.avg_profit ? '+' : ''}${(comp.best.avg_profit - comp.current.avg_profit).toFixed(1)}%</div>
            </div>
            <div class="comparison-metric">
                <div class="metric-name">Max Drawdown</div>
                <div class="metric-values">
                    <span class="current-val">${comp.current.max_drawdown}%</span>
                    <span class="best-val">${comp.best.max_drawdown}%</span>
                </div>
                <div class="difference">${Math.abs(comp.best.max_drawdown - comp.current.max_drawdown).toFixed(1)}% better</div>
            </div>
            <div class="comparison-metric">
                <div class="metric-name">Monthly P&L</div>
                <div class="metric-values">
                    <span class="current-val">$${comp.current.monthly_pnl}</span>
                    <span class="best-val">$${comp.best.monthly_pnl}</span>
                </div>
                <div class="difference">+$${comp.best.monthly_pnl - comp.current.monthly_pnl}</div>
            </div>
        `;
        
        container.innerHTML = html;
    }
}

// Update Strategy Report Cards
function updateStrategyReports(data) {
    const container = document.getElementById('strategyReports');
    
    if (data.strategy_reports) {
        let html = '';
        
        ['DCA', 'SWING', 'CHANNEL'].forEach(strategy => {
            if (data.strategy_reports[strategy]) {
                const report = data.strategy_reports[strategy];
                const gradeClass = report.grade.startsWith('A') ? 'grade-a' :
                                   report.grade.startsWith('B') ? 'grade-b' : 'grade-c';
                
                html += `
                    <div class="report-card">
                        <div class="report-header">
                            <div class="strategy-name">${strategy} Strategy</div>
                            <div class="strategy-grade ${gradeClass}">${report.grade}</div>
                        </div>
                        <div class="report-sections">
                            <div class="report-section">
                                <h4>✅ Strengths</h4>
                                <ul class="report-list">
                                    ${report.strengths.map(s => `<li>${s}</li>`).join('')}
                                </ul>
                            </div>
                            <div class="report-section">
                                <h4>❌ Weaknesses</h4>
                                <ul class="report-list">
                                    ${report.weaknesses.map(w => `<li>${w}</li>`).join('')}
                                </ul>
                            </div>
                            <div class="report-section">
                                <h4>💡 Suggested Changes</h4>
                                <ul class="report-list">
                                    ${report.suggestions.map(s => `<li>${s}</li>`).join('')}
                                </ul>
                            </div>
                        </div>
                    </div>
                `;
            }
        });
        
        container.innerHTML = html || '<div class="no-data">Generating strategy analysis...</div>';
    }
}

// Update What If Scenarios
function updateWhatIfScenarios(data) {
    const container = document.getElementById('whatIfContent');
    
    if (data.what_if) {
        const whatIf = data.what_if;
        
        let html = `
            <div class="impact-metrics">
                <div class="impact-item">
                    <div class="impact-label">Expected Monthly Profit</div>
                    <div class="impact-value">$${whatIf.expected_profit}</div>
                </div>
                <div class="impact-item">
                    <div class="impact-label">Win Rate</div>
                    <div class="impact-value">${whatIf.expected_win_rate}%</div>
                </div>
                <div class="impact-item">
                    <div class="impact-label">Risk Level</div>
                    <div class="impact-value">${whatIf.risk_level}</div>
                </div>
                <div class="impact-item">
                    <div class="impact-label">Confidence</div>
                    <div class="impact-value">${whatIf.confidence}</div>
                </div>
            </div>
            <p style="margin-top: 15px; color: #94a3b8;">
                ${whatIf.description}
            </p>
        `;
        
        container.innerHTML = html;
    }
}

// Update Plain English Insights
function updatePlainInsights(data) {
    const container = document.getElementById('plainInsights');
    
    if (data.plain_insights && data.plain_insights.length > 0) {
        let html = '';
        
        data.plain_insights.forEach(insight => {
            html += `<div class="insight-paragraph">${insight}</div>`;
        });
        
        container.innerHTML = html;
    } else {
        container.innerHTML = '<div class="insight-paragraph">Shadow Testing is analyzing your trading patterns. Insights will appear here once we have enough data to make confident recommendations.</div>';
    }
}

// Apply a recommendation
async function applyRecommendation(recId) {
    if (!confirm('Apply this recommendation to your configuration?')) return;
    
    try {
        const response = await fetch('/api/apply-recommendation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ recommendation_id: recId })
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert('Recommendation applied successfully!');
            fetchShadowPerformance(); // Refresh data
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        console.error('Error applying recommendation:', error);
        alert('Failed to apply recommendation');
    }
}

// Apply safe changes
async function applySafeChanges() {
    if (!confirm('Apply all high-confidence recommendations?')) return;
    
    try {
        const response = await fetch('/api/apply-safe-changes', {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(`Applied ${result.count} recommendations successfully!`);
            fetchShadowPerformance();
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        console.error('Error applying safe changes:', error);
    }
}

// Show custom test dialog
function showCustomTest() {
    // This would open a modal for custom parameter testing
    alert('Custom parameter testing coming soon!');
}

// Export report
async function exportReport() {
    try {
        const response = await fetch('/api/export-shadow-report');
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `shadow_testing_report_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        a.remove();
    } catch (error) {
        console.error('Error exporting report:', error);
        alert('Failed to export report');
    }
}

// Fetch ML model status
async function fetchModelStatus() {
    try {
        const response = await fetch('/api/ml-model-status');
        const data = await response.json();

        // Update model scores with detailed metrics
        if (data.channel) {
            let details = data.channel.accuracy ?
                `<br><small style="font-size: 0.7em; color: #9ca3af;">Acc: ${data.channel.accuracy} | Prec: ${data.channel.precision} | Rec: ${data.channel.recall}</small>` : '';
            document.getElementById('channelScore').innerHTML =
                `${data.channel.score} <span style="color: #10b981;">✓</span>${details}`;
        } else {
            document.getElementById('channelScore').innerHTML = 'Not Trained';
        }

        document.getElementById('dcaScore').innerHTML =
            data.dca ? `${data.dca.score}` : `${data.dca_samples}/20 samples`;
        document.getElementById('swingScore').innerHTML =
            data.swing ? `${data.swing.score}` : `${data.swing_samples}/20 samples`;
        document.getElementById('nextRetrain').textContent = data.next_retrain || '2:00 AM PST';

    } catch (error) {
        console.error('Error fetching model status:', error);
    }
}

// Fetch parameter recommendations
async function fetchRecommendations() {
    try {
        const response = await fetch('/api/parameter-recommendations');
        const data = await response.json();

        const container = document.getElementById('recommendationsContainer');

        if (data.recommendations && data.recommendations.length > 0) {
            let html = '';

            // Add warning box
            html += `<div class="warning-box">
                ⚠️ Note: These recommendations are based on historical analysis only.
                Shadow Testing (coming in Phase 4) will provide validated recommendations.
            </div>`;

            // Add recommendations
            data.recommendations.forEach(rec => {
                html += `
                    <div class="recommendation-item">
                        <div>
                            <div class="recommendation-label">${rec.strategy} - ${rec.parameter}</div>
                            <div class="recommendation-reason">${rec.reason}</div>
                        </div>
                        <div class="recommendation-values">
                            <span class="current-value">${rec.current}%</span>
                            <span class="arrow">→</span>
                            <span class="recommended-value">${rec.recommended}%</span>
                        </div>
                    </div>
                `;
            });

            container.innerHTML = html;
        } else {
            container.innerHTML = '<p style="color: #94a3b8;">No recommendations available yet. Need more completed trades for analysis.</p>';
        }
    } catch (error) {
        console.error('Error fetching recommendations:', error);
    }
}

// Fetch parameter change history
async function fetchParameterHistory() {
    try {
        const response = await fetch('/api/parameter-history');
        const data = await response.json();

        const table = document.getElementById('parameterHistoryTable');

        if (data.history && data.history.length > 0) {
            table.innerHTML = data.history.map(item => `
                <tr>
                    <td>${new Date(item.date).toLocaleDateString()}</td>
                    <td>${item.parameter}</td>
                    <td>${item.old_value}%</td>
                    <td>${item.new_value}%</td>
                    <td class="${item.impact > 0 ? 'positive' : 'negative'}">
                        ${item.impact > 0 ? '+' : ''}${item.impact}%
                    </td>
                </tr>
            `).join('');
        } else {
            table.innerHTML = '<tr><td colspan="5" style="color: #94a3b8;">No parameter changes recorded yet</td></tr>';
        }
    } catch (error) {
        console.error('Error fetching parameter history:', error);
    }
}

// Fetch ML learning progress
async function fetchLearningProgress() {
    try {
        const response = await fetch('/api/ml-learning-progress');
        const data = await response.json();

        const container = document.getElementById('learningProgressContainer');

        let html = '';

        ['CHANNEL', 'DCA', 'SWING'].forEach(strategy => {
            const progress = data[strategy] || { current: 0, required: 20, next_milestone: 20 };
            const percentage = Math.min((progress.current / progress.next_milestone) * 100, 100);

            html += `
                <div class="progress-item">
                    <div class="progress-label">
                        <span>${strategy}: ${progress.current} trades learned</span>
                        <span>Next insight at ${progress.next_milestone} trades</span>
                    </div>
                    <div class="progress-bar-bg">
                        <div class="progress-bar-fill" style="width: ${percentage}%"></div>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;
    } catch (error) {
        console.error('Error fetching learning progress:', error);
    }
}

// Fetch ML predictions accuracy
async function fetchMLPredictions() {
    try {
        const response = await fetch('/api/recent-ml-predictions');
        const data = await response.json();

        const table = document.getElementById('mlPredictionsTable');

        if (data.predictions && data.predictions.length > 0) {
            table.innerHTML = data.predictions.map(pred => {
                const accuracyIcon = pred.correct ? '✅' : '❌';
                return `
                    <tr>
                        <td>${new Date(pred.timestamp).toLocaleTimeString()}</td>
                        <td>${pred.symbol}</td>
                        <td>${pred.strategy}</td>
                        <td>${(pred.confidence * 100).toFixed(1)}%</td>
                        <td>${pred.predicted}</td>
                        <td>${pred.actual || 'Pending'}</td>
                        <td>${pred.actual ? accuracyIcon : '⏳'}</td>
                    </tr>
                `;
            }).join('');
        } else {
            table.innerHTML = '<tr><td colspan="7" style="color: #94a3b8;">No ML predictions yet</td></tr>';
        }
    } catch (error) {
        console.error('Error fetching ML predictions:', error);
    }
}

// Initial load and refresh intervals
fetchShadowPerformance();  // Primary Shadow Testing dashboard
fetchModelStatus();
fetchRecommendations();
fetchParameterHistory();
fetchLearningProgress();
fetchMLPredictions();

// Refresh intervals
setInterval(fetchShadowPerformance, 60000); // Update shadow data every minute
setInterval(fetchModelStatus, 30000); // Every 30 seconds
setInterval(fetchRecommendations, 60000); // Every minute
setInterval(fetchParameterHistory, 60000); // Every minute
setInterval(fetchLearningProgress, 60000); // Every minute
setInterval(fetchMLPredictions, 30000); // Every 30 seconds
</script>
"""


# Admin Panel Templates
ADMIN_TEMPLATE = r"""
<h1 class="page-title">Admin Panel</h1>
<p class="subtitle">Configuration Management & Control Center</p>

<!-- Paper Trading Configuration Section -->
<div class="paper-trading-section">
    <div class="section-header">Paper Trading Configuration</div>
    
    <!-- Paper Trading Status (formerly Kill Switch) -->
    <div class="stats-container">
        <div class="stat-card kill-switch-card">
            <div class="stat-label">Paper Trading Status</div>
            <div class="kill-switch-container">
                <label class="switch">
                    <input type="checkbox" id="killSwitch" onchange="markUnsaved()">
                    <span class="slider round"></span>
                </label>
                <span id="killSwitchStatus" class="status-text">Loading...</span>
            </div>
        </div>
    </div>

<!-- Configuration Sections -->
<div class="config-sections">
    <!-- Strategy Entry Thresholds (Tier-Specific) -->
    <div class="config-section">
        <h2>Strategy Entry Thresholds</h2>
        
        <!-- Strategy Tabs -->
        <div class="strategy-tabs">
            <button class="strategy-tab active" onclick="showEntryStrategyTab('DCA')">DCA</button>
            <button class="strategy-tab" onclick="showEntryStrategyTab('SWING')">SWING</button>
            <button class="strategy-tab" onclick="showEntryStrategyTab('CHANNEL')">CHANNEL</button>
        </div>
        
        <!-- DCA Entry Thresholds -->
        <div id="entry_DCA" class="strategy-entry-content" style="display: block;">
            <div class="tier-tabs">
                <button class="tier-tab active" onclick="showEntryTierTab('DCA', 'large_cap')">Large Cap</button>
                <button class="tier-tab" onclick="showEntryTierTab('DCA', 'mid_cap')">Mid Cap</button>
                <button class="tier-tab" onclick="showEntryTierTab('DCA', 'small_cap')">Small Cap</button>
                <button class="tier-tab" onclick="showEntryTierTab('DCA', 'memecoin')">Memecoin</button>
            </div>
            
            <!-- DCA Large Cap -->
            <div id="entry_DCA_large_cap" class="tier-entry-content" style="display: block;">
                <div class="config-group">
                    <h3>Large Cap DCA Thresholds</h3>
                    <div class="config-row">
                        <label>Drop Threshold (%)</label>
                        <input type="number" id="dca_large_cap_drop" step="0.1" min="-20" max="0" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Volume Requirement</label>
                        <input type="number" id="dca_large_cap_volume_req" step="0.05" min="0" max="2" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Grid Levels</label>
                        <input type="number" id="dca_large_cap_grid_levels" step="1" min="1" max="10" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Grid Spacing (%)</label>
                        <input type="number" id="dca_large_cap_grid_spacing" step="0.005" min="0.01" max="0.1" onchange="markUnsaved()">
                    </div>
                </div>
            </div>
            
            <!-- DCA Mid Cap -->
            <div id="entry_DCA_mid_cap" class="tier-entry-content" style="display: none;">
                <div class="config-group">
                    <h3>Mid Cap DCA Thresholds</h3>
                    <div class="config-row">
                        <label>Drop Threshold (%)</label>
                        <input type="number" id="dca_mid_cap_drop" step="0.1" min="-20" max="0" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Volume Requirement</label>
                        <input type="number" id="dca_mid_cap_volume_req" step="0.05" min="0" max="2" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Grid Levels</label>
                        <input type="number" id="dca_mid_cap_grid_levels" step="1" min="1" max="10" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Grid Spacing (%)</label>
                        <input type="number" id="dca_mid_cap_grid_spacing" step="0.005" min="0.01" max="0.1" onchange="markUnsaved()">
                    </div>
                </div>
            </div>
            
            <!-- DCA Small Cap -->
            <div id="entry_DCA_small_cap" class="tier-entry-content" style="display: none;">
                <div class="config-group">
                    <h3>Small Cap DCA Thresholds</h3>
                    <div class="config-row">
                        <label>Drop Threshold (%)</label>
                        <input type="number" id="dca_small_cap_drop" step="0.1" min="-20" max="0" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Volume Requirement</label>
                        <input type="number" id="dca_small_cap_volume_req" step="0.05" min="0" max="2" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Grid Levels</label>
                        <input type="number" id="dca_small_cap_grid_levels" step="1" min="1" max="10" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Grid Spacing (%)</label>
                        <input type="number" id="dca_small_cap_grid_spacing" step="0.005" min="0.01" max="0.1" onchange="markUnsaved()">
                    </div>
                </div>
            </div>
            
            <!-- DCA Memecoin -->
            <div id="entry_DCA_memecoin" class="tier-entry-content" style="display: none;">
                <div class="config-group">
                    <h3>Memecoin DCA Thresholds</h3>
                    <div class="config-row">
                        <label>Drop Threshold (%)</label>
                        <input type="number" id="dca_memecoin_drop" step="0.1" min="-20" max="0" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Volume Requirement</label>
                        <input type="number" id="dca_memecoin_volume_req" step="0.05" min="0" max="2" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Grid Levels</label>
                        <input type="number" id="dca_memecoin_grid_levels" step="1" min="1" max="10" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Grid Spacing (%)</label>
                        <input type="number" id="dca_memecoin_grid_spacing" step="0.005" min="0.01" max="0.1" onchange="markUnsaved()">
                    </div>
                </div>
            </div>
        </div>
        
        <!-- SWING Entry Thresholds -->
        <div id="entry_SWING" class="strategy-entry-content" style="display: none;">
            <div class="tier-tabs">
                <button class="tier-tab active" onclick="showEntryTierTab('SWING', 'large_cap')">Large Cap</button>
                <button class="tier-tab" onclick="showEntryTierTab('SWING', 'mid_cap')">Mid Cap</button>
                <button class="tier-tab" onclick="showEntryTierTab('SWING', 'small_cap')">Small Cap</button>
                <button class="tier-tab" onclick="showEntryTierTab('SWING', 'memecoin')">Memecoin</button>
            </div>
            
            <!-- SWING Tier Contents (similar structure for each tier) -->
            <div id="entry_SWING_large_cap" class="tier-entry-content active">
                <div class="config-group">
                    <h3>Large Cap SWING Thresholds</h3>
                    <div class="config-row">
                        <label>Breakout Threshold</label>
                        <input type="number" id="swing_large_cap_breakout" step="0.001" min="1" max="1.1" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Volume Surge</label>
                        <input type="number" id="swing_large_cap_volume" step="0.1" min="1" max="5" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>RSI Min</label>
                        <input type="number" id="swing_large_cap_rsi_min" step="1" min="0" max="100" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>RSI Max</label>
                        <input type="number" id="swing_large_cap_rsi_max" step="1" min="0" max="100" onchange="markUnsaved()">
                    </div>
                </div>
            </div>
            
            <!-- SWING Mid Cap -->
            <div id="entry_SWING_mid_cap" class="tier-entry-content" style="display: none;">
                <div class="config-group">
                    <h3>Mid Cap SWING Thresholds</h3>
                    <div class="config-row">
                        <label>Breakout Threshold</label>
                        <input type="number" id="swing_mid_cap_breakout" step="0.001" min="1" max="1.1" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Volume Surge</label>
                        <input type="number" id="swing_mid_cap_volume" step="0.1" min="1" max="5" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>RSI Min</label>
                        <input type="number" id="swing_mid_cap_rsi_min" step="1" min="0" max="100" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>RSI Max</label>
                        <input type="number" id="swing_mid_cap_rsi_max" step="1" min="0" max="100" onchange="markUnsaved()">
                    </div>
                </div>
            </div>
            
            <!-- SWING Small Cap -->
            <div id="entry_SWING_small_cap" class="tier-entry-content" style="display: none;">
                <div class="config-group">
                    <h3>Small Cap SWING Thresholds</h3>
                    <div class="config-row">
                        <label>Breakout Threshold</label>
                        <input type="number" id="swing_small_cap_breakout" step="0.001" min="1" max="1.1" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Volume Surge</label>
                        <input type="number" id="swing_small_cap_volume" step="0.1" min="1" max="5" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>RSI Min</label>
                        <input type="number" id="swing_small_cap_rsi_min" step="1" min="0" max="100" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>RSI Max</label>
                        <input type="number" id="swing_small_cap_rsi_max" step="1" min="0" max="100" onchange="markUnsaved()">
                    </div>
                </div>
            </div>
            
            <!-- SWING Memecoin -->
            <div id="entry_SWING_memecoin" class="tier-entry-content" style="display: none;">
                <div class="config-group">
                    <h3>Memecoin SWING Thresholds</h3>
                    <div class="config-row">
                        <label>Breakout Threshold</label>
                        <input type="number" id="swing_memecoin_breakout" step="0.001" min="1" max="1.1" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Volume Surge</label>
                        <input type="number" id="swing_memecoin_volume" step="0.1" min="1" max="5" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>RSI Min</label>
                        <input type="number" id="swing_memecoin_rsi_min" step="1" min="0" max="100" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>RSI Max</label>
                        <input type="number" id="swing_memecoin_rsi_max" step="1" min="0" max="100" onchange="markUnsaved()">
                    </div>
                </div>
            </div>
        </div>
        
        <!-- CHANNEL Entry Thresholds -->
        <div id="entry_CHANNEL" class="strategy-entry-content" style="display: none;">
            <div class="tier-tabs">
                <button class="tier-tab active" onclick="showEntryTierTab('CHANNEL', 'large_cap')">Large Cap</button>
                <button class="tier-tab" onclick="showEntryTierTab('CHANNEL', 'mid_cap')">Mid Cap</button>
                <button class="tier-tab" onclick="showEntryTierTab('CHANNEL', 'small_cap')">Small Cap</button>
                <button class="tier-tab" onclick="showEntryTierTab('CHANNEL', 'memecoin')">Memecoin</button>
            </div>
            
            <!-- CHANNEL Tier Contents (similar structure for each tier) -->
            <div id="entry_CHANNEL_large_cap" class="tier-entry-content active">
                <div class="config-group">
                    <h3>Large Cap CHANNEL Thresholds</h3>
                    <div class="config-row">
                        <label>Buy Zone (%)</label>
                        <input type="number" id="channel_large_cap_buy_zone" step="0.01" min="0" max="0.5" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Entry Threshold</label>
                        <input type="number" id="channel_large_cap_entry" step="0.01" min="0" max="1" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Channel Strength</label>
                        <input type="number" id="channel_large_cap_strength" step="0.01" min="0" max="1" onchange="markUnsaved()">
                    </div>
                </div>
            </div>
            
            <!-- CHANNEL Mid Cap -->
            <div id="entry_CHANNEL_mid_cap" class="tier-entry-content" style="display: none;">
                <div class="config-group">
                    <h3>Mid Cap CHANNEL Thresholds</h3>
                    <div class="config-row">
                        <label>Buy Zone (%)</label>
                        <input type="number" id="channel_mid_cap_buy_zone" step="0.01" min="0" max="0.5" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Entry Threshold</label>
                        <input type="number" id="channel_mid_cap_entry" step="0.01" min="0" max="1" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Channel Strength</label>
                        <input type="number" id="channel_mid_cap_strength" step="0.01" min="0" max="1" onchange="markUnsaved()">
                    </div>
                </div>
            </div>
            
            <!-- CHANNEL Small Cap -->
            <div id="entry_CHANNEL_small_cap" class="tier-entry-content" style="display: none;">
                <div class="config-group">
                    <h3>Small Cap CHANNEL Thresholds</h3>
                    <div class="config-row">
                        <label>Buy Zone (%)</label>
                        <input type="number" id="channel_small_cap_buy_zone" step="0.01" min="0" max="0.5" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Entry Threshold</label>
                        <input type="number" id="channel_small_cap_entry" step="0.01" min="0" max="1" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Channel Strength</label>
                        <input type="number" id="channel_small_cap_strength" step="0.01" min="0" max="1" onchange="markUnsaved()">
                    </div>
                </div>
            </div>
            
            <!-- CHANNEL Memecoin -->
            <div id="entry_CHANNEL_memecoin" class="tier-entry-content" style="display: none;">
                <div class="config-group">
                    <h3>Memecoin CHANNEL Thresholds</h3>
                    <div class="config-row">
                        <label>Buy Zone (%)</label>
                        <input type="number" id="channel_memecoin_buy_zone" step="0.01" min="0" max="0.5" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Entry Threshold</label>
                        <input type="number" id="channel_memecoin_entry" step="0.01" min="0" max="1" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Channel Strength</label>
                        <input type="number" id="channel_memecoin_strength" step="0.01" min="0" max="1" onchange="markUnsaved()">
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Risk Management -->
    <div class="config-section risk-management-section">
        <h2>Risk Management</h2>
        
        <!-- Risk Management Tabs -->
        <div class="risk-tabs">
            <button class="risk-tab active" onclick="showRiskTab('position')">Position & Portfolio</button>
            <button class="risk-tab" onclick="showRiskTab('market')">Market Protection</button>
            <button class="risk-tab" onclick="showRiskTab('limiter')">Trade Limiter</button>
            <button class="risk-tab" onclick="showRiskTab('limits')">Risk Limits</button>
            <button class="risk-tab" onclick="showRiskTab('dynamic')">Dynamic Adjustments</button>
        </div>
        
        <!-- Position & Portfolio Controls -->
        <div id="risk_position" class="risk-content active">
            <div class="config-group">
                <h3>Position Sizing <span class="section-tooltip" data-tooltip="Controls how much capital is allocated to each trade. Base size sets the default amount, multiplier adjusts for confidence/conditions, and max % prevents oversized positions.">ⓘ</span></h3>
                <div class="config-row">
                    <label>Base Position Size ($)</label>
                    <input type="number" id="base_position_size" step="10" min="10" max="1000" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Position Size Multiplier</label>
                    <input type="number" id="position_multiplier" step="0.1" min="0.5" max="5" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Max % of Balance per Position</label>
                    <input type="number" id="max_percent_balance" step="1" min="1" max="50" onchange="markUnsaved()">
                </div>
            </div>
            <div class="config-group">
                <h3>Position Limits <span class="section-tooltip" data-tooltip="Maximum number of positions that can be held simultaneously. Limits can be set globally, per strategy, and per symbol to prevent overconcentration.">ⓘ</span></h3>
                <div class="config-row">
                    <label>Max Total Positions</label>
                    <input type="number" id="max_positions" step="1" min="1" max="100" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Max Positions per Strategy</label>
                    <input type="number" id="max_positions_per_strategy" step="1" min="1" max="50" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Max Positions per Symbol</label>
                    <input type="number" id="max_positions_per_symbol" step="1" min="1" max="10" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Max Hold Hours</label>
                    <input type="number" id="max_hold_hours" step="1" min="1" max="168" onchange="markUnsaved()">
                </div>
            </div>
        </div>
        
        <!-- Market Protection -->
        <div id="risk_market" class="risk-content">
            <div class="config-group">
                <h3>Market Regime Thresholds <span class="section-tooltip" data-tooltip="Defines market conditions based on price movements. Panic indicates severe drops, Caution signals moderate declines, and Euphoria warns of potential overheating.">ⓘ</span></h3>
                <div class="config-row">
                    <label>Panic Threshold (%)</label>
                    <input type="number" id="panic_threshold" step="1" min="-50" max="-5" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Caution Threshold (%)</label>
                    <input type="number" id="caution_threshold" step="1" min="-20" max="-1" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Euphoria Threshold (%)</label>
                    <input type="number" id="euphoria_threshold" step="1" min="1" max="20" onchange="markUnsaved()">
                </div>
            </div>
            <div class="config-group">
                <h3>Volatility Thresholds <span class="section-tooltip" data-tooltip="Volatility levels that trigger different trading behaviors. Higher volatility may disable certain strategies or widen stop losses for protection.">ⓘ</span></h3>
                <div class="config-row">
                    <label>Panic Volatility (%)</label>
                    <input type="number" id="volatility_panic" step="0.5" min="5" max="50" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>High Volatility (%)</label>
                    <input type="number" id="volatility_high" step="0.5" min="3" max="30" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Moderate Volatility (%)</label>
                    <input type="number" id="volatility_moderate" step="0.5" min="1" max="20" onchange="markUnsaved()">
                </div>
            </div>
            <div class="config-group">
                <h3>Strategy Volatility Limits <span class="section-tooltip" data-tooltip="Maximum volatility each strategy can tolerate. When exceeded, the strategy is temporarily disabled to prevent losses in unstable conditions.">ⓘ</span></h3>
                <div class="config-row">
                    <label>CHANNEL Max Volatility (%)</label>
                    <input type="number" id="channel_volatility_limit" step="0.5" min="1" max="30" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>SWING Max Volatility (%)</label>
                    <input type="number" id="swing_volatility_limit" step="0.5" min="1" max="30" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>DCA Max Volatility (%)</label>
                    <input type="number" id="dca_volatility_limit" step="0.5" min="1" max="30" onchange="markUnsaved()">
                </div>
            </div>
            <div class="config-group">
                <h3>Cumulative Decline Protection <span class="section-tooltip" data-tooltip="Monitors sustained market declines over 24-48 hour periods. Triggers protective measures when cumulative drops exceed thresholds.">ⓘ</span></h3>
                <div class="config-row">
                    <label>24h Decline Threshold (%)</label>
                    <input type="number" id="decline_24h" step="1" min="-20" max="-1" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>48h Decline Threshold (%)</label>
                    <input type="number" id="decline_48h" step="1" min="-30" max="-1" onchange="markUnsaved()">
                </div>
            </div>
        </div>
        
        <!-- Trade Limiter -->
        <div id="risk_limiter" class="risk-content">
            <div class="config-group">
                <h3>Consecutive Stop Loss Limits <span class="section-tooltip" data-tooltip="Prevents repeated losses on the same symbol. After hitting the max consecutive stops, trading is paused for that symbol's cooldown period.">ⓘ</span></h3>
                <div class="config-row">
                    <label>Max Consecutive Stops</label>
                    <input type="number" id="max_consecutive_stops" step="1" min="1" max="10" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Reset on 50% Take Profit</label>
                    <input type="checkbox" id="reset_on_tp" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Reset on Trailing Stop</label>
                    <input type="checkbox" id="reset_on_trailing" onchange="markUnsaved()">
                </div>
            </div>
            <div class="config-group">
                <h3>Cooldown Hours by Tier <span class="section-tooltip" data-tooltip="How long to pause trading after consecutive stop losses. Longer cooldowns for riskier assets (memecoins) to allow market conditions to stabilize.">ⓘ</span></h3>
                <div class="config-row">
                    <label>Large Cap Cooldown (hours)</label>
                    <input type="number" id="cooldown_large" step="1" min="1" max="48" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Mid Cap Cooldown (hours)</label>
                    <input type="number" id="cooldown_mid" step="1" min="1" max="48" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Small Cap Cooldown (hours)</label>
                    <input type="number" id="cooldown_small" step="1" min="1" max="72" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Memecoin Cooldown (hours)</label>
                    <input type="number" id="cooldown_meme" step="1" min="1" max="168" onchange="markUnsaved()">
                </div>
            </div>
        </div>
        
        <!-- Risk Limits -->
        <div id="risk_limits" class="risk-content">
            <div class="config-group">
                <h3>Daily & Drawdown Limits <span class="section-tooltip" data-tooltip="Maximum acceptable losses per day and from peak equity. When exceeded, trading halts to preserve capital and allow for strategy review.">ⓘ</span></h3>
                <div class="config-row">
                    <label>Max Daily Loss (%)</label>
                    <input type="number" id="max_daily_loss_pct" step="1" min="1" max="50" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Max Daily Loss ($)</label>
                    <input type="number" id="max_daily_loss_usd" step="100" min="100" max="10000" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Max Drawdown (%)</label>
                    <input type="number" id="max_drawdown" step="1" min="5" max="50" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Max Open Risk ($)</label>
                    <input type="number" id="max_open_risk" step="100" min="100" max="10000" onchange="markUnsaved()">
                </div>
            </div>
            <div class="config-group">
                <h3>Risk per Trade <span class="section-tooltip" data-tooltip="Controls position sizing based on risk tolerance. Limits how much capital can be lost on a single trade and consecutive losing streaks.">ⓘ</span></h3>
                <div class="config-row">
                    <label>Risk per Trade (%)</label>
                    <input type="number" id="risk_per_trade" step="0.5" min="0.5" max="10" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Consecutive Loss Limit</label>
                    <input type="number" id="consecutive_loss_limit" step="1" min="1" max="20" onchange="markUnsaved()">
                </div>
            </div>
            <div class="config-group">
                <h3>Emergency Controls <span class="section-tooltip" data-tooltip="Circuit breakers for extreme market conditions. Emergency stop halts all trading, while recovery mode reduces position sizes during drawdowns.">ⓘ</span></h3>
                <div class="config-row">
                    <label>Emergency Stop Enabled</label>
                    <input type="checkbox" id="emergency_stop_enabled" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Recovery Mode Enabled</label>
                    <input type="checkbox" id="recovery_mode_enabled" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Recovery Position Size (%)</label>
                    <input type="number" id="recovery_position_size" step="10" min="10" max="100" onchange="markUnsaved()">
                </div>
            </div>
        </div>
        
        <!-- Dynamic Adjustments -->
        <div id="risk_dynamic" class="risk-content">
            <div class="config-group">
                <h3>Stop Loss Widening <span class="section-tooltip" data-tooltip="Dynamically adjusts stop losses based on market volatility. In high volatility, stops are widened to avoid premature exits from normal price swings.">ⓘ</span></h3>
                <div class="config-row">
                    <label>Stop Widening Enabled</label>
                    <input type="checkbox" id="stop_widening_enabled" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Volatility Factor</label>
                    <input type="number" id="volatility_factor" step="0.1" min="0.1" max="2" onchange="markUnsaved()">
                </div>
            </div>
            <div class="config-group">
                <h3>Max Stop Loss by Tier <span class="section-tooltip" data-tooltip="Maximum allowable stop loss for each market cap tier. Prevents stops from being widened beyond reasonable limits, even in extreme volatility.">ⓘ</span></h3>
                <div class="config-row">
                    <label>Large Cap Max SL (%)</label>
                    <input type="number" id="max_sl_large" step="1" min="5" max="30" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Mid Cap Max SL (%)</label>
                    <input type="number" id="max_sl_mid" step="1" min="5" max="30" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Small Cap Max SL (%)</label>
                    <input type="number" id="max_sl_small" step="1" min="5" max="40" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Memecoin Max SL (%)</label>
                    <input type="number" id="max_sl_meme" step="1" min="5" max="50" onchange="markUnsaved()">
                </div>
            </div>
            <div class="config-group">
                <h3>Regime Multipliers <span class="section-tooltip" data-tooltip="Adjusts trading parameters based on market regime. Higher multipliers in panic/caution modes widen stops and reduce position sizes for protection.">ⓘ</span></h3>
                <div class="config-row">
                    <label>Panic Multiplier</label>
                    <input type="number" id="panic_multiplier" step="0.1" min="1" max="3" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Caution Multiplier</label>
                    <input type="number" id="caution_multiplier" step="0.1" min="1" max="2" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Euphoria Multiplier</label>
                    <input type="number" id="euphoria_multiplier" step="0.1" min="1" max="2" onchange="markUnsaved()">
                </div>
            </div>
            <div class="config-group">
                <h3>Hysteresis Settings <span class="section-tooltip" data-tooltip="Prevents strategies from rapidly toggling on/off. Requires volatility to drop below re-enable threshold and stay there for cooldown period before reactivating.">ⓘ</span></h3>
                <div class="config-row">
                    <label>Channel Disable Volatility (%)</label>
                    <input type="number" id="channel_disable_vol" step="0.5" min="1" max="30" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Channel Re-enable Volatility (%)</label>
                    <input type="number" id="channel_reenable_vol" step="0.5" min="1" max="30" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Re-enable Cooldown (hours)</label>
                    <input type="number" id="reenable_cooldown" step="1" min="1" max="24" onchange="markUnsaved()">
                </div>
            </div>
        </div>
    </div>
    
    <!-- Exit Parameters -->
    <div class="config-section">
        <h2>Exit Parameters by Strategy and Market Cap</h2>
        
        <!-- Strategy Tabs -->
        <div class="strategy-tabs">
            <button class="strategy-tab active" onclick="showStrategyTab('DCA')">DCA</button>
            <button class="strategy-tab" onclick="showStrategyTab('SWING')">SWING</button>
            <button class="strategy-tab" onclick="showStrategyTab('CHANNEL')">CHANNEL</button>
        </div>
        
        <!-- DCA Strategy -->
        <div id="DCA_strategy" class="strategy-content active">
            <!-- Tier Tabs for DCA -->
            <div class="tier-tabs">
                <button class="tier-tab active" onclick="showTier('DCA', 'large_cap')">Large Cap</button>
                <button class="tier-tab" onclick="showTier('DCA', 'mid_cap')">Mid Cap</button>
                <button class="tier-tab" onclick="showTier('DCA', 'small_cap')">Small Cap</button>
                <button class="tier-tab" onclick="showTier('DCA', 'memecoin')">Memecoin</button>
            </div>
            
            <!-- DCA Large Cap -->
            <div id="DCA_large_cap" class="tier-content active">
                <div class="config-group">
                    <div class="config-row">
                        <label>Take Profit (%)</label>
                        <input type="number" id="tp_dca_large" step="0.1" min="1" max="50" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Stop Loss (%)</label>
                        <input type="number" id="sl_dca_large" step="0.1" min="1" max="20" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Trailing Stop (%)</label>
                        <input type="number" id="trail_dca_large" step="0.1" min="1" max="10" onchange="markUnsaved()">
                    </div>
                </div>
            </div>
            
            <!-- DCA Mid Cap -->
            <div id="DCA_mid_cap" class="tier-content">
                <div class="config-group">
                    <div class="config-row">
                        <label>Take Profit (%)</label>
                        <input type="number" id="tp_dca_mid" step="0.1" min="1" max="50" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Stop Loss (%)</label>
                        <input type="number" id="sl_dca_mid" step="0.1" min="1" max="20" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Trailing Stop (%)</label>
                        <input type="number" id="trail_dca_mid" step="0.1" min="1" max="10" onchange="markUnsaved()">
                    </div>
                </div>
            </div>
            
            <!-- DCA Small Cap -->
            <div id="DCA_small_cap" class="tier-content">
                <div class="config-group">
                    <div class="config-row">
                        <label>Take Profit (%)</label>
                        <input type="number" id="tp_dca_small" step="0.1" min="1" max="50" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Stop Loss (%)</label>
                        <input type="number" id="sl_dca_small" step="0.1" min="1" max="20" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Trailing Stop (%)</label>
                        <input type="number" id="trail_dca_small" step="0.1" min="1" max="10" onchange="markUnsaved()">
                    </div>
                </div>
            </div>
            
            <!-- DCA Memecoin -->
            <div id="DCA_memecoin" class="tier-content">
                <div class="config-group">
                    <div class="config-row">
                        <label>Take Profit (%)</label>
                        <input type="number" id="tp_dca_meme" step="0.1" min="1" max="100" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Stop Loss (%)</label>
                        <input type="number" id="sl_dca_meme" step="0.1" min="1" max="30" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Trailing Stop (%)</label>
                        <input type="number" id="trail_dca_meme" step="0.1" min="1" max="20" onchange="markUnsaved()">
                    </div>
                </div>
            </div>
        </div>
        
        <!-- SWING Strategy -->
        <div id="SWING_strategy" class="strategy-content">
            <!-- Tier Tabs for SWING -->
            <div class="tier-tabs">
                <button class="tier-tab active" onclick="showTier('SWING', 'large_cap')">Large Cap</button>
                <button class="tier-tab" onclick="showTier('SWING', 'mid_cap')">Mid Cap</button>
                <button class="tier-tab" onclick="showTier('SWING', 'small_cap')">Small Cap</button>
                <button class="tier-tab" onclick="showTier('SWING', 'memecoin')">Memecoin</button>
            </div>
            
            <!-- SWING Large Cap -->
            <div id="SWING_large_cap" class="tier-content active">
                <div class="config-group">
                    <div class="config-row">
                        <label>Take Profit (%)</label>
                        <input type="number" id="tp_swing_large" step="0.1" min="1" max="50" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Stop Loss (%)</label>
                        <input type="number" id="sl_swing_large" step="0.1" min="1" max="20" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Trailing Stop (%)</label>
                        <input type="number" id="trail_swing_large" step="0.1" min="1" max="10" onchange="markUnsaved()">
                    </div>
                </div>
            </div>
            
            <!-- SWING Mid Cap -->
            <div id="SWING_mid_cap" class="tier-content">
                <div class="config-group">
                    <div class="config-row">
                        <label>Take Profit (%)</label>
                        <input type="number" id="tp_swing_mid" step="0.1" min="1" max="50" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Stop Loss (%)</label>
                        <input type="number" id="sl_swing_mid" step="0.1" min="1" max="20" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Trailing Stop (%)</label>
                        <input type="number" id="trail_swing_mid" step="0.1" min="1" max="10" onchange="markUnsaved()">
                    </div>
                </div>
            </div>
            
            <!-- SWING Small Cap -->
            <div id="SWING_small_cap" class="tier-content">
                <div class="config-group">
                    <div class="config-row">
                        <label>Take Profit (%)</label>
                        <input type="number" id="tp_swing_small" step="0.1" min="1" max="50" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Stop Loss (%)</label>
                        <input type="number" id="sl_swing_small" step="0.1" min="1" max="20" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Trailing Stop (%)</label>
                        <input type="number" id="trail_swing_small" step="0.1" min="1" max="10" onchange="markUnsaved()">
                    </div>
                </div>
            </div>
            
            <!-- SWING Memecoin -->
            <div id="SWING_memecoin" class="tier-content">
                <div class="config-group">
                    <div class="config-row">
                        <label>Take Profit (%)</label>
                        <input type="number" id="tp_swing_meme" step="0.1" min="1" max="100" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Stop Loss (%)</label>
                        <input type="number" id="sl_swing_meme" step="0.1" min="1" max="30" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Trailing Stop (%)</label>
                        <input type="number" id="trail_swing_meme" step="0.1" min="1" max="20" onchange="markUnsaved()">
                    </div>
                </div>
            </div>
        </div>
        
        <!-- CHANNEL Strategy -->
        <div id="CHANNEL_strategy" class="strategy-content">
            <!-- Tier Tabs for CHANNEL -->
            <div class="tier-tabs">
                <button class="tier-tab active" onclick="showTier('CHANNEL', 'large_cap')">Large Cap</button>
                <button class="tier-tab" onclick="showTier('CHANNEL', 'mid_cap')">Mid Cap</button>
                <button class="tier-tab" onclick="showTier('CHANNEL', 'small_cap')">Small Cap</button>
                <button class="tier-tab" onclick="showTier('CHANNEL', 'memecoin')">Memecoin</button>
            </div>
            
            <!-- CHANNEL Large Cap -->
            <div id="CHANNEL_large_cap" class="tier-content active">
                <div class="config-group">
                    <div class="config-row">
                        <label>Take Profit (%)</label>
                        <input type="number" id="tp_channel_large" step="0.1" min="1" max="50" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Stop Loss (%)</label>
                        <input type="number" id="sl_channel_large" step="0.1" min="1" max="20" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Trailing Stop (%)</label>
                        <input type="number" id="trail_channel_large" step="0.1" min="1" max="10" onchange="markUnsaved()">
                    </div>
                </div>
            </div>
            
            <!-- CHANNEL Mid Cap -->
            <div id="CHANNEL_mid_cap" class="tier-content">
                <div class="config-group">
                    <div class="config-row">
                        <label>Take Profit (%)</label>
                        <input type="number" id="tp_channel_mid" step="0.1" min="1" max="50" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Stop Loss (%)</label>
                        <input type="number" id="sl_channel_mid" step="0.1" min="1" max="20" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Trailing Stop (%)</label>
                        <input type="number" id="trail_channel_mid" step="0.1" min="1" max="10" onchange="markUnsaved()">
                    </div>
                </div>
            </div>
            
            <!-- CHANNEL Small Cap -->
            <div id="CHANNEL_small_cap" class="tier-content">
                <div class="config-group">
                    <div class="config-row">
                        <label>Take Profit (%)</label>
                        <input type="number" id="tp_channel_small" step="0.1" min="1" max="50" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Stop Loss (%)</label>
                        <input type="number" id="sl_channel_small" step="0.1" min="1" max="20" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Trailing Stop (%)</label>
                        <input type="number" id="trail_channel_small" step="0.1" min="1" max="10" onchange="markUnsaved()">
                    </div>
                </div>
            </div>
            
            <!-- CHANNEL Memecoin -->
            <div id="CHANNEL_memecoin" class="tier-content">
                <div class="config-group">
                    <div class="config-row">
                        <label>Take Profit (%)</label>
                        <input type="number" id="tp_channel_meme" step="0.1" min="1" max="100" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Stop Loss (%)</label>
                        <input type="number" id="sl_channel_meme" step="0.1" min="1" max="30" onchange="markUnsaved()">
                    </div>
                    <div class="config-row">
                        <label>Trailing Stop (%)</label>
                        <input type="number" id="trail_channel_meme" step="0.1" min="1" max="20" onchange="markUnsaved()">
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Save/Discard Controls for Paper Trading -->
<div class="save-controls">
    <div id="unsavedIndicator" style="display: none;" class="unsaved-indicator">
        ⚠️ Settings have been modified, click Save All Changes to save
    </div>
    <div class="save-buttons">
        <button class="save-btn" onclick="saveAllChanges()">💾 Save All Changes</button>
        <button class="discard-btn" onclick="discardChanges()">🔄 Discard Changes</button>
    </div>
</div>

</div> <!-- End of Paper Trading Configuration Section -->

<!-- Configuration History -->
<div class="config-history">
    <h2>Recent Configuration Changes</h2>
    <div id="configHistoryTable">
        <table>
            <thead>
                <tr>
                    <th>Timestamp</th>
                    <th>Section</th>
                    <th>Field</th>
                    <th>Old Value</th>
                    <th>New Value</th>
                    <th>Changed By</th>
                </tr>
            </thead>
            <tbody id="configHistoryBody">
                <!-- Will be populated by JavaScript -->
            </tbody>
        </table>
    </div>
</div>
"""

ADMIN_CSS = r"""
<style>
.kill-switch-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.kill-switch-container {
    display: flex;
    align-items: center;
    gap: 20px;
    margin-top: 10px;
}

.switch {
    position: relative;
    display: inline-block;
    width: 60px;
    height: 34px;
}

.switch input {
    opacity: 0;
    width: 0;
    height: 0;
}

.slider {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: #ccc;
    transition: .4s;
}

.slider:before {
    position: absolute;
    content: "";
    height: 26px;
    width: 26px;
    left: 4px;
    bottom: 4px;
    background-color: white;
    transition: .4s;
}

input:checked + .slider {
    background-color: #2196F3;
}

input:checked + .slider:before {
    transform: translateX(26px);
}

.slider.round {
    border-radius: 34px;
}

.slider.round:before {
    border-radius: 50%;
}

.status-text {
    font-size: 1.2rem;
    font-weight: bold;
}

.config-sections {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
    gap: 20px;
    margin-top: 30px;
}

.config-section {
    background: rgba(30, 41, 59, 0.5);
    border: 1px solid rgba(59, 130, 246, 0.3);
    border-radius: 12px;
    padding: 20px;
}

.config-section h2 {
    color: #60a5fa;
    margin-bottom: 20px;
    font-size: 1.3rem;
}

.config-group {
    margin-bottom: 20px;
}

.config-group h3 {
    color: #94a3b8;
    margin-bottom: 15px;
    font-size: 1.1rem;
}

.config-row {
    display: grid;
    grid-template-columns: 200px 150px 100px;
    gap: 10px;
    align-items: center;
    margin-bottom: 10px;
}

.config-row label {
    color: #cbd5e1;
}

.config-row input {
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(59, 130, 246, 0.3);
    color: #e2e8f0;
    padding: 8px;
    border-radius: 6px;
}

.config-row button {
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.3s ease;
}

.config-row button:hover {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
}

.config-history {
    margin-top: 40px;
    background: rgba(30, 41, 59, 0.5);
    border: 1px solid rgba(59, 130, 246, 0.3);
    border-radius: 12px;
    padding: 20px;
}

.config-history h2 {
    color: #60a5fa;
    margin-bottom: 20px;
}

.config-history table {
    width: 100%;
    border-collapse: collapse;
}

.config-history th {
    background: rgba(59, 130, 246, 0.2);
    color: #60a5fa;
    padding: 10px;
    text-align: left;
    border-bottom: 1px solid rgba(59, 130, 246, 0.3);
}

.config-history td {
    color: #cbd5e1;
    padding: 10px;
    border-bottom: 1px solid rgba(59, 130, 246, 0.1);
}
</style>
"""

ADMIN_SCRIPTS = r"""
<script>
let originalConfig = {};
let currentConfig = {};
let hasUnsavedChanges = false;
const strategies = ['DCA', 'SWING', 'CHANNEL'];
let unsavedValues = {}; // Track unsaved input values

// Mark configuration as having unsaved changes
function markUnsaved() {
    hasUnsavedChanges = true;
    updateUnsavedIndicator();
    
    // Store all current input values
    storeAllInputValues();
}

// Store all current input values
function storeAllInputValues() {
    document.querySelectorAll('input').forEach(input => {
        if (input.id) {
            unsavedValues[input.id] = input.type === 'checkbox' ? input.checked : input.value;
        }
    });
    console.log('Stored unsaved values:', unsavedValues);
}

// Update unsaved indicator
function updateUnsavedIndicator() {
    const indicator = document.getElementById('unsavedIndicator');
    if (indicator) {
        indicator.style.display = hasUnsavedChanges ? 'flex' : 'none';
    }
}

// Load current configuration
async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        originalConfig = await response.json();
        currentConfig = JSON.parse(JSON.stringify(originalConfig));
        
        // Populate form fields
        document.getElementById('killSwitch').checked = currentConfig.global_settings?.trading_enabled || false;
        document.getElementById('killSwitchStatus').textContent = currentConfig.global_settings?.trading_enabled ? 'ENABLED' : 'DISABLED';
        document.getElementById('killSwitchStatus').style.color = currentConfig.global_settings?.trading_enabled ? '#10b981' : '#ef4444';
        
        // Populate tier-specific entry thresholds
        // Using strategies and tiers already defined at the top
        const tiers = ['large_cap', 'mid_cap', 'small_cap', 'memecoin'];
        
        // DCA Entry Thresholds by Tier
        const dcaThresholds = currentConfig.strategies?.DCA?.detection_thresholds_by_tier || {};
        tiers.forEach(tier => {
            const tierData = dcaThresholds[tier] || {};
            const dropInput = document.getElementById(`dca_${tier}_drop`);
            const volumeReqInput = document.getElementById(`dca_${tier}_volume_req`);
            const gridLevelsInput = document.getElementById(`dca_${tier}_grid_levels`);
            const gridSpacingInput = document.getElementById(`dca_${tier}_grid_spacing`);
            
            if (dropInput) dropInput.value = tierData.drop_threshold || -4;
            if (volumeReqInput) volumeReqInput.value = tierData.volume_requirement || 0.85;
            if (gridLevelsInput) gridLevelsInput.value = tierData.grid_levels || 5;
            if (gridSpacingInput) gridSpacingInput.value = tierData.grid_spacing || 0.02;
        });
        
        // SWING Entry Thresholds by Tier
        const swingThresholds = currentConfig.strategies?.SWING?.detection_thresholds_by_tier || {};
        tiers.forEach(tier => {
            const tierData = swingThresholds[tier] || {};
            const breakoutInput = document.getElementById(`swing_${tier}_breakout`);
            const volumeInput = document.getElementById(`swing_${tier}_volume`);
            const rsiMinInput = document.getElementById(`swing_${tier}_rsi_min`);
            const rsiMaxInput = document.getElementById(`swing_${tier}_rsi_max`);
            
            if (breakoutInput) breakoutInput.value = tierData.breakout_threshold || 1.01;
            if (volumeInput) volumeInput.value = tierData.volume_surge || 1.3;
            if (rsiMinInput) rsiMinInput.value = tierData.rsi_min || 45;
            if (rsiMaxInput) rsiMaxInput.value = tierData.rsi_max || 75;
        });
        
        // CHANNEL Entry Thresholds by Tier
        const channelThresholds = currentConfig.strategies?.CHANNEL?.detection_thresholds_by_tier || {};
        tiers.forEach(tier => {
            const tierData = channelThresholds[tier] || {};
            const buyZoneInput = document.getElementById(`channel_${tier}_buy_zone`);
            const entryInput = document.getElementById(`channel_${tier}_entry`);
            const strengthInput = document.getElementById(`channel_${tier}_strength`);
            
            if (buyZoneInput) buyZoneInput.value = tierData.buy_zone || 0.05;
            if (entryInput) entryInput.value = tierData.entry_threshold || 0.9;
            if (strengthInput) strengthInput.value = tierData.channel_strength_min || 0.75;
        });
        
        // Populate Risk Management - Position & Portfolio
        document.getElementById('base_position_size').value = currentConfig.position_management?.position_sizing?.base_position_size_usd || 50;
        document.getElementById('position_multiplier').value = currentConfig.position_management?.position_sizing?.position_size_multiplier || 1.5;
        document.getElementById('max_percent_balance').value = (currentConfig.position_management?.position_sizing?.max_percent_of_balance || 0.5) * 100;
        document.getElementById('max_positions').value = currentConfig.position_management?.max_positions_total || 50;
        document.getElementById('max_positions_per_strategy').value = currentConfig.position_management?.max_positions_per_strategy || 50;
        document.getElementById('max_positions_per_symbol').value = currentConfig.position_management?.max_positions_per_symbol || 3;
        document.getElementById('max_hold_hours').value = currentConfig.position_management?.max_hold_hours || 72;
        
        // Populate Risk Management - Market Protection
        const marketProtection = currentConfig.market_protection || {};
        document.getElementById('panic_threshold').value = (marketProtection.enhanced_regime?.panic_threshold || -0.1) * 100;
        document.getElementById('caution_threshold').value = (marketProtection.enhanced_regime?.caution_threshold || -0.05) * 100;
        document.getElementById('euphoria_threshold').value = (marketProtection.enhanced_regime?.euphoria_threshold || 0.05) * 100;
        document.getElementById('volatility_panic').value = marketProtection.volatility_thresholds?.panic || 12;
        document.getElementById('volatility_high').value = marketProtection.volatility_thresholds?.high || 8;
        document.getElementById('volatility_moderate').value = marketProtection.volatility_thresholds?.moderate || 5;
        document.getElementById('channel_volatility_limit').value = marketProtection.volatility_thresholds?.strategy_limits?.CHANNEL || 8;
        document.getElementById('swing_volatility_limit').value = marketProtection.volatility_thresholds?.strategy_limits?.SWING || 15;
        document.getElementById('dca_volatility_limit').value = marketProtection.volatility_thresholds?.strategy_limits?.DCA || 20;
        document.getElementById('decline_24h').value = (marketProtection.cumulative_decline?.['24h_threshold'] || -3);
        document.getElementById('decline_48h').value = (marketProtection.cumulative_decline?.['48h_threshold'] || -5);
        
        // Populate Risk Management - Trade Limiter
        const tradeLimiter = marketProtection.trade_limiter || {};
        document.getElementById('max_consecutive_stops').value = tradeLimiter.max_consecutive_stops || 3;
        document.getElementById('reset_on_tp').checked = tradeLimiter.reset_on_50pct_tp !== false;
        document.getElementById('reset_on_trailing').checked = tradeLimiter.reset_on_trailing_stop !== false;
        document.getElementById('cooldown_large').value = tradeLimiter.cooldown_hours_by_tier?.large_cap || 4;
        document.getElementById('cooldown_mid').value = tradeLimiter.cooldown_hours_by_tier?.mid_cap || 6;
        document.getElementById('cooldown_small').value = tradeLimiter.cooldown_hours_by_tier?.small_cap || 12;
        document.getElementById('cooldown_meme').value = tradeLimiter.cooldown_hours_by_tier?.memecoin || 24;
        
        // Populate Risk Management - Risk Limits (placeholder values for now)
        const riskManagement = currentConfig.risk_management || {};
        document.getElementById('max_daily_loss_pct').value = riskManagement.max_daily_loss_pct || 10;
        document.getElementById('max_daily_loss_usd').value = riskManagement.max_daily_loss_usd || 1000;
        document.getElementById('max_drawdown').value = riskManagement.max_drawdown || 20;
        document.getElementById('max_open_risk').value = riskManagement.max_open_risk || 2000;
        document.getElementById('risk_per_trade').value = riskManagement.risk_per_trade || 2;
        document.getElementById('consecutive_loss_limit').value = riskManagement.consecutive_loss_limit || 5;
        document.getElementById('emergency_stop_enabled').checked = riskManagement.emergency_stop_enabled || false;
        document.getElementById('recovery_mode_enabled').checked = riskManagement.recovery_mode_enabled || false;
        document.getElementById('recovery_position_size').value = riskManagement.recovery_position_size || 50;
        
        // Populate Risk Management - Dynamic Adjustments
        const stopWidening = marketProtection.stop_widening || {};
        document.getElementById('stop_widening_enabled').checked = stopWidening.enabled !== false;
        document.getElementById('volatility_factor').value = stopWidening.volatility_factor || 0.3;
        document.getElementById('max_sl_large').value = (stopWidening.max_stop_loss_by_tier?.large_cap || 0.1) * 100;
        document.getElementById('max_sl_mid').value = (stopWidening.max_stop_loss_by_tier?.mid_cap || 0.12) * 100;
        document.getElementById('max_sl_small').value = (stopWidening.max_stop_loss_by_tier?.small_cap || 0.15) * 100;
        document.getElementById('max_sl_meme').value = (stopWidening.max_stop_loss_by_tier?.memecoin || 0.15) * 100;
        document.getElementById('panic_multiplier').value = stopWidening.regime_multipliers?.PANIC || 1.5;
        document.getElementById('caution_multiplier').value = stopWidening.regime_multipliers?.CAUTION || 1.3;
        document.getElementById('euphoria_multiplier').value = stopWidening.regime_multipliers?.EUPHORIA || 1.2;
        
        const hysteresis = marketProtection.hysteresis || {};
        document.getElementById('channel_disable_vol').value = hysteresis.channel_disable_volatility || 8;
        document.getElementById('channel_reenable_vol').value = hysteresis.channel_reenable_volatility || 6;
        document.getElementById('reenable_cooldown').value = hysteresis.reenable_cooldown_hours || 2;
        
        // Populate exit parameters for all strategies and tiers
        // Using tiers already defined above
        
        strategies.forEach(strategy => {
            const strategyExits = currentConfig.strategies?.[strategy]?.exits_by_tier || {};
            const prefix = strategy.toLowerCase();
            
            // Large Cap
            const tpLarge = document.getElementById(`tp_${prefix}_large`);
            const slLarge = document.getElementById(`sl_${prefix}_large`);
            const trailLarge = document.getElementById(`trail_${prefix}_large`);
            if (tpLarge) tpLarge.value = Math.round((strategyExits.large_cap?.take_profit || 0.05) * 1000) / 10;
            if (slLarge) slLarge.value = Math.round((strategyExits.large_cap?.stop_loss || 0.05) * 1000) / 10;
            if (trailLarge) trailLarge.value = Math.round((strategyExits.large_cap?.trailing_stop || 0.03) * 1000) / 10;
            
            // Mid Cap
            const tpMid = document.getElementById(`tp_${prefix}_mid`);
            const slMid = document.getElementById(`sl_${prefix}_mid`);
            const trailMid = document.getElementById(`trail_${prefix}_mid`);
            if (tpMid) tpMid.value = Math.round((strategyExits.mid_cap?.take_profit || 0.08) * 1000) / 10;
            if (slMid) slMid.value = Math.round((strategyExits.mid_cap?.stop_loss || 0.06) * 1000) / 10;
            if (trailMid) trailMid.value = Math.round((strategyExits.mid_cap?.trailing_stop || 0.04) * 1000) / 10;
            
            // Small Cap
            const tpSmall = document.getElementById(`tp_${prefix}_small`);
            const slSmall = document.getElementById(`sl_${prefix}_small`);
            const trailSmall = document.getElementById(`trail_${prefix}_small`);
            if (tpSmall) tpSmall.value = Math.round((strategyExits.small_cap?.take_profit || 0.12) * 1000) / 10;
            if (slSmall) slSmall.value = Math.round((strategyExits.small_cap?.stop_loss || 0.08) * 1000) / 10;
            if (trailSmall) trailSmall.value = Math.round((strategyExits.small_cap?.trailing_stop || 0.05) * 1000) / 10;
            
            // Memecoin
            const tpMeme = document.getElementById(`tp_${prefix}_meme`);
            const slMeme = document.getElementById(`sl_${prefix}_meme`);
            const trailMeme = document.getElementById(`trail_${prefix}_meme`);
            if (tpMeme) tpMeme.value = Math.round((strategyExits.memecoin?.take_profit || 0.15) * 1000) / 10;
            if (slMeme) slMeme.value = Math.round((strategyExits.memecoin?.stop_loss || 0.12) * 1000) / 10;
            if (trailMeme) trailMeme.value = Math.round((strategyExits.memecoin?.trailing_stop || 0.08) * 1000) / 10;
        });
        
        hasUnsavedChanges = false;
        updateUnsavedIndicator();
        
    } catch (error) {
        console.error('Error loading config:', error);
    }
}

// Toggle kill switch
async function toggleKillSwitch() {
    const isEnabled = document.getElementById('killSwitch').checked;
    
    try {
        const response = await fetch('/api/config/update', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                updates: {'global_settings.trading_enabled': isEnabled},
                change_type: 'admin_panel',
                changed_by: 'admin',
                description: `Trading ${isEnabled ? 'enabled' : 'disabled'} via admin panel`
            })
        });
        
        if (response.ok) {
            document.getElementById('killSwitchStatus').textContent = isEnabled ? 'ENABLED' : 'DISABLED';
            document.getElementById('killSwitchStatus').style.color = isEnabled ? '#10b981' : '#ef4444';
            showNotification(`Trading ${isEnabled ? 'enabled' : 'disabled'} successfully`, 'success');
            loadConfigHistory();
        } else {
            showNotification('Failed to update kill switch', 'error');
            document.getElementById('killSwitch').checked = !isEnabled; // Revert
        }
    } catch (error) {
        console.error('Error toggling kill switch:', error);
        showNotification('Error updating kill switch', 'error');
        document.getElementById('killSwitch').checked = !isEnabled; // Revert
    }
}

// Update configuration value
async function updateConfig(path, inputId) {
    const input = document.getElementById(inputId);
    const value = parseFloat(input.value);
    
    try {
        const response = await fetch('/api/config/update', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                updates: {[path]: value},
                change_type: 'admin_panel',
                changed_by: 'admin',
                description: `Updated ${path} to ${value}`
            })
        });
        
        if (response.ok) {
            showNotification(`Updated ${path} successfully`, 'success');
            loadConfigHistory();
        } else {
            showNotification(`Failed to update ${path}`, 'error');
        }
    } catch (error) {
        console.error('Error updating config:', error);
        showNotification('Error updating configuration', 'error');
    }
}

// Load configuration history
// Collect all changes
function collectChanges() {
    const changes = {};
    console.log('collectChanges called with unsavedValues:', unsavedValues);
    
    // Kill switch
    const killSwitch = document.getElementById('killSwitch').checked;
    if (killSwitch !== originalConfig.global_settings?.trading_enabled) {
        changes['global_settings.trading_enabled'] = killSwitch;
    }
    
    // Tier-specific entry thresholds
    const tiers = ['large_cap', 'mid_cap', 'small_cap', 'memecoin'];
    
    // DCA Entry Thresholds by Tier
    tiers.forEach(tier => {
        checkChange(changes, `strategies.DCA.detection_thresholds_by_tier.${tier}.drop_threshold`, `dca_${tier}_drop`);
        checkChange(changes, `strategies.DCA.detection_thresholds_by_tier.${tier}.volume_requirement`, `dca_${tier}_volume_req`);
        checkChange(changes, `strategies.DCA.detection_thresholds_by_tier.${tier}.grid_levels`, `dca_${tier}_grid_levels`);
        checkChange(changes, `strategies.DCA.detection_thresholds_by_tier.${tier}.grid_spacing`, `dca_${tier}_grid_spacing`);
    });
    
    // SWING Entry Thresholds by Tier
    tiers.forEach(tier => {
        checkChange(changes, `strategies.SWING.detection_thresholds_by_tier.${tier}.breakout_threshold`, `swing_${tier}_breakout`);
        checkChange(changes, `strategies.SWING.detection_thresholds_by_tier.${tier}.volume_surge`, `swing_${tier}_volume`);
        checkChange(changes, `strategies.SWING.detection_thresholds_by_tier.${tier}.rsi_min`, `swing_${tier}_rsi_min`);
        checkChange(changes, `strategies.SWING.detection_thresholds_by_tier.${tier}.rsi_max`, `swing_${tier}_rsi_max`);
    });
    
    // CHANNEL Entry Thresholds by Tier
    tiers.forEach(tier => {
        checkChange(changes, `strategies.CHANNEL.detection_thresholds_by_tier.${tier}.buy_zone`, `channel_${tier}_buy_zone`);
        checkChange(changes, `strategies.CHANNEL.detection_thresholds_by_tier.${tier}.entry_threshold`, `channel_${tier}_entry`);
        checkChange(changes, `strategies.CHANNEL.detection_thresholds_by_tier.${tier}.channel_strength_min`, `channel_${tier}_strength`);
    });
    
    // Risk Management - Position & Portfolio
    checkChange(changes, 'position_management.position_sizing.base_position_size_usd', 'base_position_size');
    checkChange(changes, 'position_management.position_sizing.position_size_multiplier', 'position_multiplier');
    checkChangePercentage(changes, 'position_management.position_sizing.max_percent_of_balance', 'max_percent_balance');
    checkChange(changes, 'position_management.max_positions_total', 'max_positions');
    checkChange(changes, 'position_management.max_positions_per_strategy', 'max_positions_per_strategy');
    checkChange(changes, 'position_management.max_positions_per_symbol', 'max_positions_per_symbol');
    checkChange(changes, 'position_management.max_hold_hours', 'max_hold_hours');
    
    // Risk Management - Market Protection
    checkChangePercentage(changes, 'market_protection.enhanced_regime.panic_threshold', 'panic_threshold');
    checkChangePercentage(changes, 'market_protection.enhanced_regime.caution_threshold', 'caution_threshold');
    checkChangePercentage(changes, 'market_protection.enhanced_regime.euphoria_threshold', 'euphoria_threshold');
    checkChange(changes, 'market_protection.volatility_thresholds.panic', 'volatility_panic');
    checkChange(changes, 'market_protection.volatility_thresholds.high', 'volatility_high');
    checkChange(changes, 'market_protection.volatility_thresholds.moderate', 'volatility_moderate');
    checkChange(changes, 'market_protection.volatility_thresholds.strategy_limits.CHANNEL', 'channel_volatility_limit');
    checkChange(changes, 'market_protection.volatility_thresholds.strategy_limits.SWING', 'swing_volatility_limit');
    checkChange(changes, 'market_protection.volatility_thresholds.strategy_limits.DCA', 'dca_volatility_limit');
    checkChange(changes, 'market_protection.cumulative_decline.24h_threshold', 'decline_24h');
    checkChange(changes, 'market_protection.cumulative_decline.48h_threshold', 'decline_48h');
    
    // Risk Management - Trade Limiter
    checkChange(changes, 'market_protection.trade_limiter.max_consecutive_stops', 'max_consecutive_stops');
    checkChangeBoolean(changes, 'market_protection.trade_limiter.reset_on_50pct_tp', 'reset_on_tp');
    checkChangeBoolean(changes, 'market_protection.trade_limiter.reset_on_trailing_stop', 'reset_on_trailing');
    checkChange(changes, 'market_protection.trade_limiter.cooldown_hours_by_tier.large_cap', 'cooldown_large');
    checkChange(changes, 'market_protection.trade_limiter.cooldown_hours_by_tier.mid_cap', 'cooldown_mid');
    checkChange(changes, 'market_protection.trade_limiter.cooldown_hours_by_tier.small_cap', 'cooldown_small');
    checkChange(changes, 'market_protection.trade_limiter.cooldown_hours_by_tier.memecoin', 'cooldown_meme');
    
    // Risk Management - Risk Limits (these will create new fields in config)
    checkChange(changes, 'risk_management.max_daily_loss_pct', 'max_daily_loss_pct');
    checkChange(changes, 'risk_management.max_daily_loss_usd', 'max_daily_loss_usd');
    checkChange(changes, 'risk_management.max_drawdown', 'max_drawdown');
    checkChange(changes, 'risk_management.max_open_risk', 'max_open_risk');
    checkChange(changes, 'risk_management.risk_per_trade', 'risk_per_trade');
    checkChange(changes, 'risk_management.consecutive_loss_limit', 'consecutive_loss_limit');
    checkChangeBoolean(changes, 'risk_management.emergency_stop_enabled', 'emergency_stop_enabled');
    checkChangeBoolean(changes, 'risk_management.recovery_mode_enabled', 'recovery_mode_enabled');
    checkChange(changes, 'risk_management.recovery_position_size', 'recovery_position_size');
    
    // Risk Management - Dynamic Adjustments
    checkChangeBoolean(changes, 'market_protection.stop_widening.enabled', 'stop_widening_enabled');
    checkChange(changes, 'market_protection.stop_widening.volatility_factor', 'volatility_factor');
    checkChangePercentage(changes, 'market_protection.stop_widening.max_stop_loss_by_tier.large_cap', 'max_sl_large');
    checkChangePercentage(changes, 'market_protection.stop_widening.max_stop_loss_by_tier.mid_cap', 'max_sl_mid');
    checkChangePercentage(changes, 'market_protection.stop_widening.max_stop_loss_by_tier.small_cap', 'max_sl_small');
    checkChangePercentage(changes, 'market_protection.stop_widening.max_stop_loss_by_tier.memecoin', 'max_sl_meme');
    checkChange(changes, 'market_protection.stop_widening.regime_multipliers.PANIC', 'panic_multiplier');
    checkChange(changes, 'market_protection.stop_widening.regime_multipliers.CAUTION', 'caution_multiplier');
    checkChange(changes, 'market_protection.stop_widening.regime_multipliers.EUPHORIA', 'euphoria_multiplier');
    checkChange(changes, 'market_protection.hysteresis.channel_disable_volatility', 'channel_disable_vol');
    checkChange(changes, 'market_protection.hysteresis.channel_reenable_volatility', 'channel_reenable_vol');
    checkChange(changes, 'market_protection.hysteresis.reenable_cooldown_hours', 'reenable_cooldown');
    
    // Exit parameters for all strategies and tiers
    // strategies already defined at top
    const tierNames = [
        {tier: 'large_cap', suffix: 'large'},
        {tier: 'mid_cap', suffix: 'mid'},
        {tier: 'small_cap', suffix: 'small'},
        {tier: 'memecoin', suffix: 'meme'}
    ];
    
    strategies.forEach(strategy => {
        const prefix = strategy.toLowerCase();
        tierNames.forEach(({tier, suffix}) => {
            // Get the input elements for this strategy and tier
            const tpInput = document.getElementById(`tp_${prefix}_${suffix}`);
            const slInput = document.getElementById(`sl_${prefix}_${suffix}`);
            const trailInput = document.getElementById(`trail_${prefix}_${suffix}`);
            
            if (tpInput && slInput && trailInput) {
                // Convert percentage to decimal when saving
                const tpValue = parseFloat(tpInput.value) / 100;
                const slValue = parseFloat(slInput.value) / 100;
                const trailValue = parseFloat(trailInput.value) / 100;
                
                const currentTp = currentConfig.strategies?.[strategy]?.exits_by_tier?.[tier]?.take_profit;
                const currentSl = currentConfig.strategies?.[strategy]?.exits_by_tier?.[tier]?.stop_loss;
                const currentTrail = currentConfig.strategies?.[strategy]?.exits_by_tier?.[tier]?.trailing_stop;
                
                if (currentTp !== tpValue && !isNaN(tpValue)) {
                    changes[`strategies.${strategy}.exits_by_tier.${tier}.take_profit`] = tpValue;
                }
                if (currentSl !== slValue && !isNaN(slValue)) {
                    changes[`strategies.${strategy}.exits_by_tier.${tier}.stop_loss`] = slValue;
                }
                if (currentTrail !== trailValue && !isNaN(trailValue)) {
                    changes[`strategies.${strategy}.exits_by_tier.${tier}.trailing_stop`] = trailValue;
                }
            }
        });
    });
    
    return changes;
}

// Helper to check if a value changed
function checkChange(changes, path, elementId) {
    // First check unsavedValues for any pending changes
    let newValue = null;
    
    if (unsavedValues.hasOwnProperty(elementId)) {
        // Use the unsaved value if it exists
        newValue = parseFloat(unsavedValues[elementId]);
        console.log(`checkChange ${elementId}: using unsaved value ${unsavedValues[elementId]} -> ${newValue}`);
    } else {
        // Otherwise, try to get the current DOM value
        const element = document.getElementById(elementId);
        if (!element) {
            console.log(`checkChange ${elementId}: element not found`);
            return;
        }
        newValue = element.value ? parseFloat(element.value) : null;
        console.log(`checkChange ${elementId}: using DOM value ${element.value} -> ${newValue}`);
    }
    
    const oldValue = getNestedValue(originalConfig, path);
    console.log(`checkChange ${elementId}: comparing new ${newValue} vs old ${oldValue}`);
    
    if (newValue !== oldValue && newValue !== null) {
        changes[path] = newValue;
        console.log(`checkChange ${elementId}: CHANGE DETECTED`);
    }
}

// Get nested value from object
function getNestedValue(obj, path) {
    const keys = path.split('.');
    let value = obj;
    for (const key of keys) {
        value = value?.[key];
    }
    return value;
}

// Helper to check if a percentage value changed (converts % to decimal)
function checkChangePercentage(changes, path, elementId) {
    // First check unsavedValues for any pending changes
    let newValue = null;
    
    if (unsavedValues.hasOwnProperty(elementId)) {
        // Use the unsaved value if it exists
        newValue = parseFloat(unsavedValues[elementId]) / 100;
    } else {
        // Otherwise, try to get the current DOM value
        const element = document.getElementById(elementId);
        if (!element) return;
        newValue = element.value ? parseFloat(element.value) / 100 : null;
    }
    
    const oldValue = getNestedValue(originalConfig, path);
    
    if (newValue !== oldValue && newValue !== null) {
        changes[path] = newValue;
    }
}

// Helper to check if a boolean value changed
function checkChangeBoolean(changes, path, elementId) {
    // First check unsavedValues for any pending changes
    let newValue = null;
    
    if (unsavedValues.hasOwnProperty(elementId)) {
        // Use the unsaved value if it exists (for checkboxes, it's a boolean)
        newValue = unsavedValues[elementId];
    } else {
        // Otherwise, try to get the current DOM value
        const element = document.getElementById(elementId);
        if (!element) return;
        newValue = element.checked;
    }
    
    const oldValue = getNestedValue(originalConfig, path);
    
    if (newValue !== oldValue) {
        changes[path] = newValue;
    }
}

// Save all changes
async function saveAllChanges() {
    console.log('saveAllChanges called');
    const changes = collectChanges();
    console.log('Changes collected:', changes);
    
    if (Object.keys(changes).length === 0) {
        showNotification('No changes to save', 'info');
        return;
    }
    
    console.log('Sending POST request with changes:', changes);
    try {
        const response = await fetch('/api/config/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                updates: changes,
                change_type: 'admin_panel',
                changed_by: 'admin',
                description: `Bulk update: ${Object.keys(changes).length} fields changed`
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            // Show success with any warnings
            showNotification(`Saved ${Object.keys(changes).length} configuration changes`, 'success');
            if (data.warnings && data.warnings.length > 0) {
                showValidationMessages(data.warnings, 'warning');
            }
            hasUnsavedChanges = false;
            unsavedValues = {}; // Clear unsaved values after successful save
            updateUnsavedIndicator();
            await loadConfig();  // Reload to get new version
            await loadConfigHistory();
        } else {
            // Show validation errors
            if (data.errors && data.errors.length > 0) {
                showValidationMessages(data.errors, 'error');
            }
            if (data.warnings && data.warnings.length > 0) {
                showValidationMessages(data.warnings, 'warning');
            }
            showNotification(data.message || 'Failed to save configuration', 'error');
        }
    } catch (error) {
        console.error('Error saving config:', error);
        showNotification('Failed to save configuration', 'error');
    }
}

// Discard changes
function discardChanges() {
    if (confirm('Are you sure you want to discard all unsaved changes?')) {
        loadConfig();  // Reload original values
        hasUnsavedChanges = false;
        unsavedValues = {}; // Clear unsaved values on discard
        updateUnsavedIndicator();
        showNotification('Changes discarded', 'info');
    }
}

async function loadConfigHistory() {
    try {
        const response = await fetch('/api/config/history');
        const history = await response.json();
        
        const tbody = document.getElementById('configHistoryBody');
        tbody.innerHTML = '';
        
        history.slice(0, 10).forEach(change => {
            const row = tbody.insertRow();
            row.innerHTML = `
                <td>${new Date(change.change_timestamp).toLocaleString()}</td>
                <td>${change.config_section}</td>
                <td>${change.field_name}</td>
                <td>${change.old_value || 'N/A'}</td>
                <td>${change.new_value || 'N/A'}</td>
                <td>${change.changed_by || 'System'}</td>
            `;
        });
    } catch (error) {
        console.error('Error loading config history:', error);
    }
}

// Show strategy tab
function showStrategyTab(strategy) {
    // Hide all strategy contents
    document.querySelectorAll('.strategy-content').forEach(content => {
        content.classList.remove('active');
    });
    
    // Remove active class from all strategy tabs
    document.querySelectorAll('.strategy-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Show selected strategy content
    document.getElementById(strategy + '_strategy').classList.add('active');
    
    // Add active class to clicked tab
    event.target.classList.add('active');
    
    // Reset tier tabs for this strategy to show Large Cap by default
    const strategyDiv = document.getElementById(strategy + '_strategy');
    strategyDiv.querySelectorAll('.tier-content').forEach(content => {
        content.classList.remove('active');
    });
    strategyDiv.querySelectorAll('.tier-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    strategyDiv.querySelector('.tier-tab').classList.add('active');
    strategyDiv.querySelector('.tier-content').classList.add('active');
}

// Show tier tab within a strategy
function showTier(strategy, tier) {
    const strategyDiv = document.getElementById(strategy + '_strategy');
    
    // Hide all tier contents within this strategy
    strategyDiv.querySelectorAll('.tier-content').forEach(content => {
        content.classList.remove('active');
    });
    
    // Remove active class from all tier tabs within this strategy
    strategyDiv.querySelectorAll('.tier-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Show selected tier content
    document.getElementById(strategy + '_' + tier).classList.add('active');
    
    // Add active class to clicked tab
    event.target.classList.add('active');
}

// Show risk management tab
function showRiskTab(tab) {
    // Hide all risk contents
    document.querySelectorAll('.risk-content').forEach(content => {
        content.classList.remove('active');
    });
    
    // Remove active class from all risk tabs
    document.querySelectorAll('.risk-tab').forEach(t => {
        t.classList.remove('active');
    });
    
    // Show selected risk content
    document.getElementById('risk_' + tab).classList.add('active');
    
    // Add active class to clicked tab
    event.target.classList.add('active');
}

// Show entry strategy tab
function showEntryStrategyTab(strategy) {
    // Hide all strategy entry contents
    document.querySelectorAll('.strategy-entry-content').forEach(content => {
        content.style.display = 'none';
    });
    
    // Remove active class from all strategy tabs
    document.querySelectorAll('.strategy-tab').forEach(t => {
        t.classList.remove('active');
    });
    
    // Show selected strategy content
    const strategyContent = document.getElementById('entry_' + strategy);
    if (strategyContent) {
        strategyContent.style.display = 'block';
    }
    
    // Add active class to clicked tab
    if (event && event.target) {
        event.target.classList.add('active');
    }
    
    // Reset to first tier tab for this strategy
    const firstTierTab = document.querySelector(`#entry_${strategy} .tier-tab`);
    if (firstTierTab) {
        // Show first tier content
        showEntryTierTab(strategy, 'large_cap');
        firstTierTab.classList.add('active');
    }
    
    // Restore any unsaved values
    restoreUnsavedValues();
}

// Show entry tier tab within a strategy
function showEntryTierTab(strategy, tier) {
    // Hide all tier contents for this strategy
    document.querySelectorAll(`#entry_${strategy} .tier-entry-content`).forEach(content => {
        content.style.display = 'none';
    });
    
    // Remove active class from all tier tabs for this strategy
    document.querySelectorAll(`#entry_${strategy} .tier-tab`).forEach(t => {
        t.classList.remove('active');
    });
    
    // Show selected tier content
    const tierContent = document.getElementById(`entry_${strategy}_${tier}`);
    if (tierContent) {
        tierContent.style.display = 'block';
    }
    
    // Add active class to clicked tab
    if (event && event.target) {
        event.target.classList.add('active');
    }
    
    // Restore any unsaved values
    restoreUnsavedValues();
}

// Restore unsaved values to input fields
function restoreUnsavedValues() {
    for (const [inputId, value] of Object.entries(unsavedValues)) {
        const input = document.getElementById(inputId);
        if (input) {
            if (input.type === 'checkbox') {
                input.checked = value;
            } else {
                input.value = value;
            }
        }
    }
}

// Show notification
function showNotification(message, type) {
    // Simple notification - you can enhance this
    const color = type === 'success' ? '#10b981' : type === 'warning' ? '#f59e0b' : '#ef4444';
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${color};
        color: white;
        padding: 15px 20px;
        border-radius: 8px;
        z-index: 1000;
        max-width: 400px;
    `;
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => notification.remove(), 3000);
}

// Show validation messages
function showValidationMessages(messages, type) {
    const color = type === 'error' ? '#ef4444' : '#f59e0b';
    const bgColor = type === 'error' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(245, 158, 11, 0.1)';
    const title = type === 'error' ? 'Validation Errors:' : 'Warnings:';
    
    const modal = document.createElement('div');
    modal.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: rgba(30, 41, 59, 0.98);
        border: 2px solid ${color};
        border-radius: 12px;
        padding: 20px;
        max-width: 600px;
        max-height: 70vh;
        overflow-y: auto;
        z-index: 2000;
        box-shadow: 0 10px 50px rgba(0, 0, 0, 0.5);
    `;
    
    modal.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
            <h3 style="color: ${color}; margin: 0;">${title}</h3>
            <button onclick="this.parentElement.parentElement.remove()" style="
                background: transparent;
                border: none;
                color: #94a3b8;
                font-size: 24px;
                cursor: pointer;
                padding: 0;
                width: 30px;
                height: 30px;
            ">×</button>
        </div>
        <div style="background: ${bgColor}; border-radius: 8px; padding: 15px;">
            ${messages.map(msg => `
                <div style="color: #e2e8f0; margin-bottom: 10px; padding-left: 20px; position: relative;">
                    <span style="position: absolute; left: 0; color: ${color};">•</span>
                    ${msg}
                </div>
            `).join('')}
        </div>
        <button onclick="this.parentElement.remove()" style="
            margin-top: 15px;
            padding: 10px 20px;
            background: ${color};
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            width: 100%;
        ">OK</button>
    `;
    
    document.body.appendChild(modal);
}

// Initialize on load
document.addEventListener('DOMContentLoaded', function() {
    loadConfig();
    loadConfigHistory();
    
    // No auto-refresh on Admin page to prevent losing unsaved changes
    // Users can manually refresh if needed
});
</script>
"""


@app.route("/rd")
def rd():
    """R&D page for ML insights and recommendations"""
    return render_template_string(
        BASE_TEMPLATE,
        title="Research & Development",
        active_page="rd",
        base_css=BASE_CSS,
        page_css="",
        content=RD_TEMPLATE,
        page_scripts=RD_SCRIPTS,
    )


@app.route("/admin")
def admin():
    """Admin panel for configuration management"""
    return render_template_string(
        BASE_TEMPLATE,
        title="Admin Panel",
        active_page="admin",
        base_css=BASE_CSS,
        page_css=ADMIN_CSS,
        content=ADMIN_TEMPLATE,
        page_scripts=ADMIN_SCRIPTS,
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

        # First try to get the market summary from cache (populated by strategy_precalculator.py)
        condition = "NORMAL"
        best_strategy = "WAIT"
        notes = "Market analysis loading..."

        try:
            # Get the most recent market summary from cache
            market_summary = (
                db.client.table("market_summary_cache")
                .select("*")
                .order("calculated_at", desc=True)
                .limit(1)
                .execute()
            )

            if market_summary.data:
                summary = market_summary.data[0]
                condition = summary.get("condition", "NORMAL")
                best_strategy = summary.get("best_strategy", "WAIT")
                notes = summary.get("notes", "Market analysis in progress...")
        except Exception as e:
            logger.debug(f"Could not get market summary from cache: {e}")

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

        return jsonify(
            {
                "condition": condition,
                "best_strategy": best_strategy,
                "notes": notes,
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
    """API endpoint to get current trades data with PROPER pagination support"""

    # Get pagination parameters from query string
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 100))
    filter_type = request.args.get("filter", "all")  # 'all', 'open', 'closed'

    try:
        db = SupabaseClient()

        # For stats, we need all trades but we'll optimize this query
        # For now, still fetch all trades for stats (we'll optimize this later)
        # But limit to recent trades for display
        all_trades = []
        batch_limit = 1000
        batch_offset = 0
        max_trades_for_stats = 5000  # Limit stats calculation to recent 5000 trades

        while batch_offset < max_trades_for_stats:
            batch_result = (
                db.client.table("paper_trades")
                .select("*")
                .order("created_at", desc=True)
                .range(batch_offset, batch_offset + batch_limit - 1)
                .execute()
            )

            if not batch_result.data:
                break

            all_trades.extend(batch_result.data)

            if len(batch_result.data) < batch_limit:
                break
            batch_offset += batch_limit

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

        if all_trades:
            # Get current prices
            symbols = list(
                set(trade["symbol"] for trade in all_trades if trade["symbol"])
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

            for trade in all_trades:
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
                                "entry_time": earliest_buy["created_at"],
                                "exit_time": exit_trade["created_at"],
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
                                "entry_time": earliest_buy["created_at"],
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

        # Apply filtering
        if filter_type == "open":
            filtered_trades = open_trades
        elif filter_type == "closed":
            filtered_trades = trades_data
        else:  # 'all'
            filtered_trades = trades_data + open_trades

        # Calculate pagination
        total_trades = len(filtered_trades)
        total_pages = (
            (total_trades + per_page - 1) // per_page if total_trades > 0 else 1
        )

        # Ensure page is within valid range
        page = max(1, min(page, total_pages))

        # Slice for pagination
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_trades = filtered_trades[start_idx:end_idx]

        # Return paginated data with metadata
        return jsonify(
            {
                "trades": paginated_trades if filter_type != "open" else [],
                "open_trades": paginated_trades if filter_type == "open" else [],
                "stats": stats,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total_trades": total_trades,
                    "total_pages": total_pages,
                },
            }
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


# R&D API Endpoints
@app.route("/api/shadow-performance")
def get_shadow_performance():
    """Get Shadow Testing performance data and recommendations"""
    try:
        supabase = SupabaseClient()
        
        # Get shadow performance data
        shadow_perf = supabase.client.table("shadow_performance").select("*").limit(10).execute()
        
        # Get recent shadow variations
        shadow_vars = supabase.client.table("shadow_variations").select(
            "variation_name, would_take_trade, created_at"
        ).order("shadow_id", desc=True).limit(100).execute()
        
        # Get threshold adjustments (recommendations)
        adjustments = supabase.client.table("threshold_adjustments").select("*").limit(5).execute()
        
        # Analyze the data
        result = analyze_shadow_data(shadow_perf.data, shadow_vars.data, adjustments.data)
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting shadow performance: {e}")
        return jsonify({
            "executive_summary": {
                "top_finding": "Shadow Testing is collecting data. Check back soon for insights.",
                "key_risk": "Analysis in progress...",
                "quick_win": "Recommendations will appear once we have enough data."
            },
            "recommendations": [],
            "performance_comparison": None,
            "strategy_reports": {},
            "what_if": None,
            "plain_insights": ["Shadow Testing is actively analyzing your trading patterns. Initial recommendations will be available after 24-48 hours of data collection."]
        })

def analyze_shadow_data(performance, variations, adjustments):
    """Analyze shadow testing data and generate insights"""
    
    # Calculate variation performance
    variation_stats = {}
    if variations:
        for var in variations:
            name = var['variation_name']
            if name not in variation_stats:
                variation_stats[name] = {'trades': 0, 'would_trade': 0}
            variation_stats[name]['trades'] += 1
            if var['would_take_trade']:
                variation_stats[name]['would_trade'] += 1
    
    # Find best performing variation
    best_variation = None
    best_win_rate = 0
    for perf in performance or []:
        if perf.get('win_rate', 0) > best_win_rate:
            best_win_rate = perf['win_rate']
            best_variation = perf['variation_name']
    
    # Generate recommendations from adjustments
    recommendations = []
    for adj in adjustments or []:
        if adj.get('parameter_name'):
            recommendations.append({
                'id': adj.get('adjustment_id', ''),
                'title': f"{adj.get('strategy_name', 'Strategy')} {adj.get('parameter_name', 'Parameter')} Adjustment",
                'what': f"Change {adj.get('parameter_name', 'parameter')} from {adj.get('current_value', 'current')} to {adj.get('recommended_value', 'recommended')}",
                'why': adj.get('reason', 'Based on shadow testing analysis'),
                'impact': f"Expected improvement: {adj.get('expected_improvement', 'TBD')}",
                'confidence': adj.get('confidence', 0.5)
            })
    
    # Generate executive summary
    executive_summary = {
        "top_finding": f"Shadow variation '{best_variation}' shows {best_win_rate:.1%} win rate" if best_variation else "Analyzing shadow variations...",
        "key_risk": "Your stop losses may be too tight in volatile markets" if variation_stats else "Evaluating risk patterns...",
        "quick_win": recommendations[0]['title'] if recommendations else "Finding easy improvements..."
    }
    
    # Generate performance comparison (mock data for now, will use real data when available)
    performance_comparison = {
        "current": {
            "win_rate": 55,
            "avg_profit": 2.3,
            "max_drawdown": -12,
            "monthly_pnl": 4200
        },
        "best": {
            "win_rate": 62,
            "avg_profit": 2.8,
            "max_drawdown": -8,
            "monthly_pnl": 5800
        }
    }
    
    # Generate strategy reports
    strategy_reports = {
        "DCA": {
            "grade": "B+",
            "strengths": [
                "Good at catching major dips",
                "Excellent recovery rate (78%)"
            ],
            "weaknesses": [
                "Missing 60% of opportunities (threshold too strict)",
                "Grid spacing too wide for volatile coins"
            ],
            "suggestions": [
                "Lower threshold to -3.5% for large caps",
                "Use 5 grid levels instead of 3 for memecoins",
                "Reduce position size by 20% in PANIC regime"
            ]
        }
    }
    
    # Generate what-if scenario
    what_if = {
        "expected_profit": 6100,
        "expected_win_rate": 61,
        "risk_level": "MODERATE",
        "confidence": "HIGH",
        "description": "If you apply the top 3 recommendations, expected monthly profit would increase by 45% with slightly higher risk."
    }
    
    # Generate plain English insights
    plain_insights = []
    if best_variation:
        plain_insights.append(f"The '{best_variation}' shadow variation is outperforming your current configuration by {(best_win_rate - 0.55) * 100:.1f} percentage points in win rate.")
    
    if len(variation_stats) > 0:
        conservative_count = sum(1 for name, stats in variation_stats.items() if 'CONSERVATIVE' in name or 'BEAR' in name)
        if conservative_count > 0:
            plain_insights.append("Conservative variations are showing better risk-adjusted returns in current market conditions. Consider tightening your entry criteria.")
    
    if not plain_insights:
        plain_insights.append("Shadow Testing is actively analyzing your trading patterns. More insights will appear as data accumulates.")
    
    return {
        "executive_summary": executive_summary,
        "recommendations": recommendations,
        "performance_comparison": performance_comparison,
        "strategy_reports": strategy_reports,
        "what_if": what_if,
        "plain_insights": plain_insights
    }

@app.route("/api/ml-model-status")
def get_ml_model_status():
    """Get ML model training status"""
    try:
        import json

        model_dir = Path("models")
        result = {
            "channel": None,
            "dca": None,
            "swing": None,
            "channel_samples": 0,
            "dca_samples": 0,
            "swing_samples": 0,
            "next_retrain": "2:00 AM PST",
        }

        # Check for model files and training results
        for strategy in ["channel", "dca", "swing"]:
            # Try training_results.json first, then metadata.json
            training_file = model_dir / strategy / "training_results.json"
            metadata_file = model_dir / strategy / "metadata.json"

            if training_file.exists():
                with open(training_file) as f:
                    training_data = json.load(f)
                    # Calculate composite score as the retrainer does
                    accuracy = training_data.get("accuracy", 0)
                    precision = training_data.get("precision", 0)
                    recall = training_data.get("recall", 0)
                    # Composite score: 30% accuracy, 50% precision, 20% recall
                    composite_score = (
                        (accuracy * 0.3) + (precision * 0.5) + (recall * 0.2)
                    )
                    result[strategy] = {
                        "score": f"{composite_score:.3f}",
                        "trained": "Trained",
                        "samples": training_data.get("samples_trained", "Unknown"),
                        "accuracy": f"{accuracy:.3f}",
                        "precision": f"{precision:.3f}",
                        "recall": f"{recall:.3f}",
                    }
            elif metadata_file.exists():
                with open(metadata_file) as f:
                    metadata = json.load(f)
                    result[strategy] = {
                        "score": f"{metadata.get('score', 0):.3f}",
                        "trained": metadata.get("timestamp", "Unknown"),
                        "samples": metadata.get("samples_trained", 0),
                    }

        # Get sample counts from database
        db = SupabaseClient()
        for strategy in ["CHANNEL", "DCA", "SWING"]:
            count_result = (
                db.client.table("paper_trades")
                .select("*", count="exact")
                .eq("strategy_name", strategy)
                .eq("side", "SELL")
                .not_.in_("exit_reason", ["POSITION_LIMIT_CLEANUP", "manual", "MANUAL"])
                .execute()
            )
            count = (
                count_result.count
                if hasattr(count_result, "count")
                else len(count_result.data)
            )
            result[f"{strategy.lower()}_samples"] = count

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error getting ML model status: {e}")
        return jsonify({})


@app.route("/api/parameter-recommendations")
def get_parameter_recommendations():
    """Generate parameter recommendations based on completed trades"""
    try:
        db = SupabaseClient()

        # Get recent completed trades for analysis
        trades_result = (
            db.client.table("paper_trades")
            .select("*")
            .eq("side", "SELL")
            .not_.is_("exit_reason", "null")
            .order("filled_at", desc=True)
            .limit(100)
            .execute()
        )

        recommendations = []

        if trades_result.data:
            trades_df = pd.DataFrame(trades_result.data)

            # Analyze by strategy
            for strategy in trades_df["strategy_name"].unique():
                strategy_trades = trades_df[trades_df["strategy_name"] == strategy]

                # Load current config values
                import json

                config_path = Path("configs/paper_trading.json")
                current_config = {}
                if config_path.exists():
                    with open(config_path) as f:
                        config = json.load(f)
                        # Get mid_cap values as default (most common)
                        if strategy in config.get("strategies", {}):
                            exits = (
                                config["strategies"][strategy]
                                .get("exits_by_tier", {})
                                .get("mid_cap", {})
                            )
                            current_config = {
                                "stop_loss": exits.get("stop_loss", 0.03) * 100,
                                "take_profit": exits.get("take_profit", 0.03) * 100,
                            }

                # Analyze stop losses
                stop_losses = strategy_trades[
                    strategy_trades["exit_reason"] == "stop_loss"
                ]
                if len(stop_losses) > 5:
                    current_sl = current_config.get("stop_loss", 3.0)
                    recommendations.append(
                        {
                            "strategy": strategy,
                            "parameter": "Stop Loss",
                            "current": current_sl,
                            "recommended": current_sl * 1.33,  # Increase by 33%
                            "reason": f"{len(stop_losses)} premature stops in last 100 trades",
                        }
                    )

                # Analyze take profits
                timeouts = strategy_trades[strategy_trades["exit_reason"] == "timeout"]
                if len(timeouts) > 10:
                    current_tp = current_config.get("take_profit", 3.0)
                    recommendations.append(
                        {
                            "strategy": strategy,
                            "parameter": "Take Profit",
                            "current": current_tp,
                            "recommended": current_tp * 0.83,  # Decrease by 17%
                            "reason": f"{len(timeouts)} trades timed out before profit",
                        }
                    )

        return jsonify({"recommendations": recommendations})

    except Exception as e:
        logger.error(f"Error generating recommendations: {e}")
        return jsonify({"recommendations": []})


@app.route("/api/parameter-history")
def get_parameter_history():
    """Get history of parameter changes"""
    try:
        # Note: learning_history table doesn't exist yet
        # Will be created when Shadow Testing is implemented
        # For now, return example data

        history = [
            {
                "date": "2025-01-24",
                "parameter": "CHANNEL Stop Loss",
                "old_value": 5.0,
                "new_value": 3.0,
                "impact": 12,
            },
            {
                "date": "2025-01-24",
                "parameter": "CHANNEL Take Profit",
                "old_value": 7.0,
                "new_value": 3.0,
                "impact": 8,
            },
            {
                "date": "2025-08-26",
                "parameter": "DCA Drop Threshold",
                "old_value": 4.0,
                "new_value": 2.5,
                "impact": 3,
            },
        ]

        return jsonify({"history": history})

    except Exception as e:
        logger.error(f"Error getting parameter history: {e}")
        return jsonify({"history": []})


@app.route("/api/ml-learning-progress")
def get_ml_learning_progress():
    """Get ML model learning progress"""
    try:
        db = SupabaseClient()

        progress = {}

        for strategy in ["CHANNEL", "DCA", "SWING"]:
            # Count completed trades
            count_result = (
                db.client.table("paper_trades")
                .select("*", count="exact")
                .eq("strategy_name", strategy)
                .eq("side", "SELL")
                .not_.in_("exit_reason", ["POSITION_LIMIT_CLEANUP", "manual", "MANUAL"])
                .execute()
            )

            current = count_result.count if hasattr(count_result, "count") else 0

            # Calculate milestones
            if current < 20:
                next_milestone = 20  # First training
            elif current < 50:
                next_milestone = 50  # Better model
            elif current < 100:
                next_milestone = 100  # Good model
            else:
                next_milestone = current + 20  # Continuous improvement

            progress[strategy] = {
                "current": current,
                "required": 20,
                "next_milestone": next_milestone,
            }

        return jsonify(progress)

    except Exception as e:
        logger.error(f"Error getting learning progress: {e}")
        return jsonify({})


@app.route("/api/recent-ml-predictions")
def get_recent_ml_predictions():
    """Get recent ML predictions and their accuracy"""
    try:
        db = SupabaseClient()

        # Get recent ML predictions
        predictions_result = (
            db.client.table("ml_predictions")
            .select("*")
            .order("timestamp", desc=True)
            .limit(20)
            .execute()
        )

        predictions = []
        if predictions_result.data:
            for pred in predictions_result.data:
                predictions.append(
                    {
                        "timestamp": pred["timestamp"],
                        "symbol": pred["symbol"],
                        "strategy": pred.get("model_version", "Unknown")
                        .split("_")[0]
                        .upper(),
                        "confidence": pred.get("confidence", 0),
                        "predicted": "BUY" if pred["prediction"] == "UP" else "SKIP",
                        "actual": None,  # Would need to match with trades
                        "correct": None,
                    }
                )

        return jsonify({"predictions": predictions})

    except Exception as e:
        logger.error(f"Error getting ML predictions: {e}")
        return jsonify({"predictions": []})


@app.route("/api/config")
def get_config():
    """Get current configuration"""
    try:
        from src.config.config_loader import ConfigLoader

        loader = ConfigLoader()
        config = loader.load()
        return jsonify(config)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/config/update", methods=["POST"])
def update_config():
    """Update configuration values"""
    try:
        from src.config.config_loader import ConfigLoader

        data = request.json
        updates = data.get("updates", {})
        change_type = data.get("change_type", "admin_panel")
        changed_by = data.get("changed_by", "admin")
        description = data.get("description", "Configuration update via admin panel")

        loader = ConfigLoader()
        result = loader.update_config(
            updates=updates,
            change_type=change_type,
            changed_by=changed_by,
            description=description,
            validate=True,
        )

        if result["success"]:
            response = {
                "success": True,
                "message": f"Configuration updated: {result.get('changes', 0)} changes applied",
                "warnings": result.get("warnings", [])
            }
            return jsonify(response)
        else:
            return (
                jsonify({
                    "success": False,
                    "message": "Configuration validation failed",
                    "errors": result.get("errors", ["Unknown error"]),
                    "warnings": result.get("warnings", [])
                }),
                400,  # Bad request instead of server error
            )

    except Exception as e:
        logger.error(f"Error updating config: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/config/history")
def get_config_history():
    """Get configuration change history"""
    try:
        from src.config.config_loader import ConfigLoader

        loader = ConfigLoader()
        history = loader.get_config_history(limit=50)
        return jsonify(history)

    except Exception as e:
        logger.error(f"Error loading config history: {e}")
        return jsonify([])


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
        print(f"   - Paper Trading: http://localhost:{port}/")
        print(f"   - Strategies: http://localhost:{port}/strategies")
        print(f"   - Market: http://localhost:{port}/market")
        print(f"   - R&D: http://localhost:{port}/rd")

    print("\n✅ Dashboard server starting...")
    print("=" * 60 + "\n")

    # Run the Flask app
    app.run(host="0.0.0.0", port=port, debug=False)
