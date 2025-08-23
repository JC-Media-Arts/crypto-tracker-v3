#!/usr/bin/env python3
"""
Live trading dashboard server that auto-updates
"""

from flask import Flask, render_template_string, jsonify
import pytz
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from src.data.supabase_client import SupabaseClient  # noqa: E402
from loguru import logger  # noqa: E402

app = Flask(__name__)

HTML_TEMPLATE = r"""  # noqa: E501
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Live Trading Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #e2e8f0;
            padding: 20px;
            min-height: 100vh;
        }

        .container {
            max-width: 1800px;
            margin: 0 auto;
            padding: 0 20px;
        }

        h1 {
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

        .refresh-indicator {
            position: fixed;
            top: 20px;
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

        .stats-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: rgba(30, 41, 59, 0.5);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(148, 163, 184, 0.1);
            border-radius: 12px;
            padding: 20px;
        }

        .stat-label {
            color: #94a3b8;
            font-size: 0.875rem;
            margin-bottom: 8px;
        }

        .stat-value {
            font-size: 1.875rem;
            font-weight: 700;
        }

        .table-wrapper {
            overflow-x: auto;
            margin: 20px 0;
            border-radius: 12px;
        }

        table {
            width: 100%;
            background: rgba(30, 41, 59, 0.5);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(148, 163, 184, 0.1);
            border-radius: 12px;
            overflow: hidden;
            border-collapse: separate;
            border-spacing: 0;
            min-width: 1500px;
        }

        thead {
            background: rgba(15, 23, 42, 0.8);
        }

        th {
            padding: 16px 12px;
            text-align: left;
            font-weight: 600;
            color: #cbd5e1;
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border-bottom: 1px solid rgba(148, 163, 184, 0.1);
            white-space: nowrap;
        }

        td {
            padding: 14px 12px;
            border-bottom: 1px solid rgba(148, 163, 184, 0.05);
            font-size: 0.95rem;
            white-space: nowrap;
        }

        /* Allow wrapping for specific columns that might have longer content */
        td:nth-child(14) { /* Exit Reason - now column 14 after removing expand column */
            white-space: normal;
            max-width: 150px;
        }

        tr:hover {
            background: rgba(59, 130, 246, 0.05);
        }

        .status-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 0 8px currentColor;
        }

        .pnl-positive { color: #22c55e; font-weight: 600; }
        .pnl-negative { color: #ef4444; font-weight: 600; }
        .pnl-even { color: #94a3b8; font-weight: 600; }

        .status-open {
            background: rgba(59, 130, 246, 0.2);
            color: #60a5fa;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.875rem;
            font-weight: 600;
        }

        .status-closed {
            background: rgba(107, 114, 128, 0.2);
            color: #9ca3af;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.875rem;
            font-weight: 600;
        }

        .loading {
            opacity: 0.5;
            transition: opacity 0.3s;
        }

        .strategy-name {
            background: rgba(139, 92, 246, 0.2);
            color: #a78bfa;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.875rem;
            font-weight: 600;
        }

        .limit-tracking {
            font-size: 0.875rem;
            color: #cbd5e1;
            font-family: 'Courier New', monospace;
        }

        .strategies-section {
            margin-top: 60px;
            padding-top: 40px;
            border-top: 1px solid rgba(148, 163, 184, 0.1);
        }

        .strategies-section h2 {
            font-size: 1.875rem;
            font-weight: 700;
            margin-bottom: 30px;
            background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .strategies-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 24px;
        }

        .strategy-card {
            background: rgba(30, 41, 59, 0.5);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(148, 163, 184, 0.1);
            border-radius: 12px;
            padding: 24px;
            transition: all 0.3s ease;
        }

        .strategy-card:hover {
            border-color: rgba(139, 92, 246, 0.3);
            box-shadow: 0 4px 20px rgba(139, 92, 246, 0.1);
        }

        .strategy-card h3 {
            font-size: 1.25rem;
            font-weight: 700;
            color: #f1f5f9;
            margin-bottom: 16px;
        }

        .strategy-card ul {
            list-style: none;
            padding: 0;
            margin: 0;
        }

        .strategy-card li {
            color: #cbd5e1;
            font-size: 0.9rem;
            line-height: 1.6;
            margin-bottom: 12px;
            padding-left: 20px;
            position: relative;
        }

        .strategy-card li:before {
            content: "•";
            color: #60a5fa;
            font-weight: bold;
            position: absolute;
            left: 0;
        }

        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .status-card {
            background: rgba(30, 41, 59, 0.5);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(148, 163, 184, 0.1);
            border-radius: 12px;
            padding: 20px;
        }

        .status-card h3 {
            font-size: 1.25rem;
            font-weight: 700;
            color: #f1f5f9;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .threshold-list {
            background: rgba(15, 23, 42, 0.5);
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 15px;
        }

        .threshold-item {
            display: flex;
            justify-content: space-between;
            padding: 4px 0;
            color: #cbd5e1;
            font-size: 0.875rem;
        }

        .threshold-label {
            color: #94a3b8;
        }

        .threshold-value {
            color: #60a5fa;
            font-weight: 600;
        }

        .candidate-list {
            margin-top: 15px;
        }

        .candidate-item {
            background: rgba(15, 23, 42, 0.3);
            border-radius: 8px;
            padding: 10px;
            margin-bottom: 8px;
            border-left: 3px solid transparent;
        }

        .candidate-item.ready {
            border-left-color: #22c55e;
        }

        .candidate-item.waiting {
            border-left-color: #f59e0b;
        }

        .candidate-item.neutral {
            border-left-color: #6b7280;
        }

        /* DCA Visualization Styles */
        .dca-status {
            font-family: 'Courier New', monospace;
            color: #cbd5e1;
        }

        .expand-btn {
            background: rgba(59, 130, 246, 0.2);
            color: #60a5fa;
            border: none;
            padding: 2px 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.875rem;
        }

        .expand-btn:hover {
            background: rgba(59, 130, 246, 0.3);
        }

        .dca-details {
            background: rgba(15, 23, 42, 0.3);
            padding: 15px;
            border-radius: 8px;
            margin-top: 10px;
            display: none;
        }

        .dca-details.expanded {
            display: block;
        }

        .dca-grid-level {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid rgba(148, 163, 184, 0.1);
            font-size: 0.875rem;
        }

        .dca-grid-level.filled {
            color: #22c55e;
        }

        .dca-grid-level.pending {
            color: #94a3b8;
            opacity: 0.7;
        }

        .dca-summary {
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid rgba(148, 163, 184, 0.2);
            font-size: 0.875rem;
        }

        .dca-summary-item {
            display: flex;
            justify-content: space-between;
            padding: 4px 0;
        }

        .avg-price {
            color: #60a5fa;
            font-style: italic;
        }

        .candidate-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 5px;
        }

        .candidate-symbol {
            font-weight: 700;
            color: #f1f5f9;
        }

        .candidate-status {
            font-size: 0.75rem;
            padding: 2px 8px;
            border-radius: 12px;
            font-weight: 600;
        }

        .candidate-status.ready {
            background: rgba(34, 197, 94, 0.2);
            color: #22c55e;
        }

        .candidate-status.waiting {
            background: rgba(245, 158, 11, 0.2);
            color: #f59e0b;
        }

        .candidate-status.buy-zone {
            background: rgba(34, 197, 94, 0.2);
            color: #22c55e;
        }

        .candidate-status.sell-zone {
            background: rgba(239, 68, 68, 0.2);
            color: #ef4444;
        }

        .candidate-status.neutral {
            background: rgba(107, 114, 128, 0.2);
            color: #9ca3af;
        }

        .candidate-details {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
            font-size: 0.875rem;
            color: #94a3b8;
        }

        .candidate-detail {
            display: flex;
            justify-content: space-between;
        }

        .candidate-needs {
            margin-top: 8px;
            padding-top: 8px;
            border-top: 1px solid rgba(148, 163, 184, 0.1);
            color: #fbbf24;
            font-size: 0.875rem;
            font-weight: 500;
        }

        .market-summary {
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(139, 92, 246, 0.1) 100%);
            border: 1px solid rgba(59, 130, 246, 0.2);
            border-radius: 12px;
            padding: 20px;
            margin-top: 20px;
        }

        .market-summary h3 {
            color: #60a5fa;
            margin-bottom: 10px;
        }

        .market-condition {
            font-size: 1.5rem;
            font-weight: 700;
            color: #f1f5f9;
            margin-bottom: 5px;
        }

        .market-notes {
            color: #cbd5e1;
            font-size: 0.9rem;
        }
    </style>
</head>
<body>
    <div class="refresh-indicator" id="refresh-indicator">
        🔄 Live Updates: <span id="countdown">60</span>s
        <span style="margin-left: 20px; display: inline-flex; align-items: center; gap: 8px;">
            <span>Paper Trading:</span>
            <span id="engine-indicator" style="width: 12px; height: 12px; border-radius: 50%; background: #6b7280; display: inline-block; box-shadow: 0 0 8px currentColor;"></span>
            <span id="engine-text" style="font-size: 0.875rem;">Checking...</span>
        </span>
    </div>

    <div class="container">
        <h1>Live Trading Dashboard</h1>
        <p class="subtitle" id="last-updated">Loading...</p>

        <div class="stats-container">
            <div class="stat-card">
                <div class="stat-label">Trades Open</div>
                <div class="stat-value" style="color: #60a5fa;" id="open-positions">0/50</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Closed Trades</div>
                <div class="stat-value" id="closed-count">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Win Rate</div>
                <div class="stat-value" id="win-rate">0%</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Unrealized P&L</div>
                <div class="stat-value" id="unrealized-pnl">0.00% / $0.00</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Total P&L</div>
                <div class="stat-value" id="total-pnl">0.00% / $0.00</div>
            </div>
        </div>

        <div class="table-wrapper">
        <table id="trades-table">
            <thead>
                <tr>
                    <th style="width: 30px;"></th>
                    <th>Symbol</th>
                    <th>Strategy</th>
                    <th>Amount</th>
                    <th>Entry Price</th>
                    <th>DCA Status</th>
                    <th>Current Price</th>
                    <th>Exit Price</th>
                    <th>P&L %</th>
                    <th>P&L $</th>
                    <th>Status</th>
                    <th>Duration</th>
                    <th>SL</th>
                    <th>TP</th>
                    <th>TS</th>
                    <th>Exit Reason</th>
                </tr>
            </thead>
            <tbody id="trades-body">
                <tr><td colspan="14" style="text-align: center;">Loading trades...</td></tr>
            </tbody>
        </table>
        </div>

        <div class="strategies-section">
            <h2>📈 Market Analysis</h2>
            <div id="market-analysis">
                <p style="text-align: center; color: #94a3b8;">Loading market analysis...</p>
            </div>
        </div>

        <div class="strategies-section">
            <h2>🎯 Strategy Status Monitor</h2>
            <div id="strategy-status">
                <p style="text-align: center; color: #94a3b8;">Loading strategy status...</p>
            </div>
        </div>

        <div class="strategies-section">
            <h2>📚 Trading Strategies Guide</h2>
            <div class="strategies-grid">
                <div class="strategy-card">
                    <h3>📊 CHANNEL</h3>
                    <ul>
                        <li>Identifies price channels formed by parallel support and resistance levels</li>
                        <li>Enters when price breaks out of the channel with momentum</li>
                        <li>Uses ML model to predict optimal entry points and hold duration</li>
                        <li>Best for: Trending markets with clear directional moves</li>
                        <li>Risk management: Stop loss below channel support, take profit at predicted targets</li>
                    </ul>
                </div>
                <div class="strategy-card">
                    <h3>🎢 SWING</h3>
                    <ul>
                        <li>Captures medium-term price swings (2-10 days typically)</li>
                        <li>Uses technical indicators to identify oversold/overbought conditions</li>
                        <li>ML-enhanced entry/exit timing based on historical patterns</li>
                        <li>Best for: Volatile markets with regular oscillations</li>
                        <li>Risk management: Dynamic stop loss based on volatility, trailing stops on profits</li>
                    </ul>
                </div>
                <div class="strategy-card">
                    <h3>💰 DCA</h3>
                    <ul>
                        <li>Systematically accumulates positions during market dips</li>
                        <li>Triggers when price drops below moving averages or support levels</li>
                        <li>Reduces average entry price by buying more as price declines</li>
                        <li>Best for: Long-term accumulation in quality assets</li>
                        <li>Risk management: Position sizing limits, maximum allocation per symbol</li>
                    </ul>
                </div>
            </div>
        </div>
    </div>

    <script>
        let countdown = 10; // Update every 10 seconds

        async function checkEngineStatus() {
            try {
                const response = await fetch('/api/engine-status');
                const data = await response.json();
                const indicator = document.getElementById('engine-indicator');
                const text = document.getElementById('engine-text');

                if (data.running) {
                    indicator.style.background = '#22c55e';
                    indicator.style.boxShadow = '0 0 8px #22c55e';
                    text.textContent = 'Running';
                    text.style.color = '#22c55e';
                } else {
                    indicator.style.background = '#ef4444';
                    indicator.style.boxShadow = '0 0 8px #ef4444';
                    text.textContent = 'Stopped';
                    text.style.color = '#ef4444';
                }
            } catch (error) {
                console.error('Error checking engine status:', error);
                const indicator = document.getElementById('engine-indicator');
                const text = document.getElementById('engine-text');
                indicator.style.background = '#f59e0b';
                indicator.style.boxShadow = '0 0 8px #f59e0b';
                text.textContent = 'Unknown';
                text.style.color = '#f59e0b';
            }
        }

        async function updateStrategyStatus() {
            try {
                const response = await fetch('/api/strategy-status');
                const data = await response.json();

                let html = '<div class="status-grid">';

                // Display each strategy
                ['swing', 'channel', 'dca'].forEach(key => {
                    const strategy = data[key];
                    const icon = key === 'swing' ? '🎢' : key === 'channel' ? '📊' : '💰';

                    html += `
                        <div class="status-card">
                            <h3>${icon} ${strategy.name} Strategy</h3>

                            <div class="threshold-list">
                                <h4 style="color: #94a3b8; font-size: 0.875rem; margin-bottom: 8px;">Current Thresholds:</h4>
                    `;

                    // Display thresholds
                    Object.entries(strategy.thresholds).forEach(([label, value]) => {
                        const formattedLabel = label.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                        html += `
                            <div class="threshold-item">
                                <span class="threshold-label">${formattedLabel}:</span>
                                <span class="threshold-value">${value}</span>
                            </div>
                        `;
                    });

                    html += '</div><div class="candidate-list">';
                    html += '<h4 style="color: #94a3b8; font-size: 0.875rem; margin-bottom: 8px;">Top 5 by Readiness Score:</h4>';

                    // Display candidates (already sorted by readiness from API)
                    strategy.candidates.forEach(candidate => {
                        // Determine status class based on readiness score
                        const readiness = candidate.readiness;
                        const statusClass = readiness >= 80 ? 'ready' :
                                          readiness >= 60 ? 'close' :
                                          readiness >= 30 ? 'neutral' : 'waiting';

                        const itemClass = readiness >= 80 ? 'ready' :
                                        readiness >= 60 ? 'close' : 'waiting';

                        // Create readiness bar visual
                        const readinessColor = readiness >= 80 ? '#22c55e' :
                                              readiness >= 60 ? '#f59e0b' :
                                              readiness >= 30 ? '#3b82f6' : '#6b7280';

                        html += `
                            <div class="candidate-item ${itemClass}">
                                <div class="candidate-header">
                                    <span class="candidate-symbol">${candidate.symbol}</span>
                                    <span class="candidate-status ${statusClass}">${candidate.status}</span>
                                </div>

                                <!-- Readiness Score Bar -->
                                <div style="margin: 8px 0;">
                                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                                        <span style="color: #94a3b8; font-size: 0.75rem;">Readiness</span>
                                        <span style="color: ${readinessColor}; font-weight: 600;">${readiness.toFixed(0)}%</span>
                                    </div>
                                    <div style="background: rgba(148, 163, 184, 0.1); border-radius: 4px; height: 6px; overflow: hidden;">
                                        <div style="background: ${readinessColor}; height: 100%; width: ${readiness}%; transition: width 0.3s;"></div>
                                    </div>
                                </div>

                                <div class="candidate-details">
                                    <div class="candidate-detail">
                                        <span>Price:</span>
                                        <span style="color: #cbd5e1;">${candidate.current_price}</span>
                                    </div>
                                    <div class="candidate-detail">
                                        <span>Details:</span>
                                        <span style="color: #94a3b8; font-size: 0.85rem;">${candidate.details}</span>
                                    </div>
                                </div>
                            </div>
                        `;
                    });

                    html += '</div></div>';
                });

                html += '</div>';

                document.getElementById('strategy-status').innerHTML = html;

                // Update market analysis section
                if (data.market_summary) {
                    const marketHtml = `
                        <div class="market-summary">
                            <div class="market-condition">${data.market_summary.condition}</div>
                            <div class="market-notes">
                                Best Strategy: <strong style="color: #60a5fa;">${data.market_summary.best_strategy}</strong><br>
                                ${data.market_summary.notes}
                            </div>
                        </div>
                    `;
                    document.getElementById('market-analysis').innerHTML = marketHtml;
                }

            } catch (error) {
                console.error('Error updating strategy status:', error);
                document.getElementById('strategy-status').innerHTML =
                    '<p style="color: #ef4444; text-align: center;">Error loading strategy status</p>';
            }
        }

        async function fetchTrades() {
            const indicator = document.getElementById('refresh-indicator');
            indicator.classList.add('updating');

            try {
                const response = await fetch('/api/trades');
                const data = await response.json();

                // Update last updated time
                document.getElementById('last-updated').textContent =
                    'Last updated: ' + data.timestamp;

                // Update stats
                document.getElementById('open-positions').textContent = data.stats.open_count + '/50';
                document.getElementById('closed-count').textContent = data.stats.closed_count;
                document.getElementById('win-rate').textContent = data.stats.win_rate.toFixed(1) + '%';

                // Format Unrealized P&L with both % and $
                const unrealizedSign = data.stats.unrealized_pnl_dollar >= 0 ? '+' : '';
                document.getElementById('unrealized-pnl').textContent =
                    data.stats.unrealized_pnl.toFixed(2) + '% / ' +
                    unrealizedSign + '$' + Math.abs(data.stats.unrealized_pnl_dollar).toFixed(2);

                // Format Total P&L with both % and $
                const totalSign = data.stats.total_pnl_dollar >= 0 ? '+' : '';
                document.getElementById('total-pnl').textContent =
                    data.stats.total_pnl.toFixed(2) + '% / ' +
                    totalSign + '$' + Math.abs(data.stats.total_pnl_dollar).toFixed(2);

                // Color code win rate, unrealized PnL and total PnL
                const winRateEl = document.getElementById('win-rate');
                winRateEl.style.color = data.stats.win_rate >= 50 ? '#22c55e' : '#ef4444';

                const unrealizedPnlEl = document.getElementById('unrealized-pnl');
                unrealizedPnlEl.style.color = data.stats.unrealized_pnl_dollar >= 0 ? '#22c55e' : '#ef4444';

                const totalPnlEl = document.getElementById('total-pnl');
                totalPnlEl.style.color = data.stats.total_pnl_dollar >= 0 ? '#22c55e' : '#ef4444';

                // Update trades table
                const tbody = document.getElementById('trades-body');
                tbody.innerHTML = '';

                data.trades.forEach(trade => {
                    const row = tbody.insertRow();

                    // Status dot
                    const dotCell = row.insertCell();
                    const dot = document.createElement('span');
                    dot.className = 'status-dot';
                    dot.style.backgroundColor = trade.dot_color;
                    dotCell.appendChild(dot);

                    // Symbol
                    row.insertCell().textContent = trade.symbol;

                    // Strategy
                    const strategyCell = row.insertCell();
                    const strategySpan = document.createElement('span');
                    strategySpan.textContent = trade.strategy_name || 'N/A';
                    strategySpan.className = 'strategy-name';
                    strategyCell.appendChild(strategySpan);

                    // Amount (Position Size)
                    row.insertCell().textContent = '$' + (trade.position_size || 50).toFixed(2);

                    // Entry Price (with avg indicator for DCA)
                    const entryPriceCell = row.insertCell();
                    if (trade.strategy_name === 'DCA' && trade.dca_fills > 1) {
                        entryPriceCell.innerHTML = '$' + trade.entry_price.toFixed(4) + ' <span class="avg-price">(avg)</span>';
                    } else {
                        entryPriceCell.textContent = '$' + trade.entry_price.toFixed(4);
                    }

                    // DCA Status (with expand button if applicable)
                    const dcaStatusCell = row.insertCell();
                    if (trade.strategy_name === 'DCA') {
                        const dcaStatusContainer = document.createElement('div');
                        dcaStatusContainer.style.display = 'flex';
                        dcaStatusContainer.style.alignItems = 'center';
                        dcaStatusContainer.style.gap = '8px';

                        const dcaStatus = document.createElement('span');
                        dcaStatus.className = 'dca-status';
                        dcaStatus.textContent = (trade.dca_fills || 1) + '/5 levels';
                        dcaStatusContainer.appendChild(dcaStatus);

                        // Add expand button for open DCA trades
                        if (trade.status === 'open') {
                            const expandBtn = document.createElement('button');
                            expandBtn.className = 'expand-btn';
                            expandBtn.textContent = '+';
                            expandBtn.onclick = function() {
                                toggleDCADetails(this, trade);
                            };
                            dcaStatusContainer.appendChild(expandBtn);
                        }

                        dcaStatusCell.appendChild(dcaStatusContainer);
                    } else {
                        dcaStatusCell.textContent = '—';
                    }

                    // Current Price
                    row.insertCell().textContent = trade.current_price ?
                        '$' + trade.current_price.toFixed(4) : '—';

                    // Exit Price
                    row.insertCell().textContent = trade.exit_price ?
                        '$' + trade.exit_price.toFixed(4) : '—';

                    // P&L %
                    const pnlCell = row.insertCell();
                    const pnlSpan = document.createElement('span');
                    pnlSpan.textContent = trade.pnl_pct.toFixed(2) + '%';
                    pnlSpan.className = trade.pnl_pct > 0.1 ? 'pnl-positive' :
                                       trade.pnl_pct < -0.1 ? 'pnl-negative' : 'pnl-even';
                    pnlCell.appendChild(pnlSpan);

                    // P&L $ (Dollar amount)
                    const pnlDollarCell = row.insertCell();
                    const pnlDollar = (trade.position_size || 50) * (trade.pnl_pct / 100);
                    const pnlDollarSpan = document.createElement('span');
                    pnlDollarSpan.textContent = (pnlDollar >= 0 ? '+$' : '-$') + Math.abs(pnlDollar).toFixed(2);
                    pnlDollarSpan.className = pnlDollar > 0.1 ? 'pnl-positive' :
                                             pnlDollar < -0.1 ? 'pnl-negative' : 'pnl-even';
                    pnlDollarCell.appendChild(pnlDollarSpan);

                    // Status
                    const statusCell = row.insertCell();
                    const statusSpan = document.createElement('span');
                    statusSpan.textContent = trade.status.toUpperCase();
                    statusSpan.className = 'status-' + trade.status;
                    statusCell.appendChild(statusSpan);

                    // Duration
                    row.insertCell().textContent = trade.duration;

                    // SL
                    row.insertCell().innerHTML = trade.sl_display || '<span style="color: #6b7280;">Not Set</span>';

                    // TP
                    row.insertCell().innerHTML = trade.tp_display || '<span style="color: #6b7280;">Not Set</span>';

                    // TS
                    row.insertCell().innerHTML = trade.ts_display || '<span style="color: #6b7280;">Not Set</span>';

                    // Exit Reason
                    row.insertCell().textContent = trade.exit_reason || '—';
                });

            } catch (error) {
                console.error('Error fetching trades:', error);
            } finally {
                indicator.classList.remove('updating');
            }
        }

        // Function to toggle DCA details
        function toggleDCADetails(button, trade) {
            const row = button.closest('tr');
            let detailsRow = row.nextElementSibling;

            if (detailsRow && detailsRow.classList.contains('dca-details-row')) {
                // Remove existing details row
                detailsRow.remove();
                button.textContent = '+';
            } else {
                // Create new details row
                detailsRow = document.createElement('tr');
                detailsRow.classList.add('dca-details-row');

                const detailsCell = document.createElement('td');
                detailsCell.colSpan = 14;
                detailsCell.style.padding = '0';

                // Create DCA details HTML
                let detailsHTML = '<div class="dca-details expanded">';
                detailsHTML += '<h4 style="margin-bottom: 10px; color: #cbd5e1;">DCA Grid Details</h4>';

                // Calculate grid levels based on trade data
                const gridLevels = calculateDCAGridLevels(trade);

                gridLevels.forEach((level, index) => {
                    const levelClass = level.filled ? 'filled' : 'pending';
                    detailsHTML += `
                        <div class="dca-grid-level ${levelClass}">
                            <span>Level ${index + 1}: $${level.price.toFixed(4)}</span>
                            <span>${level.filled ? 'Filled at ' + level.fillTime : 'Pending'}</span>
                            <span>${level.filled ? '$' + level.amount.toFixed(2) : ''}</span>
                        </div>
                    `;
                });

                // Add summary information
                const totalInvested = (trade.dca_fills || 1) * (trade.position_size || 50);
                const maxInvestment = 5 * (trade.position_size || 50);

                detailsHTML += `
                    <div class="dca-summary">
                        <div class="dca-summary-item">
                            <span>Total Invested:</span>
                            <span>$${totalInvested.toFixed(2)} / $${maxInvestment.toFixed(2)}</span>
                        </div>
                        <div class="dca-summary-item">
                            <span>Average Entry:</span>
                            <span>$${trade.entry_price.toFixed(4)}</span>
                        </div>
                        <div class="dca-summary-item">
                            <span>Next Level Triggers at:</span>
                            <span>${gridLevels.find(l => !l.filled) ? '$' + gridLevels.find(l => !l.filled).price.toFixed(4) : 'All filled'}</span>
                        </div>
                    </div>
                `;

                detailsHTML += '</div>';
                detailsCell.innerHTML = detailsHTML;
                detailsRow.appendChild(detailsCell);

                // Insert after current row
                row.parentNode.insertBefore(detailsRow, row.nextSibling);
                button.textContent = '−';
            }
        }

        // Function to calculate DCA grid levels
        function calculateDCAGridLevels(trade) {
            const levels = [];
            const basePrice = trade.initial_price || trade.entry_price;
            const gridSpacing = 0.02; // 2% spacing between levels
            const fills = trade.dca_fills || 1;

            for (let i = 0; i < 5; i++) {
                const levelPrice = basePrice * (1 - i * gridSpacing);
                levels.push({
                    price: levelPrice,
                    filled: i < fills,
                    fillTime: i < fills ? new Date().toLocaleTimeString() : null,
                    amount: trade.position_size || 50
                });
            }

            return levels;
        }

        // Update countdown
        setInterval(() => {
            countdown--;
            if (countdown <= 0) {
                countdown = 10;
                fetchTrades();
                checkEngineStatus();
            }
            document.getElementById('countdown').textContent = countdown;
        }, 1000);

        // Initial load
        fetchTrades();
        checkEngineStatus();
        updateStrategyStatus();

        // Update strategy status every 30 seconds (less frequent as it doesn't change as often)
        setInterval(() => {
            updateStrategyStatus();
        }, 30000);
    </script>
</body>
</html>
"""


@app.route("/")
def dashboard():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/engine-status")
def get_engine_status():
    """Check if paper trading engine is running"""
    import os
    from datetime import datetime, timedelta, timezone

    try:
        # If running on Railway, check database for recent activity
        if os.environ.get("RAILWAY_ENVIRONMENT"):
            # Check for recent trades or scan history entries (within last 30 minutes)
            # Using 30 minutes as Paper Trading may have periods of inactivity
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

            # Also check for the process in ps output for more details
            if is_running:
                ps_result = subprocess.run(
                    ["ps", "aux"], capture_output=True, text=True
                )
                paper_trading_running = "run_paper_trading" in ps_result.stdout
            else:
                paper_trading_running = False

            return jsonify(
                {
                    "running": paper_trading_running,
                    "pid": result.stdout.strip() if paper_trading_running else None,
                }
            )
    except Exception as e:
        logger.error(f"Error checking engine status: {e}")
        return jsonify({"running": False, "error": str(e)})


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
        stats = {
            "open_count": 0,
            "closed_count": 0,
            "win_count": 0,
            "loss_count": 0,
            "win_rate": 0,
            "total_pnl": 0,
            "total_pnl_dollar": 0,
            "unrealized_pnl": 0,
            "unrealized_pnl_dollar": 0,
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
            legacy_trades = []  # For trades without group_id

            for trade in result.data:
                group_id = trade.get("trade_group_id")

                if group_id:
                    # New format with group_id
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
                else:
                    # Legacy format without group_id
                    legacy_trades.append(trade)

            # Process grouped trades (new format with trade_group_id)
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
                    first_buy = group_data["buys"][0]

                    for buy in group_data["buys"]:
                        price = float(buy.get("price", 0))
                        amount = float(buy.get("amount", 1))
                        total_cost += price * amount
                        total_amount += amount

                    avg_entry_price = (
                        total_cost / total_amount if total_amount > 0 else 0
                    )
                    position_size = float(first_buy.get("position_size", 50))

                    # Check if position is closed (has SELL)
                    if group_data["sells"]:
                        # CLOSED POSITION
                        sell_trade = group_data["sells"][
                            0
                        ]  # Should only be one SELL per group
                        exit_price = float(sell_trade.get("price", 0))

                        # Calculate P&L
                        if avg_entry_price > 0:
                            pnl_pct = (
                                (exit_price - avg_entry_price) / avg_entry_price
                            ) * 100
                        else:
                            pnl_pct = (
                                float(sell_trade.get("pnl", 0)) / position_size * 100
                                if sell_trade.get("pnl")
                                else 0
                            )

                        # Calculate duration
                        entry_time = datetime.fromisoformat(
                            first_buy["created_at"].replace("Z", "+00:00")
                        )
                        exit_timestamp = sell_trade.get("filled_at") or sell_trade.get(
                            "created_at"
                        )
                        exit_time = datetime.fromisoformat(
                            exit_timestamp.replace("Z", "+00:00")
                        )
                        duration = exit_time - entry_time

                        # Format duration
                        days = duration.days
                        hours = duration.seconds // 3600
                        minutes = (duration.seconds % 3600) // 60

                        if days > 0:
                            duration_str = f"{days}d {hours}h"
                        elif hours > 0:
                            duration_str = f"{hours}h {minutes}m"
                        else:
                            duration_str = f"{minutes}m"

                        # Update stats
                        if pnl_pct > 0.1:
                            dot_color = "#22c55e"
                            stats["win_count"] += 1
                        elif pnl_pct < -0.1:
                            dot_color = "#ef4444"
                            stats["loss_count"] += 1
                        else:
                            dot_color = "#6b7280"

                        stats["closed_count"] += 1
                        stats["total_pnl"] += pnl_pct
                        stats["total_pnl_dollar"] += position_size * pnl_pct / 100

                        # Add closed trade to list
                        trades_data.append(
                            {
                                "symbol": symbol,
                                "strategy_name": strategy,
                                "position_size": position_size,
                                "entry_price": avg_entry_price,
                                "initial_price": float(first_buy.get("price", 0)),
                                "current_price": exit_price,
                                "exit_price": exit_price,
                                "pnl_pct": pnl_pct,
                                "status": "closed",
                                "duration": duration_str,
                                "dot_color": dot_color,
                                "dca_fills": len(group_data["buys"])
                                if strategy == "DCA"
                                else 1,
                                "sl_display": f"${first_buy['stop_loss']:.2f}"
                                if first_buy.get("stop_loss")
                                else None,
                                "tp_display": f"${first_buy['take_profit']:.2f}"
                                if first_buy.get("take_profit")
                                else None,
                                "ts_display": f"{float(first_buy.get('trailing_stop_pct', 0))*100:.1f}%"
                                if first_buy.get("trailing_stop_pct")
                                else None,
                                "exit_reason": sell_trade.get("exit_reason", ""),
                            }
                        )

                    else:
                        # OPEN POSITION (no SELL yet)
                        if not current_price:
                            continue  # Skip if no current price available

                        # Calculate unrealized P&L
                        pnl_pct = (
                            ((current_price - avg_entry_price) / avg_entry_price * 100)
                            if avg_entry_price > 0
                            else 0
                        )

                        # Calculate duration
                        entry_time = datetime.fromisoformat(
                            first_buy["created_at"].replace("Z", "+00:00")
                        )
                        duration = datetime.now(timezone.utc) - entry_time

                        # Format duration
                        days = duration.days
                        hours = duration.seconds // 3600
                        minutes = (duration.seconds % 3600) // 60

                        if days > 0:
                            duration_str = f"{days}d {hours}h"
                        elif hours > 0:
                            duration_str = f"{hours}h {minutes}m"
                        else:
                            duration_str = f"{minutes}m"

                        # Determine color
                        if pnl_pct > 0.1:
                            dot_color = "#22c55e"
                        elif pnl_pct < -0.1:
                            dot_color = "#ef4444"
                        else:
                            dot_color = "#6b7280"

                        # Calculate SL/TP/TS displays
                        sl_display = None
                        tp_display = None
                        ts_display = None

                        if first_buy.get("stop_loss"):
                            sl_price = float(first_buy["stop_loss"])
                            sl_pnl = (
                                (sl_price - avg_entry_price) / avg_entry_price
                            ) * 100
                            sl_display = f"{pnl_pct:.1f}% / {sl_pnl:.1f}%"

                        if first_buy.get("take_profit"):
                            tp_price = float(first_buy["take_profit"])
                            tp_pnl = (
                                (tp_price - avg_entry_price) / avg_entry_price
                            ) * 100
                            tp_display = f"{pnl_pct:.1f}% / {tp_pnl:.1f}%"

                        if first_buy.get("trailing_stop_pct"):
                            ts_pct = float(first_buy["trailing_stop_pct"]) * 100
                            if first_buy.get("take_profit"):
                                tp_price = float(first_buy["take_profit"])
                                tp_pnl = (
                                    (tp_price - avg_entry_price) / avg_entry_price
                                ) * 100
                                if pnl_pct >= tp_pnl:
                                    ts_display = (
                                        f"🟢 Active: {pnl_pct:.1f}% / -{ts_pct:.1f}%"
                                    )
                                else:
                                    ts_display = (
                                        f"⚪ Inactive (activates at TP: {tp_pnl:.1f}%)"
                                    )

                        # Update stats
                        stats["open_count"] += 1
                        stats["unrealized_pnl"] += pnl_pct
                        stats["unrealized_pnl_dollar"] += position_size * pnl_pct / 100

                        # Add open position to list
                        trades_data.append(
                            {
                                "symbol": symbol,
                                "strategy_name": strategy,
                                "position_size": position_size,
                                "entry_price": avg_entry_price,
                                "initial_price": float(first_buy.get("price", 0)),
                                "current_price": current_price,
                                "exit_price": None,
                                "pnl_pct": pnl_pct,
                                "status": "open",
                                "duration": duration_str,
                                "dot_color": dot_color,
                                "dca_fills": len(group_data["buys"])
                                if strategy == "DCA"
                                else 1,
                                "sl_display": sl_display,
                                "tp_display": tp_display,
                                "ts_display": ts_display,
                                "exit_reason": "",
                            }
                        )

            # Handle legacy trades (without trade_group_id) - simplified display
            # Just show them as individual trades for now
            for trade in legacy_trades:
                symbol = trade["symbol"]
                current_price = current_prices.get(symbol)

                if trade["side"] == "BUY" and trade["status"] == "FILLED":
                    # Legacy open position
                    entry_price = float(trade.get("price", 0))
                    position_size = float(trade.get("position_size", 50))

                    if current_price and entry_price > 0:
                        pnl_pct = ((current_price - entry_price) / entry_price) * 100
                    else:
                        pnl_pct = 0

                    # Simple duration calculation
                    entry_time = datetime.fromisoformat(
                        trade["created_at"].replace("Z", "+00:00")
                    )
                    duration = datetime.now(timezone.utc) - entry_time
                    duration_str = (
                        f"{duration.days}d"
                        if duration.days > 0
                        else f"{duration.seconds // 3600}h"
                    )

                    trades_data.append(
                        {
                            "symbol": symbol,
                            "strategy_name": trade.get("strategy_name", "LEGACY"),
                            "position_size": position_size,
                            "entry_price": entry_price,
                            "current_price": current_price,
                            "pnl_pct": pnl_pct,
                            "status": "open",
                            "duration": duration_str,
                            "dot_color": "#94a3b8",  # Gray for legacy
                            "dca_fills": 1,
                            "exit_reason": "",
                        }
                    )

                    stats["open_count"] += 1
                    stats["unrealized_pnl"] += pnl_pct
                    stats["unrealized_pnl_dollar"] += position_size * pnl_pct / 100

        # Calculate win rate
        total_closed = stats["win_count"] + stats["loss_count"]
        if total_closed > 0:
            stats["win_rate"] = (stats["win_count"] / total_closed) * 100

        # Sort trades: open first, then by status
        trades_data.sort(key=lambda x: (x["status"] != "open", x.get("entry_price", 0)))

        # Get current time in LA
        la_time = datetime.now(pytz.timezone("America/Los_Angeles"))
        timestamp = la_time.strftime("%Y-%m-%d %I:%M:%S %p PST")

        return jsonify({"trades": trades_data, "stats": stats, "timestamp": timestamp})

    except Exception as e:
        logger.error(f"Error fetching trades: {e}")
        return jsonify({"trades": [], "timestamp": "Error", "error": str(e)}), 500


@app.route("/api/strategy-status")
def get_strategy_status():
    """Get current strategy status and proximity to triggers - sorted by readiness"""
    try:
        print("DEBUG: Starting strategy-status endpoint")
        # NOTE: Database queries are timing out on Supabase
        # Returning simplified mock data to keep dashboard functional
        # TODO: Fix the database timeout issue - likely need to:
        # 1. Increase Supabase statement timeout
        # 2. Create better indexes
        # 3. Use a background service to pre-calculate this data

        strategy_status = {
            "swing": {
                "name": "SWING",
                "thresholds": {
                    "breakout_threshold": "2.0%",
                    "volume_spike": "1.5x average",
                    "rsi_range": "60-70 optimal",
                },
                "candidates": [],
            },
            "channel": {
                "name": "CHANNEL",
                "thresholds": {
                    "buy_zone": "Bottom 35% of channel",
                    "sell_zone": "Top 35% of channel",
                    "channel_width": "3-20% range",
                },
                "candidates": [],
            },
            "dca": {
                "name": "DCA",
                "thresholds": {
                    "drop_threshold": "-3.5% from recent high",
                    "lookback": "20 bars",
                },
                "candidates": [],
            },
        }

        # Skip database query for now - Supabase has timeout issues
        # Use mock data to keep dashboard functional
        btc_price = 95000  # Mock price

        # Add mock candidates
        strategy_status["swing"]["candidates"] = [
            {
                "symbol": "BTC",
                "readiness": 75,
                "current_price": f"${btc_price:.2f}",
                "details": "Near breakout level",
                "status": "CLOSE 🟡",
            },
            {
                "symbol": "ETH",
                "readiness": 65,
                "current_price": "$3,200.00",
                "details": "Building momentum",
                "status": "WAITING ⚪",
            },
        ]
        strategy_status["channel"]["candidates"] = [
            {
                "symbol": "SOL",
                "readiness": 85,
                "current_price": "$180.00",
                "details": "Bottom of channel",
                "status": "BUY ZONE 🟢",
            },
            {
                "symbol": "BTC",
                "readiness": 60,
                "current_price": f"${btc_price:.2f}",
                "details": "Middle of channel",
                "status": "NEUTRAL 🟡",
            },
        ]
        strategy_status["dca"]["candidates"] = [
            {
                "symbol": "BNB",
                "readiness": 70,
                "current_price": "$600.00",
                "details": "Drop: -4.2% from high",
                "status": "CLOSE 🟡",
            },
            {
                "symbol": "XRP",
                "readiness": 45,
                "current_price": "$2.20",
                "details": "Drop: -1.5% from high",
                "status": "WAITING ⚪",
            },
        ]

        market_condition = "NEUTRAL - DATABASE TIMEOUT"
        best_strategy = "CHANNEL"
        notes = "⚠️ Database timeout - showing mock data. Fix: Check Supabase statement_timeout setting"

        strategy_status["market_summary"] = {
            "condition": market_condition,
            "best_strategy": best_strategy,
            "notes": notes,
        }

        return jsonify(strategy_status)

    except Exception as e:
        logger.error(f"Error getting strategy status: {e}")

        # Return a simplified status on error to keep dashboard functional
        fallback_status = {
            "swing": {"name": "SWING", "thresholds": {}, "candidates": []},
            "channel": {"name": "CHANNEL", "thresholds": {}, "candidates": []},
            "dca": {"name": "DCA", "thresholds": {}, "candidates": []},
            "market_summary": {
                "condition": "DATA UNAVAILABLE",
                "best_strategy": "WAIT",
                "notes": f"Unable to fetch market data. Error: {str(e)[:100]}",
            },
        }
        return jsonify(fallback_status)


if __name__ == "__main__":
    import os

    # Get port from Railway or default to 8080 for local
    port = int(os.environ.get("PORT", 8080))

    print("\n" + "=" * 60)
    print("🚀 STARTING LIVE TRADING DASHBOARD")
    print("=" * 60)

    if os.environ.get("RAILWAY_ENVIRONMENT"):
        print(f"\n📊 Dashboard running on Railway (port {port})")
        print("🔗 Access via Railway's public URL")
    else:
        print(f"\n📊 Dashboard will be available at: http://localhost:{port}")

    print("🔄 Auto-updates every 10 seconds")
    print("\nPress Ctrl+C to stop the server\n")

    app.run(debug=False, host="0.0.0.0", port=port)
