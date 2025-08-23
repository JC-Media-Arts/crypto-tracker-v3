#!/usr/bin/env python3
"""
Live trading dashboard server that auto-updates
"""

from flask import Flask, render_template_string, jsonify
from datetime import datetime
import pytz
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from src.data.supabase_client import SupabaseClient
from loguru import logger

app = Flask(__name__)

HTML_TEMPLATE = """
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
                    html += '<h4 style="color: #94a3b8; font-size: 0.875rem; margin-bottom: 8px;">Top 5 Closest to Trigger:</h4>';

                    // Sort candidates by proximity to trigger
                    let sortedCandidates = [...strategy.candidates];
                    sortedCandidates.sort((a, b) => {
                        // Extract numeric distance from the "needs" field
                        const extractDistance = (needs) => {
                            if (!needs) return 999;

                            // If it's "Ready" status, return 0 (closest to trigger)
                            if (needs.toLowerCase().includes('ready')) return 0;

                            // Extract percentage (e.g., "0.7% more drop needed" -> 0.7)
                            const percentMatch = needs.match(/(\d+\.?\d*)%/);
                            if (percentMatch) return parseFloat(percentMatch[1]);

                            // Extract dollar amount (e.g., "$406.00 rise needed" -> 406.00)
                            const dollarMatch = needs.match(/\$(\d+\.?\d*)/);
                            if (dollarMatch) {
                                // Normalize dollar amounts to percentage equivalent
                                // Use a small percentage for dollar amounts to keep them comparable
                                return parseFloat(dollarMatch[1]) * 0.001;
                            }

                            // Default for unparseable values
                            return 999;
                        };

                        const aDistance = extractDistance(a.needs);
                        const bDistance = extractDistance(b.needs);

                        // Sort by distance (smaller distance = closer to trigger = higher priority)
                        return aDistance - bDistance;
                    });

                    // Display only top 5 candidates
                    sortedCandidates.slice(0, 5).forEach(candidate => {
                        const statusClass = candidate.status === 'READY' ? 'ready' :
                                          candidate.status === 'WAITING' ? 'waiting' :
                                          candidate.status === 'BUY ZONE' ? 'buy-zone' :
                                          candidate.status === 'SELL ZONE' ? 'sell-zone' : 'neutral';

                        const itemClass = candidate.status === 'READY' || candidate.status === 'BUY ZONE' ? 'ready' :
                                        candidate.status === 'WAITING' ? 'waiting' : 'neutral';

                        html += `
                            <div class="candidate-item ${itemClass}">
                                <div class="candidate-header">
                                    <span class="candidate-symbol">${candidate.symbol}</span>
                                    <span class="candidate-status ${statusClass}">${candidate.status}</span>
                                </div>
                                <div class="candidate-details">
                        `;

                        // Add strategy-specific details
                        if (key === 'swing') {
                            html += `
                                <div class="candidate-detail">
                                    <span>Price:</span>
                                    <span style="color: #cbd5e1;">${candidate.current_price}</span>
                                </div>
                                <div class="candidate-detail">
                                    <span>Breakout:</span>
                                    <span style="color: #cbd5e1;">${candidate.breakout}</span>
                                </div>
                                <div class="candidate-detail">
                                    <span>Volume:</span>
                                    <span style="color: #cbd5e1;">${candidate.volume}</span>
                                </div>
                            `;
                        } else if (key === 'channel') {
                            html += `
                                <div class="candidate-detail">
                                    <span>Price:</span>
                                    <span style="color: #cbd5e1;">${candidate.current_price}</span>
                                </div>
                                <div class="candidate-detail">
                                    <span>Position:</span>
                                    <span style="color: #cbd5e1;">${candidate.position}</span>
                                </div>
                                <div class="candidate-detail">
                                    <span>Range:</span>
                                    <span style="color: #cbd5e1;">${candidate.channel_range}</span>
                                </div>
                            `;
                        } else if (key === 'dca') {
                            html += `
                                <div class="candidate-detail">
                                    <span>Price:</span>
                                    <span style="color: #cbd5e1;">${candidate.current_price}</span>
                                </div>
                                <div class="candidate-detail">
                                    <span>Drop:</span>
                                    <span style="color: #cbd5e1;">${candidate.drop_from_high}</span>
                                </div>
                            `;
                        }

                        html += `
                                </div>
                                <div class="candidate-needs">📍 ${candidate.needs}</div>
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
    import subprocess

    try:
        # Check if the paper trading process is running
        result = subprocess.run(["pgrep", "-f", "run_paper_trading"], capture_output=True, text=True)
        is_running = bool(result.stdout.strip())

        # Also check for the process in ps output for more details
        if is_running:
            ps_result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
            paper_trading_running = "run_paper_trading" in ps_result.stdout
        else:
            paper_trading_running = False

        return jsonify(
            {"running": paper_trading_running, "pid": result.stdout.strip() if paper_trading_running else None}
        )
    except Exception as e:
        logger.error(f"Error checking engine status: {e}")
        return jsonify({"running": False, "error": str(e)})


@app.route("/api/trades")
def get_trades():
    """API endpoint to get current trades data"""
    try:
        db = SupabaseClient()

        # Get all trades
        result = (
            db.client.table("paper_trades")
            .select("*")
            .order("side", desc=False)
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
            symbols = list(set(trade["symbol"] for trade in result.data if trade["symbol"]))
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
                except:
                    pass

            # Process trades - group by symbol to match BUY/SELL
            trades_by_symbol = {}
            for trade in result.data:
                symbol = trade["symbol"]
                if symbol not in trades_by_symbol:
                    trades_by_symbol[symbol] = {"buys": [], "sells": []}

                if trade["side"] == "BUY":
                    trades_by_symbol[symbol]["buys"].append(trade)
                else:
                    trades_by_symbol[symbol]["sells"].append(trade)

            # Process each symbol's trades
            for symbol, symbol_trades in trades_by_symbol.items():
                current_price = current_prices.get(symbol)

                # Sort by created_at
                symbol_trades["buys"].sort(key=lambda x: x["created_at"])
                symbol_trades["sells"].sort(key=lambda x: x["created_at"])

                # Track matched buys
                matched_buys = set()

                # Process closed trades (matching BUY and SELL)
                for sell_trade in symbol_trades["sells"]:
                    # Find matching buy
                    for i, buy_trade in enumerate(symbol_trades["buys"]):
                        if i not in matched_buys and buy_trade["created_at"] <= sell_trade["created_at"]:
                            matched_buys.add(i)

                            # Create closed trade record
                            entry_price = float(buy_trade["price"]) if buy_trade.get("price") else 0
                            exit_price = float(sell_trade["price"]) if sell_trade.get("price") else 0

                            if entry_price > 0:
                                pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                            else:
                                pnl_pct = float(sell_trade.get("pnl", 0)) if sell_trade.get("pnl") else 0

                            # Calculate duration
                            from datetime import datetime, timezone

                            entry_time = datetime.fromisoformat(buy_trade["created_at"].replace("Z", "+00:00"))
                            # Use filled_at from SELL trade if available, otherwise use updated_at or created_at
                            exit_timestamp = (
                                sell_trade.get("filled_at")
                                or sell_trade.get("updated_at")
                                or sell_trade.get("created_at")
                            )
                            exit_time = datetime.fromisoformat(exit_timestamp.replace("Z", "+00:00"))
                            duration = exit_time - entry_time
                            days = duration.days
                            hours = duration.seconds // 3600
                            minutes = (duration.seconds % 3600) // 60

                            # Format duration more precisely
                            if days > 0:
                                duration_str = f"{days}d {hours}h"
                            elif hours > 0:
                                duration_str = f"{hours}h {minutes}m"
                            else:
                                duration_str = f"{minutes}m"

                            # Determine dot color
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
                            position_size = float(buy_trade.get("position_size", 50))
                            stats["total_pnl_dollar"] += position_size * pnl_pct / 100

                            trades_data.append(
                                {
                                    "symbol": symbol,
                                    "strategy_name": buy_trade.get("strategy_name", "N/A"),
                                    "position_size": float(buy_trade.get("position_size", 50)),  # Default to $50
                                    "entry_price": entry_price,
                                    "current_price": exit_price,
                                    "exit_price": exit_price,
                                    "pnl_pct": pnl_pct,
                                    "status": "closed",
                                    "duration": duration_str,
                                    "dot_color": dot_color,
                                    "sl_display": f"${buy_trade['stop_loss']:.2f}"
                                    if buy_trade.get("stop_loss")
                                    else None,
                                    "tp_display": f"${buy_trade['take_profit']:.2f}"
                                    if buy_trade.get("take_profit")
                                    else None,
                                    "ts_display": f"{float(buy_trade.get('trailing_stop_pct', 0))*100:.1f}%"
                                    if buy_trade.get("trailing_stop_pct")
                                    else None,
                                    "exit_reason": sell_trade.get("exit_reason", ""),
                                }
                            )
                            break

                # Process open positions (unmatched BUYs)
                for i, buy_trade in enumerate(symbol_trades["buys"]):
                    if i not in matched_buys and buy_trade["status"] == "FILLED":
                        entry_price = float(buy_trade["price"]) if buy_trade.get("price") else 0

                        if current_price and entry_price > 0:
                            pnl_pct = ((current_price - entry_price) / entry_price) * 100
                            current_pnl = pnl_pct

                            # Calculate SL/TP/TS displays for open positions
                            sl_display = None
                            tp_display = None
                            ts_display = None

                            if buy_trade.get("stop_loss"):
                                sl_price = float(buy_trade["stop_loss"])
                                sl_pnl = ((sl_price - entry_price) / entry_price) * 100
                                sl_display = f"{current_pnl:.1f}% / {sl_pnl:.1f}%"

                            if buy_trade.get("take_profit"):
                                tp_price = float(buy_trade["take_profit"])
                                tp_pnl = ((tp_price - entry_price) / entry_price) * 100
                                tp_display = f"{current_pnl:.1f}% / {tp_pnl:.1f}%"

                            if buy_trade.get("trailing_stop_pct"):
                                ts_pct = float(buy_trade["trailing_stop_pct"]) * 100
                                # Trailing stop only activates after TP is hit
                                if current_pnl >= tp_pnl:  # TP has been reached
                                    # Calculate the trailing stop trigger price from highest
                                    highest_price = buy_trade.get("highest_price", current_price)
                                    ts_trigger_from_high = ((current_price - highest_price) / highest_price) * 100
                                    ts_display = f"🟢 Active: {ts_trigger_from_high:.1f}% / -{ts_pct:.1f}%"
                                else:
                                    # Not yet active - show when it will activate
                                    ts_display = f"⚪ Inactive (activates at TP: {tp_pnl:.1f}%)"
                        else:
                            pnl_pct = 0
                            sl_display = None
                            tp_display = None
                            ts_display = None

                        # Calculate duration
                        from datetime import datetime, timezone

                        entry_time = datetime.fromisoformat(buy_trade["created_at"].replace("Z", "+00:00"))
                        duration = datetime.now(timezone.utc) - entry_time
                        days = duration.days
                        hours = duration.seconds // 3600
                        minutes = (duration.seconds % 3600) // 60

                        # Format duration more precisely
                        if days > 0:
                            duration_str = f"{days}d {hours}h"
                        elif hours > 0:
                            duration_str = f"{hours}h {minutes}m"
                        else:
                            duration_str = f"{minutes}m"

                        # Determine dot color
                        if pnl_pct > 0.1:
                            dot_color = "#22c55e"
                        elif pnl_pct < -0.1:
                            dot_color = "#ef4444"
                        else:
                            dot_color = "#6b7280"

                        stats["open_count"] += 1
                        stats["unrealized_pnl"] += pnl_pct
                        position_size = float(buy_trade.get("position_size", 50))
                        stats["unrealized_pnl_dollar"] += position_size * pnl_pct / 100

                        # Check if this is part of a DCA grid
                        dca_fills = 1
                        initial_price = entry_price
                        if buy_trade.get("strategy_name") == "DCA":
                            # Count how many BUY trades exist for this symbol
                            all_buys_for_symbol = [
                                t
                                for t in symbol_trades["buys"]
                                if t["status"] == "FILLED" and t.get("strategy_name") == "DCA"
                            ]
                            dca_fills = len(all_buys_for_symbol)

                            # Calculate average entry price if multiple fills
                            if dca_fills > 1:
                                total_cost = sum(
                                    float(t["price"]) * float(t.get("amount", 1)) for t in all_buys_for_symbol
                                )
                                total_amount = sum(float(t.get("amount", 1)) for t in all_buys_for_symbol)
                                entry_price = total_cost / total_amount if total_amount > 0 else entry_price
                                initial_price = float(all_buys_for_symbol[0]["price"])

                        trades_data.append(
                            {
                                "symbol": symbol,
                                "strategy_name": buy_trade.get("strategy_name", "N/A"),
                                "position_size": float(buy_trade.get("position_size", 50)),  # Default to $50
                                "entry_price": entry_price,
                                "initial_price": initial_price,
                                "dca_fills": dca_fills,
                                "current_price": current_price,
                                "exit_price": None,
                                "pnl_pct": pnl_pct,
                                "status": "open",
                                "duration": duration_str,
                                "dot_color": dot_color,
                                "sl_display": sl_display,
                                "tp_display": tp_display,
                                "ts_display": ts_display,
                                "exit_reason": "",
                            }
                        )

        # Calculate win rate
        total_closed = stats["win_count"] + stats["loss_count"]
        if total_closed > 0:
            stats["win_rate"] = (stats["win_count"] / total_closed) * 100

        # Sort trades: open first, then by created time
        trades_data.sort(key=lambda x: (x["status"] != "open"))

        # Get current time in LA
        la_time = datetime.now(pytz.timezone("America/Los_Angeles"))
        timestamp = la_time.strftime("%Y-%m-%d %I:%M:%S %p PST")

        return jsonify({"trades": trades_data, "stats": stats, "timestamp": timestamp})

    except Exception as e:
        logger.error(f"Error fetching trades: {e}")
        return jsonify({"trades": [], "timestamp": "Error", "error": str(e)}), 500


@app.route("/api/strategy-status")
def get_strategy_status():
    """Get current strategy status and proximity to triggers"""
    try:
        supabase = SupabaseClient()

        # Get recent market data for a few key symbols
        symbols = ["BTC", "ETH", "SOL", "DOGE", "SHIB"]
        strategy_status = {
            "swing": {"name": "SWING", "thresholds": {}, "candidates": [], "market_needs": []},
            "channel": {"name": "CHANNEL", "thresholds": {}, "candidates": [], "market_needs": []},
            "dca": {"name": "DCA", "thresholds": {}, "candidates": [], "market_needs": []},
        }

        # Get thresholds from detectors
        from src.strategies.swing.detector import SwingDetector
        from src.strategies.channel.detector import ChannelDetector
        from src.strategies.simple_rules import SimpleRules

        # Initialize detectors
        swing_detector = SwingDetector(supabase)
        channel_detector = ChannelDetector()
        simple_rules = SimpleRules()

        # Swing thresholds
        strategy_status["swing"]["thresholds"] = {
            "breakout_threshold": f"{(swing_detector.config['breakout_threshold'] - 1) * 100:.1f}%",
            "volume_spike": f"{swing_detector.config['volume_spike_threshold']}x",
            "min_price_change_24h": f"{swing_detector.config['min_price_change_24h']}%",
            "rsi_range": f"{swing_detector.config['rsi_bullish_min']}-{swing_detector.config['rsi_overbought']}",
            "fallback_breakout": f"{simple_rules.swing_breakout_threshold}%",
            "fallback_volume": "1.5x",
        }

        # Channel thresholds
        strategy_status["channel"]["thresholds"] = {
            "min_touches": f"{channel_detector.min_touches} per line",
            "buy_zone": f"< {channel_detector.buy_zone * 100:.0f}%",
            "sell_zone": f"> {channel_detector.sell_zone * 100:.0f}%",
            "channel_width": f"{channel_detector.min_channel_width * 100:.1f}-{channel_detector.max_channel_width * 100:.0f}%",
            "fallback_position": f"< {simple_rules.channel_position_threshold * 100:.0f}%",
        }

        # DCA thresholds
        strategy_status["dca"]["thresholds"] = {
            "drop_threshold": f"{simple_rules.dca_drop_threshold}%",
            "lookback_period": "20 bars",
        }

        # Check each symbol for proximity to triggers
        for symbol in symbols:
            # Get recent data
            result = (
                supabase.client.table("ohlc_data")
                .select("*")
                .eq("symbol", symbol)
                .order("timestamp", desc=True)
                .limit(25)
                .execute()
            )

            if not result.data or len(result.data) < 20:
                continue

            data = result.data[::-1]  # Reverse to chronological
            current = data[-1]
            recent_data = data[-10:-1]

            # Check Swing proximity
            recent_high = max(d["high"] for d in recent_data)
            breakout_pct = ((current["close"] - recent_high) / recent_high) * 100
            avg_volume = sum(d["volume"] for d in recent_data) / len(recent_data)
            volume_ratio = current["volume"] / avg_volume if avg_volume > 0 else 0

            swing_info = {
                "symbol": symbol,
                "current_price": f"${current['close']:.2f}" if current["close"] > 1 else f"${current['close']:.4f}",
                "breakout": f"{breakout_pct:.2f}%",
                "volume": f"{volume_ratio:.1f}x",
                "status": "READY" if breakout_pct > 0.3 and volume_ratio > 1.5 else "WAITING",
            }

            if breakout_pct > 0:
                swing_info["needs"] = f"Already breaking out!"
            elif breakout_pct > -1:
                swing_info["needs"] = f"${abs(breakout_pct * current['close'] / 100):.2f} rise needed"
            else:
                swing_info["needs"] = f"Needs {abs(breakout_pct):.1f}% recovery first"

            strategy_status["swing"]["candidates"].append(swing_info)

            # Check Channel proximity
            prices = [d["close"] for d in data[-20:]]
            high = max(prices)
            low = min(prices)
            current_price = prices[-1]
            position = (current_price - low) / (high - low) if high != low else 0.5

            channel_info = {
                "symbol": symbol,
                "current_price": f"${current_price:.2f}" if current_price > 1 else f"${current_price:.4f}",
                "position": f"{position * 100:.1f}%",
                "channel_range": f"${low:.2f}-${high:.2f}" if low > 1 else f"${low:.4f}-${high:.4f}",
                "status": "BUY ZONE" if position <= 0.35 else ("SELL ZONE" if position >= 0.65 else "NEUTRAL"),
            }

            if position <= 0.35:
                channel_info["needs"] = "Ready for BUY"
            elif position >= 0.65:
                channel_info["needs"] = "Ready for SELL (if holding)"
            else:
                if position < 0.5:
                    drop_needed = (current_price - low * 1.35) / current_price * 100
                    channel_info["needs"] = f"{abs(drop_needed):.1f}% drop to buy zone"
                else:
                    rise_needed = (high * 0.65 - current_price) / current_price * 100
                    channel_info["needs"] = f"{rise_needed:.1f}% rise to sell zone"

            strategy_status["channel"]["candidates"].append(channel_info)

            # Check DCA proximity
            high_20 = max(d["high"] for d in data[-20:])
            drop_from_high = ((current["close"] - high_20) / high_20) * 100

            dca_info = {
                "symbol": symbol,
                "current_price": f"${current['close']:.2f}" if current["close"] > 1 else f"${current['close']:.4f}",
                "drop_from_high": f"{drop_from_high:.2f}%",
                "status": "READY" if drop_from_high <= -1.0 else "WAITING",
            }

            if drop_from_high <= -1.0:
                dca_info["needs"] = "Ready for DCA entry"
            else:
                additional_drop = abs(-1.0 - drop_from_high)
                dca_info["needs"] = f"{additional_drop:.1f}% more drop needed"

            strategy_status["dca"]["candidates"].append(dca_info)

        # Add market condition summary
        strategy_status["market_summary"] = {
            "condition": "CONSOLIDATION",
            "best_strategy": "CHANNEL",
            "notes": "Low volume and sideways movement favors channel trading",
        }

        return jsonify(strategy_status)

    except Exception as e:
        logger.error(f"Error getting strategy status: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 STARTING LIVE TRADING DASHBOARD")
    print("=" * 60)
    print("\n📊 Dashboard will be available at: http://localhost:8080")
    print("🔄 Auto-updates every 10 seconds")
    print("\nPress Ctrl+C to stop the server\n")

    app.run(debug=False, host="0.0.0.0", port=8080)
