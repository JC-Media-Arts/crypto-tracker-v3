#!/usr/bin/env python3
"""
Enhanced multi-page trading dashboard with proper UI pagination
"""

from flask import Flask, render_template_string, jsonify, request
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
            <tr><td colspan="13" style="text-align: center;">Loading...</td></tr>
        </tbody>
    </table>
</div>

<!-- Closed Trades Table -->
<div class="table-container" id="closedTradesContainer" style="display: none;">
    <h3 style="margin-bottom: 15px;">Closed Trades</h3>
    <table>
        <thead>
            <tr>
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
            <tr><td colspan="8" style="text-align: center;">Loading...</td></tr>
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

async function fetchTrades(page = 1) {
    try {
        const response = await fetch(`/api/trades?page=${page}&per_page=100`);
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
            document.getElementById('tradeInfo').textContent =
                `Showing trades ${startTrade}-${endTrade} of ${data.pagination.total_trades} total`;

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

function updateTables(data) {
    const openTable = document.getElementById('openPositionsTableBody');
    const closedTable = document.getElementById('closedTradesTable');

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
        } else {
            openTable.innerHTML = '<tr><td colspan="13" style="text-align: center;">No open positions</td></tr>';
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
                '<tr><td colspan="8" style="text-align: center;">No closed trades on this page</td></tr>';
        }
        document.getElementById('closedTradesContainer').style.display = 'block';
    } else {
        document.getElementById('closedTradesContainer').style.display = 'none';
    }
}

function changePage(direction) {
    const newPage = currentPage + direction;
    if (newPage >= 1 && newPage <= totalPages) {
        fetchTrades(newPage);
    }
}

function goToPage() {
    const pageInput = document.getElementById('pageInput');
    const page = parseInt(pageInput.value);
    if (page >= 1 && page <= totalPages) {
        fetchTrades(page);
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
            fetchTrades(1);
        });
    });

    // Initial load
    fetchTrades(1);
    checkEngineStatus();

    // Set up refresh intervals
    setInterval(() => fetchTrades(currentPage), 10000); // Refresh current page every 10 seconds
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

        # Get pagination parameters
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 100))
        offset = (page - 1) * per_page

        # Get total count of trades for pagination
        count_result = (
            db.client.table("paper_trades").select("*", count="exact").execute()
        )
        total_trades = count_result.count if count_result else 0
        total_pages = (
            (total_trades + per_page - 1) // per_page if total_trades > 0 else 1
        )

        # Get trades for current page only
        page_result = (
            db.client.table("paper_trades")
            .select("*")
            .order("created_at", desc=True)
            .range(offset, offset + per_page - 1)
            .execute()
        )

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
                    "total_trades": total_trades,
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


# Add placeholder routes for other pages
@app.route("/strategies")
def strategies():
    return "<h1>Strategies Page - Coming Soon</h1>"


@app.route("/market")
def market():
    return "<h1>Market Page - Coming Soon</h1>"


@app.route("/rd")
def rd():
    return "<h1>R&D Page - Coming Soon</h1>"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
