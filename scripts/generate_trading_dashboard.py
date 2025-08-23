#!/usr/bin/env python3
"""
Generate an HTML trading dashboard showing all open and closed trades.
Auto-refreshes every minute with current performance data.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
import json
import pytz

sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from loguru import logger


def get_current_prices(supabase, symbols):
    """Get current prices for all symbols."""
    prices = {}
    
    for symbol in symbols:
        try:
            # Get the most recent price from ohlc_data
            result = supabase.client.table("ohlc_data")\
                .select("close")\
                .eq("symbol", symbol)\
                .order("timestamp", desc=True)\
                .limit(1)\
                .execute()
            
            if result.data:
                prices[symbol] = float(result.data[0]['close'])
            else:
                prices[symbol] = None
                
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            prices[symbol] = None
    
    return prices


def calculate_trade_metrics(trade, current_price):
    """Calculate performance metrics for a trade."""
    metrics = {}
    
    # For paper_trades table, we use 'price' for entry price
    entry_price = float(trade['price']) if trade.get('price') else 0
    
    # Determine if trade is open or closed based on side and status
    is_open = trade['side'] == 'BUY' and trade['status'] == 'FILLED'
    is_closed = trade['side'] == 'SELL' or trade.get('pnl') is not None
    
    if is_closed and trade.get('pnl') is not None:
        # For closed trades, use the actual P&L value
        metrics['current_price'] = float(trade['exit_price']) if trade.get('exit_price') else entry_price
        # If we have the actual P&L amount, calculate the percentage
        if trade.get('amount') and entry_price > 0:
            position_value = entry_price * float(trade['amount'])
            metrics['pnl_pct'] = (float(trade['pnl']) / position_value) * 100 if position_value > 0 else 0
        else:
            # Fallback: just use the P&L as percentage if we can't calculate it
            metrics['pnl_pct'] = float(trade['pnl']) if trade.get('pnl') else 0
    elif current_price and is_open:
        # For open trades, use current price
        metrics['current_price'] = current_price
        metrics['pnl_pct'] = ((current_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
    else:
        metrics['current_price'] = None
        metrics['pnl_pct'] = 0
    
    # Calculate distance to limits for open trades
    if is_open and current_price and entry_price > 0:
        current_pnl = ((current_price - entry_price) / entry_price) * 100
        
        # Stop Loss tracking
        if trade.get('stop_loss'):
            sl_price = float(trade['stop_loss'])
            sl_pnl = ((sl_price - entry_price) / entry_price) * 100
            metrics['sl_current'] = f"{current_pnl:.1f}%"
            metrics['sl_limit'] = f"{sl_pnl:.1f}%"
            metrics['sl_display'] = f"{current_pnl:.1f}% / {sl_pnl:.1f}%"
        else:
            metrics['sl_display'] = "Not Set"
        
        # Take Profit tracking
        if trade.get('take_profit'):
            tp_price = float(trade['take_profit'])
            tp_pnl = ((tp_price - entry_price) / entry_price) * 100
            metrics['tp_current'] = f"{current_pnl:.1f}%"
            metrics['tp_limit'] = f"{tp_pnl:.1f}%"
            metrics['tp_display'] = f"{current_pnl:.1f}% / {tp_pnl:.1f}%"
        else:
            metrics['tp_display'] = "Not Set"
        
        # Trailing Stop tracking
        if trade.get('trailing_stop_pct'):
            ts_pct = float(trade['trailing_stop_pct'])
            # Trailing stop moves with the highest price reached
            # For now, show current position vs trailing percentage
            metrics['ts_current'] = f"{current_pnl:.1f}%"
            metrics['ts_limit'] = f"-{ts_pct:.1f}%"
            metrics['ts_display'] = f"{current_pnl:.1f}% / -{ts_pct:.1f}%"
        else:
            metrics['ts_display'] = "Not Set"
    else:
        # For closed trades, just show the limits that were set
        metrics['sl_display'] = f"${trade.get('stop_loss'):.2f}" if trade.get('stop_loss') else "Not Set"
        metrics['tp_display'] = f"${trade.get('take_profit'):.2f}" if trade.get('take_profit') else "Not Set"
        metrics['ts_display'] = f"{float(trade.get('trailing_stop_pct'))*100:.1f}%" if trade.get('trailing_stop_pct') else "Not Set"
    
    # Calculate duration
    if trade.get('created_at'):
        entry_time = datetime.fromisoformat(trade['created_at'].replace('Z', '+00:00'))
        
        # For closed trades, use exit_time if available (from the SELL trade)
        # Otherwise for open trades, use current time
        if is_closed and trade.get('exit_time'):
            exit_time = datetime.fromisoformat(trade['exit_time'].replace('Z', '+00:00'))
            duration = exit_time - entry_time
        elif is_closed and trade.get('filled_at'):
            # Fallback to filled_at if exit_time is not available
            exit_time = datetime.fromisoformat(trade['filled_at'].replace('Z', '+00:00'))
            duration = exit_time - entry_time
        elif not is_closed:
            # For open trades, calculate duration from entry to now
            duration = datetime.now(timezone.utc) - entry_time
        else:
            # If we can't determine the exit time for a closed trade, show N/A
            logger.warning(f"Cannot determine exit time for closed trade {trade.get('symbol')}")
            metrics['duration'] = "N/A"
            return metrics
        
        # Format duration
        days = duration.days
        hours = duration.seconds // 3600
        minutes = (duration.seconds % 3600) // 60
        
        if days > 0:
            metrics['duration'] = f"{days}d {hours}h"
        elif hours > 0:
            metrics['duration'] = f"{hours}h {minutes}m"
        else:
            metrics['duration'] = f"{minutes}m"
    else:
        metrics['duration'] = "N/A"
    
    # Determine status dot color
    if metrics['pnl_pct'] > 0.1:  # Positive (with small buffer for rounding)
        metrics['dot_color'] = '#22c55e'  # Green
        metrics['dot_title'] = 'Profit'
    elif metrics['pnl_pct'] < -0.1:  # Negative (with small buffer for rounding)
        metrics['dot_color'] = '#ef4444'  # Red
        metrics['dot_title'] = 'Loss'
    else:  # Even (between -0.1% and 0.1%)
        metrics['dot_color'] = '#6b7280'  # Gray/Black
        metrics['dot_title'] = 'Even'
    
    return metrics


def generate_html(trades_data):
    """Generate the HTML dashboard."""
    
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="60">
    <title>Trading Dashboard</title>
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
            max-width: 1600px;
            margin: 0 auto;
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
        
        table {
            width: 100%;
            background: rgba(30, 41, 59, 0.5);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(148, 163, 184, 0.1);
            border-radius: 12px;
            overflow: hidden;
            border-collapse: separate;
            border-spacing: 0;
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
        }
        
        td {
            padding: 14px 12px;
            border-bottom: 1px solid rgba(148, 163, 184, 0.05);
            font-size: 0.95rem;
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
        
        .symbol {
            font-weight: 600;
            color: #f1f5f9;
        }
        
        .price {
            font-family: 'Courier New', monospace;
            color: #cbd5e1;
        }
        
        .pnl-positive {
            color: #22c55e;
            font-weight: 600;
        }
        
        .pnl-negative {
            color: #ef4444;
            font-weight: 600;
        }
        
        .pnl-even {
            color: #94a3b8;
            font-weight: 600;
        }
        
        .status-open {
            background: rgba(59, 130, 246, 0.2);
            color: #60a5fa;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.875rem;
            font-weight: 600;
            display: inline-block;
        }
        
        .status-closed {
            background: rgba(107, 114, 128, 0.2);
            color: #9ca3af;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.875rem;
            font-weight: 600;
            display: inline-block;
        }
        
        .limit-tracking {
            font-size: 0.875rem;
            color: #cbd5e1;
            font-family: 'Courier New', monospace;
        }
        
        .limit-not-set {
            color: #6b7280;
            font-style: italic;
            font-size: 0.875rem;
        }
        
        .exit-reason {
            font-size: 0.875rem;
            color: #94a3b8;
        }
        
        .duration {
            color: #94a3b8;
            font-size: 0.875rem;
        }
        
        .current-price {
            color: #60a5fa;
            font-weight: 500;
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
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .pulse {
            animation: pulse 2s infinite;
        }
        
        .strategy-name {
            background: rgba(139, 92, 246, 0.2);
            color: #a78bfa;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.875rem;
            font-weight: 600;
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
        
        .strategy-card li:last-child {
            margin-bottom: 0;
        }
        
        @media (max-width: 768px) {
            .strategies-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
    <script>
        // Auto-refresh every 60 seconds
        let secondsLeft = 60;
        
        // Update countdown and refresh when it hits 0
        const refreshInterval = setInterval(function() {
            secondsLeft--;
            
            // Update the display
            const timerElement = document.querySelector('.refresh-timer');
            if (timerElement) {
                timerElement.textContent = secondsLeft + 's';
            }
            
            // Refresh when countdown reaches 0
            if (secondsLeft <= 0) {
                clearInterval(refreshInterval);
                location.reload();
            }
        }, 1000);
        
        // Also force refresh if meta refresh fails (backup after 65 seconds)
        setTimeout(function() {
            location.reload();
        }, 65000);
    </script>
</head>
<body>
    <div class="refresh-indicator">
        <span class="pulse">🔄</span> Auto-refresh: <span class="refresh-timer">60s</span>
    </div>
    
    <div class="container">
        <h1>Trading Dashboard</h1>
        <p class="subtitle">Last updated: """ + datetime.now(pytz.timezone('America/Los_Angeles')).strftime("%Y-%m-%d %I:%M:%S %p PST") + """</p>
        
        <div class="stats-container">
            <div class="stat-card">
                <div class="stat-label">Open Trades</div>
                <div class="stat-value" style="color: #60a5fa;">""" + str(trades_data['stats']['open_count']) + """</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Closed Trades</div>
                <div class="stat-value">""" + str(trades_data['stats']['closed_count']) + """</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Win Rate</div>
                <div class="stat-value" style="color: """ + ('#22c55e' if trades_data['stats']['win_rate'] >= 50 else '#ef4444') + """;">""" + f"{trades_data['stats']['win_rate']:.1f}%" + """</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Unrealized P&L %</div>
                <div class="stat-value" style="color: """ + ('#22c55e' if trades_data['stats']['unrealized_pnl'] >= 0 else '#ef4444') + """;">""" + f"{trades_data['stats']['unrealized_pnl']:.2f}%" + """</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Total P&L %</div>
                <div class="stat-value" style="color: """ + ('#22c55e' if trades_data['stats']['total_pnl'] >= 0 else '#ef4444') + """;">""" + f"{trades_data['stats']['total_pnl']:.2f}%" + """</div>
            </div>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th style="width: 30px;"></th>
                    <th>Symbol</th>
                    <th>Strategy</th>
                    <th>Entry Price</th>
                    <th>Current Price</th>
                    <th>Exit Price</th>
                    <th>P&L %</th>
                    <th>Status</th>
                    <th>Duration</th>
                    <th>SL</th>
                    <th>TP</th>
                    <th>TS</th>
                    <th>Exit Reason</th>
                </tr>
            </thead>
            <tbody>
"""
    
    # Add table rows
    for trade in trades_data['trades']:
        metrics = trade['metrics']
        
        # Determine P&L class
        if metrics['pnl_pct'] > 0.1:
            pnl_class = "pnl-positive"
        elif metrics['pnl_pct'] < -0.1:
            pnl_class = "pnl-negative"
        else:
            pnl_class = "pnl-even"
        
        # Status badge
        status_badge = f'<span class="status-{trade["trade_status"]}">{trade["trade_status"].upper()}</span>'
        
        # Format prices
        entry_price = f"${float(trade['price']):.2f}" if trade.get('price') else "—"
        current_price = f"${metrics['current_price']:.2f}" if metrics['current_price'] else "—"
        exit_price = f"${float(trade['exit_price']):.2f}" if trade.get('exit_price') else "—"
        
        # Format limits
        sl_display = f'<span class="limit-tracking">{metrics["sl_display"]}</span>' if metrics['sl_display'] != "Not Set" else '<span class="limit-not-set">Not Set</span>'
        tp_display = f'<span class="limit-tracking">{metrics["tp_display"]}</span>' if metrics['tp_display'] != "Not Set" else '<span class="limit-not-set">Not Set</span>'
        ts_display = f'<span class="limit-tracking">{metrics["ts_display"]}</span>' if metrics['ts_display'] != "Not Set" else '<span class="limit-not-set">Not Set</span>'
        
        # Exit reason
        exit_reason = f'<span class="exit-reason">{trade.get("exit_reason", "")}</span>' if trade.get('exit_reason') else "—"
        
        # Strategy name
        strategy = trade.get('strategy_name', 'Unknown')
        strategy_display = f'<span class="strategy-name">{strategy}</span>'
        
        html += f"""
                <tr>
                    <td><span class="status-dot" style="background-color: {metrics['dot_color']};" title="{metrics['dot_title']}"></span></td>
                    <td><span class="symbol">{trade['symbol']}</span></td>
                    <td>{strategy_display}</td>
                    <td><span class="price">{entry_price}</span></td>
                    <td><span class="current-price">{current_price}</span></td>
                    <td><span class="price">{exit_price}</span></td>
                    <td><span class="{pnl_class}">{metrics['pnl_pct']:.2f}%</span></td>
                    <td>{status_badge}</td>
                    <td><span class="duration">{metrics['duration']}</span></td>
                    <td>{sl_display}</td>
                    <td>{tp_display}</td>
                    <td>{ts_display}</td>
                    <td>{exit_reason}</td>
                </tr>
"""
    
    html += """
            </tbody>
        </table>
        
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
</body>
</html>
"""
    
    return html


def main():
    """Generate the trading dashboard."""
    
    logger.info("Generating trading dashboard...")
    supabase = SupabaseClient()
    
    try:
        # Fetch all trades from paper_trades table
        result = supabase.client.table("paper_trades")\
            .select("*")\
            .order("side", desc=False)\
            .order("created_at", desc=True)\
            .execute()
        
        if not result.data:
            logger.warning("No trades found")
            trades = []
        else:
            trades = result.data
        
        # Get unique symbols
        symbols = list(set(trade['symbol'] for trade in trades if trade['symbol']))
        
        # Get current prices
        logger.info(f"Fetching current prices for {len(symbols)} symbols...")
        current_prices = get_current_prices(supabase, symbols)
        
        # Process trades and calculate metrics
        trades_data = {
            'trades': [],
            'stats': {
                'open_count': 0,
                'closed_count': 0,
                'total_pnl': 0,
                'unrealized_pnl': 0,  # New field for unrealized P&L
                'win_count': 0,
                'loss_count': 0,
                'win_rate': 0
            }
        }
        
        # Group trades by symbol to match BUY with SELL
        trades_by_symbol = {}
        for trade in trades:
            symbol = trade['symbol']
            if symbol not in trades_by_symbol:
                trades_by_symbol[symbol] = {'buys': [], 'sells': []}
            
            if trade['side'] == 'BUY':
                trades_by_symbol[symbol]['buys'].append(trade)
            else:
                trades_by_symbol[symbol]['sells'].append(trade)
        
        # Process trades
        for symbol, symbol_trades in trades_by_symbol.items():
            # Get current price
            current_price = current_prices.get(symbol)
            
            # Sort buys and sells by created_at
            symbol_trades['buys'].sort(key=lambda x: x['created_at'])
            symbol_trades['sells'].sort(key=lambda x: x['created_at'])
            
            # Track which buys have been matched with sells
            matched_buys = set()
            
            # Process closed trades first (matching BUY and SELL)
            for sell_trade in symbol_trades['sells']:
                # Find the first unmatched buy that came before this sell
                matching_buy = None
                for i, buy in enumerate(symbol_trades['buys']):
                    if i not in matched_buys and buy['created_at'] <= sell_trade['created_at']:
                        matching_buy = buy
                        matched_buys.add(i)
                        break
                
                if matching_buy:
                    # Use filled_at from SELL trade if available, otherwise use updated_at or created_at
                    exit_timestamp = sell_trade.get('filled_at') or sell_trade.get('updated_at') or sell_trade.get('created_at')
                    
                    # Create a combined trade record
                    combined_trade = {
                        **matching_buy,
                        'exit_price': sell_trade['price'],
                        'exit_time': exit_timestamp,  # Use the best available timestamp from SELL trade
                        'pnl': sell_trade.get('pnl', 0),
                        'exit_reason': sell_trade.get('exit_reason', ''),
                        'trade_status': 'closed'
                    }
                    
                    metrics = calculate_trade_metrics(combined_trade, None)
                    combined_trade['metrics'] = metrics
                    
                    trades_data['trades'].append(combined_trade)
                    trades_data['stats']['closed_count'] += 1
                    
                    if metrics['pnl_pct'] > 0:
                        trades_data['stats']['win_count'] += 1
                    elif metrics['pnl_pct'] < 0:
                        trades_data['stats']['loss_count'] += 1
                    
                    trades_data['stats']['total_pnl'] += metrics['pnl_pct']
            
            # Process open positions (unmatched BUYs)
            for i, buy_trade in enumerate(symbol_trades['buys']):
                if i not in matched_buys and buy_trade['status'] == 'FILLED':
                    metrics = calculate_trade_metrics(buy_trade, current_price)
                    trade_data = {
                        **buy_trade,
                        'metrics': metrics,
                        'trade_status': 'open'
                    }
                    trades_data['trades'].append(trade_data)
                    trades_data['stats']['open_count'] += 1
                    # Add to unrealized P&L
                    trades_data['stats']['unrealized_pnl'] += metrics['pnl_pct']
        
        # Calculate win rate
        total_closed = trades_data['stats']['win_count'] + trades_data['stats']['loss_count']
        if total_closed > 0:
            trades_data['stats']['win_rate'] = (trades_data['stats']['win_count'] / total_closed) * 100
        
        # Sort trades: open first, then by created time
        trades_data['trades'].sort(key=lambda x: (x['trade_status'] != 'open', x['created_at'] or ''), reverse=False)
        
        # Generate HTML
        html_content = generate_html(trades_data)
        
        # Save to file
        output_path = Path(__file__).parent.parent / "trading_dashboard.html"
        with open(output_path, 'w') as f:
            f.write(html_content)
        
        logger.success(f"Dashboard generated successfully: {output_path}")
        print(f"\n✅ Trading dashboard saved to: {output_path}")
        print(f"📊 Stats: {trades_data['stats']['open_count']} open, {trades_data['stats']['closed_count']} closed trades")
        print(f"🔄 The dashboard auto-refreshes every 60 seconds")
        print(f"\n🌐 Open the file in your browser to view the dashboard")
        
        return str(output_path)
        
    except Exception as e:
        logger.error(f"Error generating dashboard: {e}")
        raise


if __name__ == "__main__":
    main()
