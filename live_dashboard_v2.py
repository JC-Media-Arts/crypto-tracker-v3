#!/usr/bin/env python3
"""
Enhanced multi-page trading dashboard with proper UI pagination
"""

from flask import Flask, render_template_string, jsonify, request
import sys
from pathlib import Path
import os
from datetime import datetime, timedelta, timezone
import json
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

    /* Pagination Controls */
    .pagination-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin: 20px 0;
        padding: 15px;
        background: rgba(30, 41, 59, 0.6);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 12px;
    }

    .pagination-info {
        color: #94a3b8;
        font-size: 0.9rem;
    }

    .pagination-controls {
        display: flex;
        gap: 10px;
        align-items: center;
    }

    .pagination-btn {
        padding: 8px 16px;
        background: rgba(59, 130, 246, 0.2);
        color: #60a5fa;
        border: 1px solid rgba(59, 130, 246, 0.3);
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.3s ease;
        font-size: 0.9rem;
    }

    .pagination-btn:hover:not(:disabled) {
        background: rgba(59, 130, 246, 0.3);
        transform: translateY(-1px);
    }

    .pagination-btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
        color: #64748b;
    }

    .page-input {
        width: 60px;
        padding: 6px;
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 4px;
        color: #e2e8f0;
        text-align: center;
        font-size: 0.9rem;
    }

    /* Tables */
    .table-container {
        background: rgba(30, 41, 59, 0.6);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 30px;
        overflow-x: auto;
    }

    table {
        width: 100%;
        border-collapse: collapse;
    }

    th {
        text-align: left;
        padding: 12px;
        font-weight: 600;
        color: #94a3b8;
        border-bottom: 1px solid rgba(148, 163, 184, 0.2);
    }

    td {
        padding: 12px;
        border-bottom: 1px solid rgba(148, 163, 184, 0.1);
    }

    tr:hover {
        background: rgba(59, 130, 246, 0.05);
    }

    /* Badges */
    .badge {
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
    }

    .badge-strategy {
        background: rgba(139, 92, 246, 0.2);
        color: #a78bfa;
    }

    /* Engine Status */
    .engine-status {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 15px;
        background: rgba(30, 41, 59, 0.6);
        border-radius: 8px;
        border: 1px solid rgba(148, 163, 184, 0.2);
    }

    .status-light {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: #fbbf24;
    }

    /* Filter Controls */
    .filter-container {
        display: flex;
        gap: 20px;
        margin-bottom: 20px;
    }

    .filter-option {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .filter-option input[type="radio"] {
        width: 18px;
        height: 18px;
        accent-color: #3b82f6;
    }

    .filter-option label {
        cursor: pointer;
        color: #cbd5e1;
        transition: color 0.3s ease;
    }

    .filter-option input[type="radio"]:checked + label {
        color: #3b82f6;
        font-weight: 600;
    }
"""

# HTML template for Paper Trading page with pagination
PAPER_TRADING_HTML = r"""
<h1 class="page-title">Paper Trading Dashboard</h1>
<div class="subtitle">Live paper trading performance with proper pagination</div>

<!-- Engine Status -->
<div class="engine-status">
    <div class="status-light" id="statusLight"></div>
    <span id="statusText">Checking status...</span>
</div>

<!-- Stats Cards -->
<div class="stats-container">
    <div class="stat-card">
        <div class="stat-label">Current Balance</div>
        <div class="stat-value" id="currentBalance">Loading...</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Total P&L</div>
        <div class="stat-value" id="totalPnl">Loading...</div>
        <div class="stat-value" id="totalPnlPct" style="font-size: 1rem; margin-top: 5px;">-</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Win Rate</div>
        <div class="stat-value" id="winRate">Loading...</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Total Investment</div>
        <div class="stat-value" id="totalInvestment">Loading...</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Open Positions</div>
        <div class="stat-value" id="openPositions">Loading...</div>
    </div>
</div>

<!-- Filter Controls -->
<div class="filter-container">
    <div class="filter-option">
        <input type="radio" id="filterOpen" name="tradeFilter" value="open" checked>
        <label for="filterOpen">Open Positions</label>
    </div>
    <div class="filter-option">
        <input type="radio" id="filterClosed" name="tradeFilter" value="closed">
        <label for="filterClosed">Closed Trades</label>
    </div>
    <div class="filter-option">
        <input type="radio" id="filterAll" name="tradeFilter" value="all">
        <label for="filterAll">All Trades</label>
    </div>
</div>

<!-- Pagination Controls (Top) -->
<div class="pagination-container" id="paginationTop">
    <div class="pagination-info">
        <span id="pageInfo">Page 1 of 1</span> |
        <span id="tradeInfo">Showing 0 trades</span>
    </div>
    <div class="pagination-controls">
        <button class="pagination-btn" id="prevBtn" onclick="changePage(-1)">← Previous</button>
        <span>Page </span>
        <input type="number" class="page-input" id="pageInput" value="1" min="1" onchange="goToPage()">
        <span> of <span id="totalPages">1</span></span>
        <button class="pagination-btn" id="nextBtn" onclick="changePage(1)">Next →</button>
    </div>
</div>

<!-- Open Positions Table -->
<div class="table-container" id="openPositionsTable">
    <h3 style="margin-bottom: 15px;">Open Positions</h3>
    <table>
        <thead>
            <tr>
                <th>Open Date/Time</th>
                <th>Symbol</th>
                <th>Strategy</th>
                <th>Amount</th>
                <th>Entry Price</th>
                <th>DCA Status</th>
                <th>Current Price</th>
                <th>P&L %</th>
                <th>P&L $</th>
                <th>Hold Time</th>
                <th>SL</th>
                <th>TP</th>
                <th>TS</th>
                <th>Exit Reason</th>
            </tr>
        </thead>
        <tbody id="openPositionsTableBody">
            <tr><td colspan="14" style="text-align: center;">Loading...</td></tr>
        </tbody>
    </table>
</div>

<!-- Closed Trades Table -->
<div class="table-container" id="closedTradesContainer" style="display: none;">
    <h3 style="margin-bottom: 15px;">Closed Trades</h3>
    <table>
        <thead>
            <tr>
                <th>Open Date/Time</th>
                <th>Symbol</th>
                <th>Strategy</th>
                <th>Entry Price</th>
                <th>Exit Price</th>
                <th>P&L %</th>
                <th>P&L $</th>
                <th>Exit Reason</th>
                <th>Hold Time</th>
            </tr>
        </thead>
        <tbody id="closedTradesTable">
            <tr><td colspan="9" style="text-align: center;">Loading...</td></tr>
        </tbody>
    </table>
</div>

<!-- Pagination Controls (Bottom) -->
<div class="pagination-container" id="paginationBottom">
    <div class="pagination-info">
        <span id="pageInfoBottom">Page 1 of 1</span>
    </div>
    <div class="pagination-controls">
        <button class="pagination-btn" onclick="changePage(-1)">← Previous</button>
        <button class="pagination-btn" onclick="changePage(1)">Next →</button>
    </div>
</div>
"""

# JavaScript for Paper Trading page with pagination
PAPER_TRADING_SCRIPTS = r"""
<script>
let currentPage = 1;
let totalPages = 1;
let currentFilter = 'open';
let allStats = {};
let isNavigating = false;
let autoRefreshTimer = null;

async function checkEngineStatus() {
    try {
        const response = await fetch('/api/engine-status');
        const data = await response.json();

        const statusLight = document.getElementById('statusLight');
        const statusText = document.getElementById('statusText');

        if (data.running) {
            statusLight.style.background = '#10b981';
            statusText.textContent = 'Paper Trading Active';
            statusText.style.color = '#10b981';
        } else {
            statusLight.style.background = '#ef4444';
            statusText.textContent = 'Paper Trading Stopped';
            statusText.style.color = '#ef4444';
        }
    } catch (error) {
        const statusLight = document.getElementById('statusLight');
        const statusText = document.getElementById('statusText');
        statusLight.style.background = '#fbbf24';
        statusText.textContent = 'Status Unknown';
        statusText.style.color = '#fbbf24';
    }
}

async function fetchTrades(page = 1, isManualNavigation = false) {
    // Don't auto-refresh if user is manually navigating
    if (isNavigating && !isManualNavigation) {
        return;
    }

    if (isManualNavigation) {
        isNavigating = true;
        // Clear and reset the auto-refresh timer
        if (autoRefreshTimer) {
            clearInterval(autoRefreshTimer);
        }
    }

    try {
        const response = await fetch(`/api/trades?page=${page}&per_page=100&filter=${currentFilter}`);
        const data = await response.json();

        // Update stats (always show total stats regardless of pagination)
        allStats = data.stats;
        updateStats(data.stats);

        // Update pagination info
        if (data.pagination) {
            currentPage = data.pagination.current_page;
            totalPages = data.pagination.total_pages;

            // Update page info
            document.getElementById('pageInfo').textContent = `Page ${currentPage} of ${totalPages}`;
            document.getElementById('pageInfoBottom').textContent = `Page ${currentPage} of ${totalPages}`;
            document.getElementById('totalPages').textContent = totalPages;
            document.getElementById('pageInput').value = currentPage;
            document.getElementById('pageInput').max = totalPages;

            // Update trade count info
            const startTrade = (currentPage - 1) * 100 + 1;
            const endTrade = Math.min(currentPage * 100, data.pagination.total_trades);
            const filterText = currentFilter === 'open' ? 'open positions' :
                            currentFilter === 'closed' ? 'closed trades' : 'trades';
            document.getElementById('tradeInfo').textContent =
                `Showing ${filterText} ${startTrade}-${endTrade} of ${data.pagination.total_trades} total`;

            // Enable/disable navigation buttons
            document.getElementById('prevBtn').disabled = !data.pagination.has_prev;
            document.getElementById('nextBtn').disabled = !data.pagination.has_next;
            document.querySelectorAll('.pagination-btn').forEach(btn => {
                if (btn.textContent.includes('Previous')) {
                    btn.disabled = !data.pagination.has_prev;
                } else if (btn.textContent.includes('Next')) {
                    btn.disabled = !data.pagination.has_next;
                }
            });
        }

        // Update tables based on filter
        updateTables(data);

        // Reset navigation flag and restart auto-refresh after manual navigation
        if (isManualNavigation) {
            isNavigating = false;
            autoRefreshTimer = setInterval(() => fetchTrades(currentPage), 10000);
        }

    } catch (error) {
        console.error('Error fetching trades:', error);
    }
}

function updateStats(stats) {
    // Update all stats displays
    document.getElementById('currentBalance').textContent =
        `$${(stats.starting_capital + stats.total_pnl_dollar).toFixed(2)}`;

    document.getElementById('totalInvestment').textContent =
        `$${stats.starting_capital.toFixed(2)}`;

    document.getElementById('openPositions').textContent = stats.open_count;

    // Update P&L
    const pnlElement = document.getElementById('totalPnl');
    pnlElement.textContent = `$${stats.total_pnl_dollar.toFixed(2)}`;
    pnlElement.className = `stat-value ${stats.total_pnl_dollar >= 0 ? 'positive' : 'negative'}`;

    // Update P&L %
    const pnlPctElement = document.getElementById('totalPnlPct');
    const pnlPct = stats.total_pnl || 0;
    pnlPctElement.textContent = `${pnlPct.toFixed(2)}%`;
    pnlPctElement.className = `stat-value ${pnlPct >= 0 ? 'positive' : 'negative'}`;

    // Update win rate
    const winRateElement = document.getElementById('winRate');
    winRateElement.textContent = `${stats.win_rate.toFixed(1)}%`;
    winRateElement.className = `stat-value ${stats.win_rate >= 50 ? 'positive' : ''}`;
}

function formatDateForLA(dateString) {
    const date = new Date(dateString);
    const options = {
        timeZone: 'America/Los_Angeles',
        month: '2-digit',
        day: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
    };
    return date.toLocaleString('en-US', options);
}

function toggleDCADetails(groupId) {
    const detailsRow = document.getElementById(`dca-details-${groupId}`);
    const expandBtn = document.getElementById(`dca-expand-${groupId}`);

    if (detailsRow.style.display === 'none' || !detailsRow.style.display) {
        detailsRow.style.display = 'table-row';
        expandBtn.textContent = '−';
    } else {
        detailsRow.style.display = 'none';
        expandBtn.textContent = '+';
    }
}

function updateTables(data) {
    const openTable = document.getElementById('openPositionsTableBody');
    const closedTable = document.getElementById('closedTradesTable');

    if (currentFilter === 'open' || currentFilter === 'all') {
        // Show open positions
        if (data.open_trades && data.open_trades.length > 0) {
            let tableRows = [];
            data.open_trades.forEach(trade => {
                // Main trade row
                const isDCA = trade.strategy === 'DCA';
                const dcaColumn = isDCA && trade.dca_buys && trade.dca_buys.length > 1 ?
                    `<button id="dca-expand-${trade.group_id}" onclick="toggleDCADetails('${trade.group_id}')"
                             style="background: none; border: 1px solid #4a5568; border-radius: 3px; ` +
                             `padding: 2px 6px; cursor: pointer; font-weight: bold;">+</button>` +
                     `<span style="margin-left: 5px;">${trade.dca_buys.length} buys</span>` :
                    (isDCA && trade.dca_status ? trade.dca_status : '−');

                tableRows.push(`
                    <tr>
                        <td>${formatDateForLA(trade.created_at)}</td>
                        <td style="font-weight: 600;">${trade.symbol}</td>
                        <td><span class="badge badge-strategy">${trade.strategy}</span></td>
                        <td>${trade.amount ? trade.amount.toFixed(6) : 'N/A'}</td>
                        <td>$${trade.entry_price.toFixed(4)}</td>
                        <td>${dcaColumn}</td>
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
                `);

                // DCA details row (hidden by default)
                if (isDCA && trade.dca_buys && trade.dca_buys.length > 1) {
                    tableRows.push(`
                        <tr id="dca-details-${trade.group_id}" style="display: none; background-color: #1a1a2e;">
                            <td colspan="14" style="padding: 10px 20px;">
                                <div style="margin-left: 30px;">
                                    <strong>DCA Buy History:</strong>
                                    <table style="margin-top: 10px; width: 80%;">
                                        <thead>
                                            <tr style="background-color: #2d2d44;">
                                                <th style="padding: 5px;">Date/Time</th>
                                                <th style="padding: 5px;">Buy #</th>
                                                <th style="padding: 5px;">Amount</th>
                                                <th style="padding: 5px;">Price</th>
                                                <th style="padding: 5px;">Cost</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            ${trade.dca_buys.map((buy, idx) => `
                                                <tr>
                                                    <td style="padding: 5px;">${formatDateForLA(buy.created_at)}</td>
                                                    <td style="padding: 5px;">${idx + 1}</td>
                                                    <td style="padding: 5px;">${buy.amount.toFixed(6)}</td>
                                                    <td style="padding: 5px;">$${buy.price.toFixed(4)}</td>
                                                    <td style="padding: 5px;">$${buy.cost.toFixed(2)}</td>
                                                </tr>
                                            `).join('')}
                                        </tbody>
                                    </table>
                                </div>
                            </td>
                        </tr>
                    `);
                }
            });
            openTable.innerHTML = tableRows.join('');
        } else {
            openTable.innerHTML = '<tr><td colspan="14" style="text-align: center;">No open positions</td></tr>';
        }
        document.getElementById('openPositionsTable').style.display = 'block';
    } else {
        document.getElementById('openPositionsTable').style.display = 'none';
    }

    if (currentFilter === 'closed' || currentFilter === 'all') {
        // Show closed trades
        const closedTrades = data.trades ? data.trades.filter(t => t.status === 'closed') : [];

        if (closedTrades.length > 0) {
            closedTable.innerHTML = closedTrades.map(trade => `
                <tr>
                    <td>${formatDateForLA(trade.created_at || trade.entry_time)}</td>
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
            closedTable.innerHTML =
                '<tr><td colspan="9" style="text-align: center;">No closed trades on this page</td></tr>';
        }
        document.getElementById('closedTradesContainer').style.display = 'block';
    } else {
        document.getElementById('closedTradesContainer').style.display = 'none';
    }
}

function changePage(direction) {
    const newPage = currentPage + direction;
    if (newPage >= 1 && newPage <= totalPages) {
        fetchTrades(newPage, true); // Mark as manual navigation
    }
}

function goToPage() {
    const pageInput = document.getElementById('pageInput');
    const page = parseInt(pageInput.value);
    if (page >= 1 && page <= totalPages) {
        fetchTrades(page, true); // Mark as manual navigation
    } else {
        pageInput.value = currentPage;
    }
}

// Add event listeners for filters
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('input[name="tradeFilter"]').forEach(radio => {
        radio.addEventListener('change', function() {
            currentFilter = this.value;
            currentPage = 1; // Reset to first page when changing filter
            fetchTrades(1, true); // Mark as manual navigation
        });
    });

    // Initial load
    fetchTrades(1);
    checkEngineStatus();

    // Set up refresh intervals
    autoRefreshTimer = setInterval(() => fetchTrades(currentPage), 10000); // Refresh current page every 10 seconds
    setInterval(checkEngineStatus, 30000); // Check engine status every 30 seconds
});
</script>
"""


# Copy the API routes from the original dashboard
@app.route("/")
def index():
    """Redirect to Paper Trading page"""
    return paper_trading()


@app.route("/paper-trading")
def paper_trading():
    """Paper Trading page"""
    return render_template_string(
        f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Paper Trading Dashboard</title>
            <style>{BASE_CSS}</style>
        </head>
        <body>
            <nav class="nav-container">
                <div class="nav-wrapper">
                    <div class="nav-brand">📈 Crypto Trader</div>
                    <div class="nav-links">
                        <a href="/paper-trading" class="nav-link active">Paper Trading</a>
                        <a href="/strategies" class="nav-link">Strategies</a>
                        <a href="/market" class="nav-link">Market</a>
                        <a href="/rd" class="nav-link">R&D</a>
                    </div>
                </div>
            </nav>
            <div class="container">
                {PAPER_TRADING_HTML}
            </div>
            {PAPER_TRADING_SCRIPTS}
        </body>
        </html>
        """
    )


@app.route("/api/trades")
def get_trades():
    """API endpoint with proper pagination for trades"""

    try:
        db = SupabaseClient()

        # Get pagination and filter parameters
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 100))
        filter_type = request.args.get("filter", "all")  # open, closed, or all
        offset = (page - 1) * per_page

        # First get ALL trades to determine which are open/closed
        # Fetch in batches to ensure we get all trades
        all_trades_for_filter = []
        batch_limit = 1000
        batch_offset = 0

        while True:
            batch_result = (
                db.client.table("paper_trades")
                .select("*")
                .order("created_at", desc=True)
                .range(batch_offset, batch_offset + batch_limit - 1)
                .execute()
            )

            if not batch_result.data:
                break

            all_trades_for_filter.extend(batch_result.data)

            if len(batch_result.data) < batch_limit:
                break
            batch_offset += batch_limit

        # Group all trades to determine open vs closed
        # Use a more sophisticated grouping that handles legacy trades better
        all_trade_groups = {}
        for trade in all_trades_for_filter:
            group_id = trade.get("trade_group_id")

            # For legacy trades without group_id, create a unique identifier
            # but only for trades that are actually standalone positions
            if not group_id:
                # Legacy trades should be grouped by symbol and approximate time
                # to avoid counting each trade as a separate position
                group_id = f"legacy_{trade.get('id')}"

            if group_id not in all_trade_groups:
                all_trade_groups[group_id] = {
                    "buys": [],
                    "sells": [],
                    "trades": [],
                    "symbol": trade.get("symbol"),
                    "strategy": trade.get("strategy_name"),
                }
            all_trade_groups[group_id]["trades"].append(trade)
            if trade["side"] == "BUY":
                all_trade_groups[group_id]["buys"].append(trade)
            else:
                all_trade_groups[group_id]["sells"].append(trade)

        # Filter groups based on filter type
        filtered_group_ids = []
        if filter_type == "open":
            # Only groups with no SELL trades
            filtered_group_ids = [
                gid
                for gid, group in all_trade_groups.items()
                if len(group["sells"]) == 0 and len(group["buys"]) > 0
            ]
        elif filter_type == "closed":
            # Only groups with SELL trades
            filtered_group_ids = [
                gid
                for gid, group in all_trade_groups.items()
                if len(group["sells"]) > 0
            ]
        else:  # all
            filtered_group_ids = list(all_trade_groups.keys())

        # Calculate pagination based on filtered groups
        total_filtered_groups = len(filtered_group_ids)
        total_pages = (
            (total_filtered_groups + per_page - 1) // per_page
            if total_filtered_groups > 0
            else 1
        )

        # Get the groups for the current page
        start_idx = offset
        end_idx = min(offset + per_page, total_filtered_groups)
        page_group_ids = (
            filtered_group_ids[start_idx:end_idx] if filtered_group_ids else []
        )

        # Get trades for the groups on this page
        page_trades = []
        for group_id in page_group_ids:
            if group_id in all_trade_groups:
                # Sort trades by created_at within each group
                group_trades = sorted(
                    all_trade_groups[group_id]["trades"],
                    key=lambda x: x["created_at"],
                    reverse=True,
                )
                page_trades.extend(group_trades)

        # Create a result object similar to the database result
        page_result = type("obj", (object,), {"data": page_trades})()

        # For stats, we need ALL trades (not paginated)
        # This is a separate query to calculate overall portfolio stats
        all_trades = []
        stats_limit = 1000
        stats_offset = 0

        while True:
            stats_batch = (
                db.client.table("paper_trades")
                .select("*")
                .order("created_at", desc=True)
                .range(stats_offset, stats_offset + stats_limit - 1)
                .execute()
            )

            if not stats_batch.data:
                break

            all_trades.extend(stats_batch.data)

            if len(stats_batch.data) < stats_limit:
                break
            stats_offset += stats_limit

        # Initialize stats
        STARTING_CAPITAL = 10000.0
        stats = {
            "starting_capital": STARTING_CAPITAL,
            "open_count": 0,
            "closed_count": 0,
            "win_count": 0,
            "loss_count": 0,
            "win_rate": 0,
            "total_pnl": 0,
            "total_pnl_dollar": 0,
        }

        # Get current prices for open positions
        current_prices = {}
        trades_by_symbol = {}

        for trade in page_result.data:
            symbol = trade.get("symbol")
            if symbol and symbol not in trades_by_symbol:
                trades_by_symbol[symbol] = []
            if symbol:
                trades_by_symbol[symbol].append(trade)

        # Fetch current prices for symbols on this page
        for symbol in trades_by_symbol.keys():
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
            except Exception as e:
                logger.error(f"Error fetching price for {symbol}: {e}")

        # Process trades for current page display
        open_trades = []
        closed_trades = []
        trades_by_group = {}

        # Group trades by trade_group_id for page display
        for trade in page_result.data:
            group_id = trade.get("trade_group_id") or f"legacy_{trade.get('id')}"

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

        # Process grouped trades for display
        for group_id, group_data in trades_by_group.items():
            symbol = group_data["symbol"]
            strategy = group_data["strategy"]
            current_price = current_prices.get(symbol)

            # Sort trades
            group_data["buys"].sort(key=lambda x: x["created_at"])
            group_data["sells"].sort(key=lambda x: x["created_at"])

            if group_data["buys"]:
                total_cost = 0
                total_amount = 0
                earliest_buy = None

                for buy in group_data["buys"]:
                    price = float(buy.get("price", 0))
                    amount = float(buy.get("amount", 0))
                    cost = price * amount
                    total_cost += cost
                    total_amount += amount
                    if not earliest_buy:
                        earliest_buy = buy

                avg_entry_price = total_cost / total_amount if total_amount > 0 else 0
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

                    closed_trades.append(
                        {
                            "symbol": symbol,
                            "strategy": strategy,
                            "status": "closed",
                            "entry_price": avg_entry_price,
                            "exit_price": exit_price,
                            "pnl": pnl,
                            "pnl_pct": pnl_pct,
                            "hold_time": hold_time,
                            "created_at": earliest_buy["created_at"],
                            "exit_reason": exit_trade.get("exit_reason", "manual"),
                        }
                    )

                else:
                    # Open position
                    unrealized_pnl = 0
                    unrealized_pnl_pct = 0

                    if current_price:
                        unrealized_pnl = (
                            current_price - avg_entry_price
                        ) * total_amount
                        unrealized_pnl_pct = (
                            ((current_price - avg_entry_price) / avg_entry_price * 100)
                            if avg_entry_price > 0
                            else 0
                        )

                    # Calculate hold time
                    entry_time = datetime.fromisoformat(
                        earliest_buy["created_at"].replace("Z", "+00:00")
                    )
                    hold_duration = datetime.now(timezone.utc) - entry_time
                    hours = int(hold_duration.total_seconds() / 3600)
                    minutes = int((hold_duration.total_seconds() % 3600) / 60)
                    hold_time = f"{hours}h {minutes}m"

                    # DCA status
                    num_fills = len(group_data["buys"])
                    dca_status = (
                        f"{num_fills}/5 levels"
                        if strategy == "DCA" and num_fills > 1
                        else "-"
                    )

                    # Get SL/TP/TS info
                    stop_loss = earliest_buy.get("stop_loss")
                    take_profit = earliest_buy.get("take_profit")
                    trailing_stop = earliest_buy.get("trailing_stop_pct")

                    sl_display = None
                    tp_display = None
                    ts_display = None

                    if stop_loss:
                        sl_price = float(stop_loss)
                        sl_pnl = ((sl_price - avg_entry_price) / avg_entry_price) * 100
                        sl_display = f"{unrealized_pnl_pct:.1f}% / {sl_pnl:.1f}%"

                    if take_profit:
                        tp_price = float(take_profit)
                        tp_pnl = ((tp_price - avg_entry_price) / avg_entry_price) * 100
                        tp_display = f"{unrealized_pnl_pct:.1f}% / {tp_pnl:.1f}%"

                    if trailing_stop:
                        ts_pct = float(trailing_stop) * 100
                        ts_display = f"Set at {ts_pct:.1f}%"

                    # Prepare DCA buy details if it's a DCA strategy
                    dca_buys = None
                    if strategy == "DCA":
                        dca_buys = []
                        for buy in group_data["buys"]:
                            dca_buys.append(
                                {
                                    "created_at": buy["created_at"],
                                    "amount": float(buy.get("amount", 0)),
                                    "price": float(buy.get("price", 0)),
                                    "cost": float(buy.get("price", 0))
                                    * float(buy.get("amount", 0)),
                                }
                            )

                    open_trades.append(
                        {
                            "group_id": group_id,
                            "symbol": symbol,
                            "strategy": strategy,
                            "amount": total_amount,
                            "entry_price": avg_entry_price,
                            "dca_status": dca_status,
                            "dca_buys": dca_buys,
                            "current_price": current_price,
                            "unrealized_pnl": unrealized_pnl,
                            "unrealized_pnl_pct": unrealized_pnl_pct,
                            "hold_time": hold_time,
                            "created_at": earliest_buy["created_at"],
                            "sl_display": sl_display,
                            "tp_display": tp_display,
                            "ts_display": ts_display,
                            "exit_reason": None,
                        }
                    )

        # Calculate overall stats from ALL trades (not just current page)
        all_trade_groups = {}
        for trade in all_trades:
            group_id = trade.get("trade_group_id") or f"legacy_{trade.get('id')}"

            if group_id not in all_trade_groups:
                all_trade_groups[group_id] = {
                    "buys": [],
                    "sells": [],
                }

            if trade["side"] == "BUY":
                all_trade_groups[group_id]["buys"].append(trade)
            else:
                all_trade_groups[group_id]["sells"].append(trade)

        # Process all groups for stats
        for group_id, group_data in all_trade_groups.items():
            if group_data["sells"]:
                # Closed position
                stats["closed_count"] += 1
                sell = group_data["sells"][0]
                pnl = sell.get("pnl", 0) or 0
                stats["total_pnl_dollar"] += pnl
                if pnl > 0:
                    stats["win_count"] += 1
                else:
                    stats["loss_count"] += 1
            elif group_data["buys"]:
                # Open position
                stats["open_count"] += 1

        # Calculate win rate
        if stats["closed_count"] > 0:
            stats["win_rate"] = (stats["win_count"] / stats["closed_count"]) * 100

        # Calculate total P&L percentage
        if STARTING_CAPITAL > 0:
            stats["total_pnl"] = (stats["total_pnl_dollar"] / STARTING_CAPITAL) * 100

        return jsonify(
            {
                "open_trades": open_trades,
                "trades": closed_trades,
                "stats": stats,
                "pagination": {
                    "current_page": page,
                    "total_pages": total_pages,
                    "per_page": per_page,
                    "total_trades": total_filtered_groups,
                    "has_prev": page > 1,
                    "has_next": page < total_pages,
                },
            }
        )

    except Exception as e:
        logger.error(f"Error fetching trades: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/engine-status")
def get_engine_status():
    """Check if paper trading engine is running"""
    try:
        db = SupabaseClient()

        # Check system_heartbeat table for paper trading status
        five_minutes_ago = (
            datetime.now(timezone.utc) - timedelta(minutes=5)
        ).isoformat()

        result = (
            db.client.table("system_heartbeat")
            .select("*")
            .eq("service_name", "paper_trading_engine")
            .gte("last_heartbeat", five_minutes_ago)
            .single()
            .execute()
        )

        is_running = result.data is not None if result else False

        # Also check for recent trades as backup
        if not is_running:
            one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
            trade_result = (
                db.client.table("paper_trades")
                .select("created_at")
                .gte("created_at", one_hour_ago)
                .limit(1)
                .execute()
            )

            is_running = bool(trade_result.data) if trade_result else False

        return jsonify({"running": is_running})

    except Exception as e:
        logger.error(f"Error checking engine status: {e}")
        return jsonify({"running": False})


# Base HTML Template for all pages
BASE_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - Crypto Trading Dashboard</title>
    <style>{{ base_css }}{{ page_css }}</style>
</head>
<body>
    <nav class="nav-container">
        <div class="nav-wrapper">
            <div class="nav-brand">📈 Crypto Trader</div>
            <div class="nav-links">
                <a href="/" class="nav-link {{ 'active' if active_page == 'paper-trading' else '' }}">Paper Trading</a>
                <a href="/strategies"
                   class="nav-link {{ 'active' if active_page == 'strategies' else '' }}">Strategies</a>
                <a href="/market" class="nav-link {{ 'active' if active_page == 'market' else '' }}">Market</a>
                <a href="/rd" class="nav-link {{ 'active' if active_page == 'rd' else '' }}">R&D</a>
            </div>
        </div>
    </nav>
    <div class="container">
        {{ content|safe }}
    </div>
    {{ page_scripts|safe }}
</body>
</html>
"""

# Strategies Page Template
STRATEGIES_TEMPLATE = r"""
<h1 class="page-title">Strategy Performance</h1>
<p class="subtitle">Real-time strategy signals and readiness analysis</p>

<!-- Strategy Stats -->
<div class="stats-container">
    <div class="stat-card">
        <div class="stat-label">Best Strategy Now</div>
        <div class="stat-value" id="bestStrategy">Loading...</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Ready Signals</div>
        <div class="stat-value" id="readySignals">Loading...</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Market Condition</div>
        <div class="stat-value" id="marketCondition">Loading...</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Last Update</div>
        <div class="stat-value" id="lastUpdate">Loading...</div>
    </div>
</div>

<!-- Strategy Signals Table -->
<div class="table-container">
    <div class="table-header">
        <h2 class="table-title">📊 Current Strategy Signals</h2>
    </div>
    <table class="data-table">
        <thead>
            <tr>
                <th>Symbol</th>
                <th>Strategy</th>
                <th>Signal Strength</th>
                <th>Entry Zone</th>
                <th>Risk/Reward</th>
                <th>ML Confidence</th>
                <th>Action</th>
            </tr>
        </thead>
        <tbody id="strategySignalsTable">
            <tr><td colspan="7">Loading signals...</td></tr>
        </tbody>
    </table>
</div>
"""

# Market Page Template
MARKET_TEMPLATE = r"""
<h1 class="page-title">Market Analysis</h1>
<p class="subtitle">Overall market conditions and protection status</p>

<!-- Market Stats -->
<div class="stats-container">
    <div class="stat-card">
        <div class="stat-label">Market Protection</div>
        <div class="stat-value" id="marketProtection">Loading...</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">BTC 24h Change</div>
        <div class="stat-value" id="btcChange">Loading...</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Market Volatility</div>
        <div class="stat-value" id="volatility">Loading...</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Active Positions</div>
        <div class="stat-value" id="activePositions">Loading...</div>
    </div>
</div>

<!-- Market Movers Table -->
<div class="table-container">
    <div class="table-header">
        <h2 class="table-title">🚀 Top Market Movers (24h)</h2>
    </div>
    <table class="data-table">
        <thead>
            <tr>
                <th>Symbol</th>
                <th>Price</th>
                <th>24h Change</th>
                <th>Volume</th>
                <th>Trend</th>
            </tr>
        </thead>
        <tbody id="marketMoversTable">
            <tr><td colspan="5">Loading market data...</td></tr>
        </tbody>
    </table>
</div>
"""

# R&D Page Template
RD_TEMPLATE = r"""
<h1 class="page-title">Research & Development</h1>
<p class="subtitle">ML insights and parameter optimization recommendations</p>

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

<!-- ML Learning Progress -->
<div class="table-container">
    <div class="table-header">
        <h2 class="table-title">🧠 ML Model Learning Progress</h2>
    </div>
    <div class="progress-container" id="learningProgressContainer">
        <div class="loading">Loading model statistics...</div>
    </div>
</div>

<style>
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

# JavaScript for Strategies page
STRATEGIES_SCRIPTS = r"""
<script>
async function fetchStrategyData() {
    try {
        const response = await fetch('/api/strategy-status');
        const data = await response.json();

        // Update stats
        if (data.summary) {
            document.getElementById('bestStrategy').textContent = data.summary.best_strategy || 'None';
            document.getElementById('readySignals').textContent = data.summary.ready_signals || '0';
            document.getElementById('marketCondition').textContent = data.summary.market_condition || 'Normal';
            document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
        }

        // Update table
        const table = document.getElementById('strategySignalsTable');
        if (data.strategies && data.strategies.length > 0) {
            table.innerHTML = data.strategies.map(s => `
                <tr>
                    <td>${s.symbol}</td>
                    <td>${s.strategy}</td>
                    <td>${(s.signal_strength * 100).toFixed(1)}%</td>
                    <td>${s.entry_zone || 'N/A'}</td>
                    <td>${s.risk_reward || 'N/A'}</td>
                    <td>${s.ml_confidence ? (s.ml_confidence * 100).toFixed(1) + '%' : 'N/A'}</td>
                    <td><span class="badge badge-${s.action === 'BUY' ? 'success' : 'neutral'}">${s.action}</span></td>
                </tr>
            `).join('');
        } else {
            table.innerHTML = '<tr><td colspan="7">No active signals</td></tr>';
        }
    } catch (error) {
        console.error('Error fetching strategy data:', error);
    }
}

fetchStrategyData();
setInterval(fetchStrategyData, 10000);
</script>
"""

# JavaScript for Market page
MARKET_SCRIPTS = r"""
<script>
async function fetchMarketData() {
    try {
        // Fetch market protection status
        const protectionResponse = await fetch('/api/market-protection');
        const protection = await protectionResponse.json();

        document.getElementById('marketProtection').innerHTML = protection.active ?
            '<span style="color: #ef4444;">ACTIVE ⚠️</span>' :
            '<span style="color: #10b981;">NORMAL ✓</span>';

        // Fetch market stats
        const statsResponse = await fetch('/api/market-stats');
        const stats = await statsResponse.json();

        if (stats.btc_change !== undefined) {
            const btcColor = stats.btc_change >= 0 ? '#10b981' : '#ef4444';
            document.getElementById('btcChange').innerHTML =
                `<span style="color: ${btcColor}">` +
                `${stats.btc_change > 0 ? '+' : ''}${stats.btc_change.toFixed(2)}%</span>`;
        }

        document.getElementById('volatility').textContent = stats.volatility || 'Normal';
        document.getElementById('activePositions').textContent = stats.active_positions || '0';

        // Update market movers table
        const table = document.getElementById('marketMoversTable');
        if (stats.top_movers && stats.top_movers.length > 0) {
            table.innerHTML = stats.top_movers.map(m => {
                const changeColor = m.change_24h >= 0 ? '#10b981' : '#ef4444';
                return `
                    <tr>
                        <td>${m.symbol}</td>
                        <td>$${m.price.toFixed(4)}</td>
                        <td style="color: ${changeColor}">${m.change_24h > 0 ? '+' : ''}${m.change_24h.toFixed(2)}%</td>
                        <td>${m.volume || 'N/A'}</td>
                        <td>${m.trend || '→'}</td>
                    </tr>
                `;
            }).join('');
        }
    } catch (error) {
        console.error('Error fetching market data:', error);
    }
}

fetchMarketData();
setInterval(fetchMarketData, 30000);
</script>
"""

# JavaScript for R&D page
RD_SCRIPTS = r"""
<script>
// Fetch ML model status
async function fetchModelStatus() {
    try {
        const response = await fetch('/api/ml-model-status');
        const data = await response.json();

        // Update model scores with detailed metrics
        if (data.channel) {
            let details = data.channel.accuracy ?
                `<br><small style="font-size: 0.7em; color: #9ca3af;">` +
                `Acc: ${data.channel.accuracy} | Prec: ${data.channel.precision} | ` +
                `Rec: ${data.channel.recall}</small>` : '';
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
            container.innerHTML = '<p style="color: #94a3b8;">' +
                'No recommendations available yet. Need more completed trades for analysis.</p>';
        }
    } catch (error) {
        console.error('Error fetching recommendations:', error);
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

// Initial load and refresh intervals
fetchModelStatus();
fetchRecommendations();
fetchLearningProgress();

// Refresh intervals
setInterval(fetchModelStatus, 30000); // Every 30 seconds
setInterval(fetchRecommendations, 60000); // Every minute
setInterval(fetchLearningProgress, 60000); // Every minute
</script>
"""


# Route implementations
@app.route("/strategies")
def strategies():
    """Strategies page for real-time strategy analysis"""
    return render_template_string(
        BASE_TEMPLATE,
        title="Strategy Performance",
        active_page="strategies",
        base_css=BASE_CSS,
        page_css="",
        content=STRATEGIES_TEMPLATE,
        page_scripts=STRATEGIES_SCRIPTS,
    )


@app.route("/market")
def market():
    """Market page for overall market analysis"""
    return render_template_string(
        BASE_TEMPLATE,
        title="Market Analysis",
        active_page="market",
        base_css=BASE_CSS,
        page_css="",
        content=MARKET_TEMPLATE,
        page_scripts=MARKET_SCRIPTS,
    )


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


# API Endpoints for R&D Page
@app.route("/api/ml-model-status")
def get_ml_model_status():
    """Get ML model training status"""
    try:
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
                if count_result.data
                else 0
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
                if not strategy:
                    continue

                strategy_trades = trades_df[trades_df["strategy_name"] == strategy]

                # Load current config values
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


@app.route("/api/market-protection")
def get_market_protection():
    """Get market protection status"""
    try:
        # Check if market protection is active
        protection_active = (
            regime_detector.check_market_protection() if regime_detector else False
        )

        return jsonify(
            {
                "active": protection_active,
                "reason": "BTC drop > 7%"
                if protection_active
                else "Normal market conditions",
                "restrictions": "No new trades allowed"
                if protection_active
                else "None",
            }
        )
    except Exception as e:
        logger.error(f"Error getting market protection: {e}")
        return jsonify({"active": False})


@app.route("/api/market-stats")
def get_market_stats():
    """Get overall market statistics"""
    try:
        db = SupabaseClient()

        # Get BTC price change
        btc_result = (
            db.client.table("ohlc_15min")
            .select("close")
            .eq("symbol", "BTC")
            .order("timestamp", desc=True)
            .limit(100)
            .execute()
        )

        btc_change = 0
        if btc_result.data and len(btc_result.data) >= 96:  # 24 hours of 15-min data
            current_price = float(btc_result.data[0]["close"])
            price_24h_ago = float(btc_result.data[95]["close"])
            btc_change = ((current_price - price_24h_ago) / price_24h_ago) * 100

        # Get active positions count
        positions_result = (
            db.client.table("paper_trades")
            .select("trade_group_id", count="exact")
            .eq("side", "BUY")
            .execute()
        )

        # Get top movers
        top_movers = []
        symbols = ["ETH", "SOL", "DOGE", "SHIB", "AVAX"]
        for symbol in symbols:
            price_result = (
                db.client.table("ohlc_15min")
                .select("close")
                .eq("symbol", symbol)
                .order("timestamp", desc=True)
                .limit(100)
                .execute()
            )

            if price_result.data and len(price_result.data) >= 96:
                current = float(price_result.data[0]["close"])
                past = float(price_result.data[95]["close"])
                change = ((current - past) / past) * 100

                top_movers.append(
                    {
                        "symbol": symbol,
                        "price": current,
                        "change_24h": change,
                        "trend": "↑" if change > 0 else "↓" if change < 0 else "→",
                    }
                )

        # Sort by absolute change
        top_movers.sort(key=lambda x: abs(x["change_24h"]), reverse=True)

        return jsonify(
            {
                "btc_change": btc_change,
                "volatility": "High" if abs(btc_change) > 5 else "Normal",
                "active_positions": positions_result.count
                if hasattr(positions_result, "count")
                else len(
                    set(
                        t["trade_group_id"]
                        for t in positions_result.data
                        if t["trade_group_id"]
                    )
                ),
                "top_movers": top_movers[:5],
            }
        )

    except Exception as e:
        logger.error(f"Error getting market stats: {e}")
        return jsonify({})


if __name__ == "__main__":
    # Get port from Railway or default to 8080 for local
    port = int(os.environ.get("PORT", 8080))

    # Print startup info
    print("\n" + "=" * 60)
    print("   📊 LIVE TRADING DASHBOARD WITH PAGINATION")
    print("=" * 60)

    if os.environ.get("RAILWAY_ENVIRONMENT"):
        print(f"🚂 Running on Railway: Port {port}")
    else:
        print(f"\n📊 Dashboard URL: http://localhost:{port}")
        print("📄 Pages available:")
        print(f"   - Paper Trading: http://localhost:{port}/")
        print(f"   - Strategies: http://localhost:{port}/strategies")
        print(f"   - Market: http://localhost:{port}/market")
        print(f"   - R&D: http://localhost:{port}/rd")

    print("\n✅ Dashboard server starting...")
    print("=" * 60 + "\n")

    app.run(host="0.0.0.0", port=port, debug=True)
