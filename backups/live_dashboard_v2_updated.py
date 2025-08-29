"""
Enhanced Multi-Page Trading Dashboard with Admin Panel
Includes Paper Trading, Strategies, Market, R&D, and Admin pages
"""

import os
import json
import asyncio
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template_string, jsonify, request
from loguru import logger
import pytz
from src.data.supabase_client import SupabaseClient
from src.strategies.regime_detector import RegimeDetector
from src.trading.trade_limiter import TradeLimiter
from src.config.config_loader import ConfigLoader

# Configure logging
logger.add("dashboard.log", rotation="1 day", retention="7 days", level="INFO")

app = Flask(__name__)

# Initialize components
db_client = SupabaseClient()
regime_detector = RegimeDetector()
trade_limiter = TradeLimiter()
config_loader = ConfigLoader()

# Base CSS styles (shared across all pages)
BASE_CSS = r"""
body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    margin: 0;
    padding: 0;
    background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
    color: #fff;
    min-height: 100vh;
}
.container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 20px;
}
.header {
    text-align: center;
    margin-bottom: 30px;
    padding: 20px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    backdrop-filter: blur(10px);
}
.page-title {
    font-size: 2.5em;
    margin: 0;
    background: linear-gradient(45deg, #fff, #64b5f6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.subtitle {
    color: #b3d4fc;
    margin-top: 10px;
    font-size: 1.1em;
}
.nav-container {
    display: flex;
    justify-content: center;
    gap: 20px;
    margin: 20px 0;
    padding: 15px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    backdrop-filter: blur(10px);
    position: relative;
}
.nav-link {
    color: #b3d4fc;
    text-decoration: none;
    padding: 10px 20px;
    border-radius: 5px;
    transition: all 0.3s ease;
}
.nav-link:hover {
    background: rgba(255, 255, 255, 0.2);
    color: #fff;
}
.nav-link.active {
    background: rgba(255, 255, 255, 0.3);
    color: #fff;
    font-weight: bold;
}
.admin-icon {
    position: absolute;
    right: 20px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 1.5em;
}
.stats-container {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 20px;
    margin-bottom: 30px;
}
.stat-card {
    background: rgba(255, 255, 255, 0.1);
    padding: 20px;
    border-radius: 10px;
    backdrop-filter: blur(10px);
    text-align: center;
    transition: transform 0.3s ease;
}
.stat-card:hover {
    transform: translateY(-5px);
}
.stat-label {
    color: #b3d4fc;
    font-size: 0.9em;
    margin-bottom: 10px;
}
.stat-value {
    font-size: 1.8em;
    font-weight: bold;
}
.positive {
    color: #4caf50;
}
.negative {
    color: #f44336;
}
.neutral {
    color: #ffc107;
}
.table-container {
    background: rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    padding: 20px;
    backdrop-filter: blur(10px);
    overflow-x: auto;
    margin-top: 20px;
}
table {
    width: 100%;
    border-collapse: collapse;
}
th, td {
    padding: 12px;
    text-align: left;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
th {
    background: rgba(255, 255, 255, 0.1);
    font-weight: 600;
    color: #fff;
}
tr:hover {
    background: rgba(255, 255, 255, 0.05);
}
.status-badge {
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 0.85em;
    font-weight: 600;
}
.status-open {
    background: #2196F3;
    color: white;
}
.status-closed {
    background: #4CAF50;
    color: white;
}
.status-pending {
    background: #FFC107;
    color: black;
}
.loading {
    text-align: center;
    padding: 40px;
    color: #b3d4fc;
}
.error {
    background: #f44336;
    color: white;
    padding: 15px;
    border-radius: 5px;
    margin: 20px 0;
}
.refresh-timer {
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: rgba(0, 0, 0, 0.7);
    padding: 10px 15px;
    border-radius: 20px;
    font-size: 0.9em;
    color: #b3d4fc;
}
"""

# Admin Panel CSS
ADMIN_CSS = r"""
.kill-switch-card {
    grid-column: span 3;
    background: rgba(255, 100, 100, 0.1);
    border: 2px solid rgba(255, 100, 100, 0.3);
}
.kill-switch-container {
    display: flex;
    align-items: center;
    justify-content: center;
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
.slider.round {
    border-radius: 34px;
}
.slider.round:before {
    border-radius: 50%;
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
    background-color: #4CAF50;
}
input:checked + .slider:before {
    transform: translateX(26px);
}
.status-text {
    font-size: 1.2em;
    font-weight: bold;
}
.config-sections {
    display: grid;
    gap: 20px;
    margin-top: 30px;
}
.config-section {
    background: rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    padding: 20px;
    backdrop-filter: blur(10px);
}
.config-section h2 {
    margin-top: 0;
    color: #64b5f6;
    border-bottom: 2px solid rgba(100, 181, 246, 0.3);
    padding-bottom: 10px;
}
.config-section h3 {
    color: #90caf9;
    margin-top: 20px;
}
.config-group {
    margin: 15px 0;
}
.config-row {
    display: grid;
    grid-template-columns: 200px 150px auto;
    gap: 10px;
    align-items: center;
    margin: 10px 0;
}
.config-row label {
    color: #b3d4fc;
}
.config-row input {
    padding: 8px;
    border: 1px solid rgba(255, 255, 255, 0.3);
    background: rgba(255, 255, 255, 0.1);
    color: white;
    border-radius: 4px;
}
.config-row button {
    padding: 8px 15px;
    background: #2196F3;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: background 0.3s;
}
.config-row button:hover {
    background: #1976D2;
}
.history-table {
    width: 100%;
    margin-top: 20px;
}
.history-table th {
    background: rgba(33, 150, 243, 0.2);
}
.notification {
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 15px 20px;
    border-radius: 5px;
    animation: slideIn 0.3s ease;
    z-index: 1000;
}
.notification.success {
    background: #4CAF50;
}
.notification.error {
    background: #f44336;
}
@keyframes slideIn {
    from {
        transform: translateX(100%);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
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
    position: sticky;
    bottom: 20px;
    background: rgba(0, 0, 0, 0.9);
    padding: 20px;
    border-radius: 10px;
    display: flex;
    justify-content: center;
    gap: 20px;
    margin-top: 30px;
    box-shadow: 0 -5px 20px rgba(0, 0, 0, 0.5);
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
.tier-tabs {
    display: flex;
    gap: 10px;
    margin-bottom: 20px;
}
.tier-tab {
    padding: 8px 16px;
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.3);
    border-radius: 5px;
    cursor: pointer;
    transition: all 0.3s;
}
.tier-tab.active {
    background: rgba(33, 150, 243, 0.3);
    border-color: #2196F3;
}
.tier-content {
    display: none;
}
.tier-content.active {
    display: block;
}
.unsaved-indicator {
    display: inline-block;
    width: 8px;
    height: 8px;
    background: #ffc107;
    border-radius: 50%;
    margin-left: 5px;
    animation: pulse 1s infinite;
}
@keyframes pulse {
    0% { opacity: 1; }
    50% { opacity: 0.5; }
    100% { opacity: 1; }
}
"""

# Admin Panel Template
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
        <!-- Strategy Thresholds -->
        <div class="config-section">
            <h2>Strategy Thresholds</h2>
            
            <div class="config-group">
                <h3>DCA Strategy</h3>
                <div class="config-row">
                    <label>Drop Threshold (%)</label>
                    <input type="number" id="dca_drop_threshold" step="0.1" min="-20" max="0" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Min Confidence</label>
                    <input type="number" id="dca_min_confidence" step="0.01" min="0" max="1" onchange="markUnsaved()">
                </div>
            </div>
            
            <div class="config-group">
                <h3>SWING Strategy</h3>
                <div class="config-row">
                    <label>Breakout Threshold</label>
                    <input type="number" id="swing_breakout" step="0.001" min="1" max="1.1" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Volume Surge</label>
                    <input type="number" id="swing_volume" step="0.1" min="1" max="5" onchange="markUnsaved()">
                </div>
            </div>
            
            <div class="config-group">
                <h3>CHANNEL Strategy</h3>
                <div class="config-row">
                    <label>Buy Zone</label>
                    <input type="number" id="channel_buy_zone" step="0.01" min="0" max="0.5" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Channel Strength</label>
                    <input type="number" id="channel_strength" step="0.01" min="0" max="1" onchange="markUnsaved()">
                </div>
            </div>
        </div>
        
        <!-- Position Management -->
        <div class="config-section">
            <h2>Position Management</h2>
            <div class="config-row">
                <label>Max Total Positions</label>
                <input type="number" id="max_positions_total" min="1" max="200" onchange="markUnsaved()">
            </div>
            <div class="config-row">
                <label>Max Per Strategy</label>
                <input type="number" id="max_positions_strategy" min="1" max="100" onchange="markUnsaved()">
            </div>
            <div class="config-row">
                <label>Max Per Symbol</label>
                <input type="number" id="max_positions_symbol" min="1" max="10" onchange="markUnsaved()">
            </div>
            <div class="config-row">
                <label>Base Position Size ($)</label>
                <input type="number" id="base_position_size" step="10" min="10" max="10000" onchange="markUnsaved()">
            </div>
        </div>
        
        <!-- Exit Parameters by Tier -->
        <div class="config-section">
            <h2>Exit Parameters</h2>
            
            <!-- Tier Tabs -->
            <div class="tier-tabs">
                <div class="tier-tab active" onclick="switchTier('large_cap')">Large Cap</div>
                <div class="tier-tab" onclick="switchTier('mid_cap')">Mid Cap</div>
                <div class="tier-tab" onclick="switchTier('small_cap')">Small Cap</div>
                <div class="tier-tab" onclick="switchTier('memecoin')">Memecoin</div>
            </div>
            
            <!-- Large Cap -->
            <div id="tier_large_cap" class="tier-content active">
                <h3>Large Cap Exit Parameters</h3>
                <div class="config-row">
                    <label>Take Profit (%)</label>
                    <input type="number" id="large_cap_tp" step="0.1" min="0" max="50" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Stop Loss (%)</label>
                    <input type="number" id="large_cap_sl" step="0.1" min="0" max="50" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Trailing Stop (%)</label>
                    <input type="number" id="large_cap_ts" step="0.1" min="0" max="20" onchange="markUnsaved()">
                </div>
            </div>
            
            <!-- Mid Cap -->
            <div id="tier_mid_cap" class="tier-content">
                <h3>Mid Cap Exit Parameters</h3>
                <div class="config-row">
                    <label>Take Profit (%)</label>
                    <input type="number" id="mid_cap_tp" step="0.1" min="0" max="50" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Stop Loss (%)</label>
                    <input type="number" id="mid_cap_sl" step="0.1" min="0" max="50" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Trailing Stop (%)</label>
                    <input type="number" id="mid_cap_ts" step="0.1" min="0" max="20" onchange="markUnsaved()">
                </div>
            </div>
            
            <!-- Small Cap -->
            <div id="tier_small_cap" class="tier-content">
                <h3>Small Cap Exit Parameters</h3>
                <div class="config-row">
                    <label>Take Profit (%)</label>
                    <input type="number" id="small_cap_tp" step="0.1" min="0" max="50" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Stop Loss (%)</label>
                    <input type="number" id="small_cap_sl" step="0.1" min="0" max="50" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Trailing Stop (%)</label>
                    <input type="number" id="small_cap_ts" step="0.1" min="0" max="20" onchange="markUnsaved()">
                </div>
            </div>
            
            <!-- Memecoin -->
            <div id="tier_memecoin" class="tier-content">
                <h3>Memecoin Exit Parameters</h3>
                <div class="config-row">
                    <label>Take Profit (%)</label>
                    <input type="number" id="memecoin_tp" step="0.1" min="0" max="50" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Stop Loss (%)</label>
                    <input type="number" id="memecoin_sl" step="0.1" min="0" max="50" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Trailing Stop (%)</label>
                    <input type="number" id="memecoin_ts" step="0.1" min="0" max="20" onchange="markUnsaved()">
                </div>
            </div>
        </div>
        
        <!-- Market Protection -->
        <div class="config-section">
            <h2>Market Protection</h2>
            
            <div class="config-group">
                <h3>Market Regime Thresholds</h3>
                <div class="config-row">
                    <label>PANIC Threshold (%)</label>
                    <input type="number" id="panic_threshold" step="0.1" min="-50" max="0" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>CAUTION Threshold (%)</label>
                    <input type="number" id="caution_threshold" step="0.1" min="-20" max="0" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>EUPHORIA Threshold (%)</label>
                    <input type="number" id="euphoria_threshold" step="0.1" min="0" max="50" onchange="markUnsaved()">
                </div>
            </div>
            
            <div class="config-group">
                <h3>Position Size Adjustments</h3>
                <div class="config-row">
                    <label>PANIC Multiplier</label>
                    <input type="number" id="panic_mult" step="0.1" min="0" max="3" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>CAUTION Multiplier</label>
                    <input type="number" id="caution_mult" step="0.1" min="0" max="3" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>EUPHORIA Multiplier</label>
                    <input type="number" id="euphoria_mult" step="0.1" min="0" max="3" onchange="markUnsaved()">
                </div>
            </div>
            
            <div class="config-group">
                <h3>Trade Limiter</h3>
                <div class="config-row">
                    <label>Max Consecutive Stops</label>
                    <input type="number" id="max_consecutive_stops" min="1" max="10" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Large Cap Cooldown (hours)</label>
                    <input type="number" id="large_cap_cooldown" min="1" max="48" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Mid Cap Cooldown (hours)</label>
                    <input type="number" id="mid_cap_cooldown" min="1" max="48" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Small Cap Cooldown (hours)</label>
                    <input type="number" id="small_cap_cooldown" min="1" max="48" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Memecoin Cooldown (hours)</label>
                    <input type="number" id="memecoin_cooldown" min="1" max="72" onchange="markUnsaved()">
                </div>
            </div>
        </div>
        
        <!-- Risk Management -->
        <div class="config-section">
            <h2>Risk Management</h2>
            
            <div class="config-group">
                <h3>Portfolio Limits</h3>
                <div class="config-row">
                    <label>Max Daily Loss (%)</label>
                    <input type="number" id="max_daily_loss_pct" step="0.1" min="0" max="50" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Max Daily Loss ($)</label>
                    <input type="number" id="max_daily_loss_usd" step="10" min="0" max="10000" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Max Drawdown (%)</label>
                    <input type="number" id="max_drawdown" step="0.1" min="0" max="50" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Max Open Risk ($)</label>
                    <input type="number" id="max_open_risk" step="10" min="0" max="10000" onchange="markUnsaved()">
                </div>
            </div>
            
            <div class="config-group">
                <h3>Position Limits</h3>
                <div class="config-row">
                    <label>Max % in One Symbol</label>
                    <input type="number" id="max_concentration" step="0.1" min="0" max="100" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Max Correlated Positions</label>
                    <input type="number" id="max_correlated" min="1" max="50" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Risk Per Trade (%)</label>
                    <input type="number" id="risk_per_trade" step="0.1" min="0" max="10" onchange="markUnsaved()">
                </div>
            </div>
            
            <div class="config-group">
                <h3>Emergency Controls</h3>
                <div class="config-row">
                    <label>Consecutive Loss Limit</label>
                    <input type="number" id="consecutive_loss_limit" min="1" max="20" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Emergency Stop Loss (%)</label>
                    <input type="number" id="emergency_stop_loss" step="0.1" min="0" max="100" onchange="markUnsaved()">
                </div>
                <div class="config-row">
                    <label>Recovery Mode Enabled</label>
                    <input type="checkbox" id="recovery_mode" onchange="markUnsaved()">
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Save/Discard Controls -->
<div class="save-controls">
    <button class="save-btn" onclick="saveAllChanges()">💾 Save All Changes</button>
    <button class="discard-btn" onclick="discardChanges()">🔄 Discard Changes</button>
    <span id="unsavedIndicator" style="display: none;" class="unsaved-indicator"></span>
</div>

<!-- Configuration History -->
<div class="config-section">
    <h2>Recent Configuration Changes</h2>
    <div class="table-container">
        <table class="history-table">
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
            <tbody id="historyTableBody">
                <tr><td colspan="6" class="loading">Loading history...</td></tr>
            </tbody>
        </table>
    </div>
</div>
"""

# Admin Panel JavaScript
ADMIN_SCRIPTS = r"""
<script>
let originalConfig = {};
let currentConfig = {};
let hasUnsavedChanges = false;

// Load configuration on page load
async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        const data = await response.json();
        originalConfig = JSON.parse(JSON.stringify(data));
        currentConfig = JSON.parse(JSON.stringify(data));
        
        // Populate all fields
        populateFields(data);
        
        // Update kill switch status
        const killSwitch = document.getElementById('killSwitch');
        const status = document.getElementById('killSwitchStatus');
        killSwitch.checked = data.global_settings?.trading_enabled || false;
        status.textContent = killSwitch.checked ? 'ENABLED' : 'DISABLED';
        status.style.color = killSwitch.checked ? '#4CAF50' : '#f44336';
        
        hasUnsavedChanges = false;
        updateUnsavedIndicator();
    } catch (error) {
        console.error('Error loading config:', error);
        showNotification('Failed to load configuration', 'error');
    }
}

// Populate all form fields
function populateFields(config) {
    // Strategy thresholds
    setValue('dca_drop_threshold', config.strategies?.DCA?.drop_threshold);
    setValue('dca_min_confidence', config.strategies?.DCA?.min_confidence);
    setValue('swing_breakout', config.strategies?.SWING?.breakout_threshold);
    setValue('swing_volume', config.strategies?.SWING?.volume_surge);
    setValue('channel_buy_zone', config.strategies?.CHANNEL?.buy_zone);
    setValue('channel_strength', config.strategies?.CHANNEL?.channel_strength_min);
    
    // Position management
    setValue('max_positions_total', config.position_management?.max_positions_total);
    setValue('max_positions_strategy', config.position_management?.max_positions_per_strategy);
    setValue('max_positions_symbol', config.position_management?.max_positions_per_symbol);
    setValue('base_position_size', config.position_management?.position_sizing?.base_position_size_usd);
    
    // Exit parameters for all tiers
    const exitParams = config.exit_parameters || {};
    
    // Large Cap
    setValue('large_cap_tp', exitParams.large_cap?.take_profit);
    setValue('large_cap_sl', exitParams.large_cap?.stop_loss);
    setValue('large_cap_ts', exitParams.large_cap?.trailing_stop);
    
    // Mid Cap
    setValue('mid_cap_tp', exitParams.mid_cap?.take_profit);
    setValue('mid_cap_sl', exitParams.mid_cap?.stop_loss);
    setValue('mid_cap_ts', exitParams.mid_cap?.trailing_stop);
    
    // Small Cap
    setValue('small_cap_tp', exitParams.small_cap?.take_profit);
    setValue('small_cap_sl', exitParams.small_cap?.stop_loss);
    setValue('small_cap_ts', exitParams.small_cap?.trailing_stop);
    
    // Memecoin
    setValue('memecoin_tp', exitParams.memecoin?.take_profit);
    setValue('memecoin_sl', exitParams.memecoin?.stop_loss);
    setValue('memecoin_ts', exitParams.memecoin?.trailing_stop);
    
    // Market Protection
    const protection = config.market_protection || {};
    setValue('panic_threshold', protection.enhanced_regime?.panic_threshold);
    setValue('caution_threshold', protection.enhanced_regime?.caution_threshold);
    setValue('euphoria_threshold', protection.enhanced_regime?.euphoria_threshold);
    
    setValue('panic_mult', protection.stop_widening?.regime_multipliers?.PANIC);
    setValue('caution_mult', protection.stop_widening?.regime_multipliers?.CAUTION);
    setValue('euphoria_mult', protection.stop_widening?.regime_multipliers?.EUPHORIA);
    
    setValue('max_consecutive_stops', protection.trade_limiter?.max_consecutive_stops);
    setValue('large_cap_cooldown', protection.trade_limiter?.cooldown_hours_by_tier?.large_cap);
    setValue('mid_cap_cooldown', protection.trade_limiter?.cooldown_hours_by_tier?.mid_cap);
    setValue('small_cap_cooldown', protection.trade_limiter?.cooldown_hours_by_tier?.small_cap);
    setValue('memecoin_cooldown', protection.trade_limiter?.cooldown_hours_by_tier?.memecoin);
    
    // Risk Management
    const risk = config.risk_management || {};
    setValue('max_daily_loss_pct', risk.max_daily_loss ? risk.max_daily_loss * 100 : null);
    setValue('max_daily_loss_usd', risk.max_daily_loss_usd);
    setValue('max_drawdown', risk.max_drawdown ? risk.max_drawdown * 100 : null);
    setValue('max_open_risk', risk.max_open_risk);
    setValue('max_concentration', risk.max_concentration ? risk.max_concentration * 100 : null);
    setValue('max_correlated', risk.max_correlated_positions);
    setValue('risk_per_trade', risk.risk_per_trade ? risk.risk_per_trade * 100 : null);
    setValue('consecutive_loss_limit', risk.consecutive_loss_limit);
    setValue('emergency_stop_loss', risk.emergency_stop_loss ? risk.emergency_stop_loss * 100 : null);
    setChecked('recovery_mode', risk.recovery_mode_enabled);
}

// Helper function to set input value
function setValue(id, value) {
    const element = document.getElementById(id);
    if (element && value !== undefined && value !== null) {
        element.value = value;
    }
}

// Helper function to set checkbox
function setChecked(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.checked = value || false;
    }
}

// Mark configuration as having unsaved changes
function markUnsaved() {
    hasUnsavedChanges = true;
    updateUnsavedIndicator();
}

// Update unsaved indicator
function updateUnsavedIndicator() {
    const indicator = document.getElementById('unsavedIndicator');
    if (indicator) {
        indicator.style.display = hasUnsavedChanges ? 'inline-block' : 'none';
    }
}

// Switch between tier tabs
function switchTier(tier) {
    // Hide all tier contents
    document.querySelectorAll('.tier-content').forEach(content => {
        content.classList.remove('active');
    });
    
    // Remove active from all tabs
    document.querySelectorAll('.tier-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Show selected tier
    document.getElementById('tier_' + tier).classList.add('active');
    
    // Mark selected tab as active
    event.target.classList.add('active');
}

// Collect all changes
function collectChanges() {
    const changes = {};
    
    // Kill switch
    const killSwitch = document.getElementById('killSwitch').checked;
    if (killSwitch !== originalConfig.global_settings?.trading_enabled) {
        changes['global_settings.trading_enabled'] = killSwitch;
    }
    
    // Strategy thresholds
    checkChange(changes, 'strategies.DCA.drop_threshold', 'dca_drop_threshold');
    checkChange(changes, 'strategies.DCA.min_confidence', 'dca_min_confidence');
    checkChange(changes, 'strategies.SWING.breakout_threshold', 'swing_breakout');
    checkChange(changes, 'strategies.SWING.volume_surge', 'swing_volume');
    checkChange(changes, 'strategies.CHANNEL.buy_zone', 'channel_buy_zone');
    checkChange(changes, 'strategies.CHANNEL.channel_strength_min', 'channel_strength');
    
    // Position management
    checkChange(changes, 'position_management.max_positions_total', 'max_positions_total');
    checkChange(changes, 'position_management.max_positions_per_strategy', 'max_positions_strategy');
    checkChange(changes, 'position_management.max_positions_per_symbol', 'max_positions_symbol');
    checkChange(changes, 'position_management.position_sizing.base_position_size_usd', 'base_position_size');
    
    // Exit parameters for all tiers
    checkChange(changes, 'exit_parameters.large_cap.take_profit', 'large_cap_tp');
    checkChange(changes, 'exit_parameters.large_cap.stop_loss', 'large_cap_sl');
    checkChange(changes, 'exit_parameters.large_cap.trailing_stop', 'large_cap_ts');
    
    checkChange(changes, 'exit_parameters.mid_cap.take_profit', 'mid_cap_tp');
    checkChange(changes, 'exit_parameters.mid_cap.stop_loss', 'mid_cap_sl');
    checkChange(changes, 'exit_parameters.mid_cap.trailing_stop', 'mid_cap_ts');
    
    checkChange(changes, 'exit_parameters.small_cap.take_profit', 'small_cap_tp');
    checkChange(changes, 'exit_parameters.small_cap.stop_loss', 'small_cap_sl');
    checkChange(changes, 'exit_parameters.small_cap.trailing_stop', 'small_cap_ts');
    
    checkChange(changes, 'exit_parameters.memecoin.take_profit', 'memecoin_tp');
    checkChange(changes, 'exit_parameters.memecoin.stop_loss', 'memecoin_sl');
    checkChange(changes, 'exit_parameters.memecoin.trailing_stop', 'memecoin_ts');
    
    // Market Protection
    checkChange(changes, 'market_protection.enhanced_regime.panic_threshold', 'panic_threshold');
    checkChange(changes, 'market_protection.enhanced_regime.caution_threshold', 'caution_threshold');
    checkChange(changes, 'market_protection.enhanced_regime.euphoria_threshold', 'euphoria_threshold');
    
    checkChange(changes, 'market_protection.stop_widening.regime_multipliers.PANIC', 'panic_mult');
    checkChange(changes, 'market_protection.stop_widening.regime_multipliers.CAUTION', 'caution_mult');
    checkChange(changes, 'market_protection.stop_widening.regime_multipliers.EUPHORIA', 'euphoria_mult');
    
    checkChange(changes, 'market_protection.trade_limiter.max_consecutive_stops', 'max_consecutive_stops');
    checkChange(changes, 'market_protection.trade_limiter.cooldown_hours_by_tier.large_cap', 'large_cap_cooldown');
    checkChange(changes, 'market_protection.trade_limiter.cooldown_hours_by_tier.mid_cap', 'mid_cap_cooldown');
    checkChange(changes, 'market_protection.trade_limiter.cooldown_hours_by_tier.small_cap', 'small_cap_cooldown');
    checkChange(changes, 'market_protection.trade_limiter.cooldown_hours_by_tier.memecoin', 'memecoin_cooldown');
    
    // Risk Management
    checkChangePercent(changes, 'risk_management.max_daily_loss', 'max_daily_loss_pct');
    checkChange(changes, 'risk_management.max_daily_loss_usd', 'max_daily_loss_usd');
    checkChangePercent(changes, 'risk_management.max_drawdown', 'max_drawdown');
    checkChange(changes, 'risk_management.max_open_risk', 'max_open_risk');
    checkChangePercent(changes, 'risk_management.max_concentration', 'max_concentration');
    checkChange(changes, 'risk_management.max_correlated_positions', 'max_correlated');
    checkChangePercent(changes, 'risk_management.risk_per_trade', 'risk_per_trade');
    checkChange(changes, 'risk_management.consecutive_loss_limit', 'consecutive_loss_limit');
    checkChangePercent(changes, 'risk_management.emergency_stop_loss', 'emergency_stop_loss');
    checkChangeCheckbox(changes, 'risk_management.recovery_mode_enabled', 'recovery_mode');
    
    return changes;
}

// Helper to check if a value changed
function checkChange(changes, path, elementId) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    const newValue = element.value ? parseFloat(element.value) : null;
    const oldValue = getNestedValue(originalConfig, path);
    
    if (newValue !== oldValue && newValue !== null) {
        changes[path] = newValue;
    }
}

// Helper to check percentage changes (convert to decimal)
function checkChangePercent(changes, path, elementId) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    const newValue = element.value ? parseFloat(element.value) / 100 : null;
    const oldValue = getNestedValue(originalConfig, path);
    
    if (newValue !== oldValue && newValue !== null) {
        changes[path] = newValue;
    }
}

// Helper to check checkbox changes
function checkChangeCheckbox(changes, path, elementId) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    const newValue = element.checked;
    const oldValue = getNestedValue(originalConfig, path) || false;
    
    if (newValue !== oldValue) {
        changes[path] = newValue;
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

// Save all changes
async function saveAllChanges() {
    const changes = collectChanges();
    
    if (Object.keys(changes).length === 0) {
        showNotification('No changes to save', 'info');
        return;
    }
    
    try {
        const response = await fetch('/api/config/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                updates: changes,
                description: `Bulk update: ${Object.keys(changes).length} fields changed`
            })
        });
        
        if (response.ok) {
            showNotification(`Saved ${Object.keys(changes).length} configuration changes`, 'success');
            hasUnsavedChanges = false;
            updateUnsavedIndicator();
            await loadConfig();  // Reload to get new version
            await loadConfigHistory();
        } else {
            throw new Error('Failed to save configuration');
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
        updateUnsavedIndicator();
        showNotification('Changes discarded', 'info');
    }
}

// Load configuration history
async function loadConfigHistory() {
    try {
        const response = await fetch('/api/config/history');
        const history = await response.json();
        
        const tbody = document.getElementById('historyTableBody');
        if (history.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6">No configuration changes recorded</td></tr>';
        } else {
            tbody.innerHTML = history.slice(0, 20).map(entry => `
                <tr>
                    <td>${new Date(entry.change_timestamp).toLocaleString()}</td>
                    <td>${entry.config_section || '-'}</td>
                    <td>${entry.field_name || '-'}</td>
                    <td>${entry.old_value || '-'}</td>
                    <td>${entry.new_value || '-'}</td>
                    <td>${entry.changed_by || 'System'}</td>
                </tr>
            `).join('');
        }
    } catch (error) {
        console.error('Error loading history:', error);
    }
}

// Show notification
function showNotification(message, type) {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 3000);
}

// Warn before leaving with unsaved changes
window.addEventListener('beforeunload', (event) => {
    if (hasUnsavedChanges) {
        event.preventDefault();
        event.returnValue = '';
    }
});

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    loadConfig();
    loadConfigHistory();
    
    // Refresh history every 30 seconds
    setInterval(loadConfigHistory, 30000);
});
</script>
"""

# Base template
BASE_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - Crypto Tracker v3</title>
    <style>
        {{ base_css }}
        {{ page_css }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 class="page-title">Crypto Tracker v3</h1>
            <p class="subtitle">Advanced Trading System Dashboard</p>
        </div>
        
        <!-- Navigation -->
        <div class="nav-container">
            <a href="/" class="nav-link {{ 'active' if active_page == 'trades' else '' }}">Paper Trading</a>
            <a href="/strategies" class="nav-link {{ 'active' if active_page == 'strategies' else '' }}">Strategies</a>
            <a href="/market" class="nav-link {{ 'active' if active_page == 'market' else '' }}">Market</a>
            <a href="/rd" class="nav-link {{ 'active' if active_page == 'rd' else '' }}">R&D</a>
            <a href="/admin" class="nav-link admin-icon {{ 'active' if active_page == 'admin' else '' }}" title="Admin Panel">
                ⚙️
            </a>
        </div>
        
        <!-- Page Content -->
        {{ content }}
        
        <!-- Refresh Timer -->
        <div class="refresh-timer" id="refreshTimer">
            Auto-refresh: <span id="countdown">30</span>s
        </div>
    </div>
    
    {{ page_scripts }}
</body>
</html>
"""


# Admin route
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


# API endpoint for getting config
@app.route("/api/config")
def get_config():
    """Get current configuration"""
    try:
        config = config_loader.load()
        return jsonify(config)
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        return jsonify({"error": str(e)}), 500


# API endpoint for updating config
@app.route("/api/config/update", methods=["POST"])
def update_config():
    """Update configuration values"""
    try:
        data = request.json
        updates = data.get("updates", {})
        description = data.get("description", "Manual update via admin panel")

        if not updates:
            return jsonify({"error": "No updates provided"}), 400

        # Update configuration
        success = config_loader.update_config(
            updates=updates,
            change_type="manual",
            changed_by="Admin Panel",
            description=description,
        )

        if success:
            return jsonify(
                {
                    "success": True,
                    "message": f"Updated {len(updates)} configuration values",
                }
            )
        else:
            return jsonify({"error": "Failed to update configuration"}), 500

    except Exception as e:
        logger.error(f"Error updating config: {e}")
        return jsonify({"error": str(e)}), 500


# API endpoint for config history
@app.route("/api/config/history")
def get_config_history():
    """Get configuration change history"""
    try:
        history = config_loader.get_config_history(limit=100)
        return jsonify(history)
    except Exception as e:
        logger.error(f"Error getting config history: {e}")
        return jsonify([])


if __name__ == "__main__":
    logger.info("Starting Enhanced Multi-Page Dashboard")
    app.run(host="0.0.0.0", port=8080, debug=False)
