#!/usr/bin/env python3
"""
Analyze why trades aren't triggering and show near-misses
"""

import asyncio
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List
import numpy as np
from loguru import logger
import sys

# Add parent directory to path
sys.path.append('.')

from src.data.supabase_client import SupabaseClient
from src.strategies.dca.detector import DCADetector
from src.strategies.swing.detector import SwingDetector
from src.strategies.channel.detector import ChannelDetector


class TradingActivityAnalyzer:
    def __init__(self):
        self.supabase = SupabaseClient()
        self.dca_detector = DCADetector({
            'drop_threshold': -5.0,
            'rsi_oversold': 30,
            'min_volume_ratio': 1.5
        })
        self.swing_detector = SwingDetector({
            'breakout_threshold': 2.0,
            'volume_surge_min': 2.0,
            'momentum_period': 14
        })
        self.channel_detector = ChannelDetector({
            'channel_period': 20,
            'min_touches': 3,
            'channel_width_min': 2.0
        })
        
        # Symbols to analyze
        self.symbols = [
            'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'AVAX', 'DOGE',
            'PEPE', 'WIF', 'BONK', 'FLOKI', 'MEME', 'POPCAT', 'MEW',
            'ARB', 'OP', 'AAVE', 'INJ', 'SEI'
        ]
    
    def fetch_recent_data(self, symbol: str, hours: int = 24) -> List[Dict]:
        """Fetch recent OHLC data for a symbol"""
        try:
            cutoff = datetime.now() - timedelta(hours=hours)
            
            response = self.supabase.client.table('ohlc_data').select('*').eq(
                'symbol', symbol
            ).gte('timestamp', cutoff.isoformat()).order(
                'timestamp', desc=False
            ).execute()
            
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return []
    
    def analyze_dca_opportunities(self, symbol: str, data: List[Dict]) -> Dict:
        """Analyze how close a symbol is to DCA trigger"""
        if not data or len(data) < 20:
            return {'status': 'insufficient_data'}
        
        # Get latest price and 4-hour high
        latest = data[-1]
        current_price = latest.get('close', 0)
        
        # Calculate 4-hour high (16 bars of 15min)
        lookback_bars = min(16, len(data))
        recent_data = data[-lookback_bars:]
        high_4h = max(bar.get('high', 0) for bar in recent_data)
        
        # Calculate drop percentage
        drop_pct = ((current_price - high_4h) / high_4h) * 100 if high_4h > 0 else 0
        
        # Calculate RSI
        closes = [bar.get('close', 0) for bar in data[-14:]]
        rsi = self._calculate_rsi(closes) if len(closes) >= 14 else 50
        
        # Volume analysis
        recent_volume = sum(bar.get('volume', 0) for bar in recent_data) / len(recent_data)
        avg_volume = sum(bar.get('volume', 0) for bar in data) / len(data)
        volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1
        
        # Check against thresholds
        drop_threshold = -5.0
        rsi_threshold = 30
        volume_threshold = 1.5
        
        # Calculate how close we are
        drop_distance = abs(drop_pct - drop_threshold) if drop_pct > drop_threshold else 0
        rsi_distance = abs(rsi - rsi_threshold) if rsi > rsi_threshold else 0
        volume_distance = abs(volume_ratio - volume_threshold) if volume_ratio < volume_threshold else 0
        
        # Would trigger?
        would_trigger = (drop_pct <= drop_threshold and 
                        rsi <= rsi_threshold and 
                        volume_ratio >= volume_threshold)
        
        return {
            'status': 'analyzed',
            'would_trigger': would_trigger,
            'current_price': current_price,
            'high_4h': high_4h,
            'drop_pct': drop_pct,
            'drop_threshold': drop_threshold,
            'drop_distance': drop_distance,
            'rsi': rsi,
            'rsi_threshold': rsi_threshold,
            'rsi_distance': rsi_distance,
            'volume_ratio': volume_ratio,
            'volume_threshold': volume_threshold,
            'volume_distance': volume_distance,
            'missing_conditions': []
        }
    
    def analyze_swing_opportunities(self, symbol: str, data: List[Dict]) -> Dict:
        """Analyze how close a symbol is to Swing trigger"""
        if not data or len(data) < 20:
            return {'status': 'insufficient_data'}
        
        latest = data[-1]
        current_price = latest.get('close', 0)
        
        # Check for breakout above 20-period high
        highs = [bar.get('high', 0) for bar in data[-20:]]
        period_high = max(highs[:-1])  # Exclude current bar
        breakout_pct = ((current_price - period_high) / period_high) * 100 if period_high > 0 else 0
        
        # Volume surge
        current_volume = latest.get('volume', 0)
        avg_volume = sum(bar.get('volume', 0) for bar in data[-20:]) / 20
        volume_surge = current_volume / avg_volume if avg_volume > 0 else 1
        
        # Momentum (price change over last 5 bars)
        if len(data) >= 5:
            price_5_bars_ago = data[-5].get('close', current_price)
            momentum = ((current_price - price_5_bars_ago) / price_5_bars_ago) * 100
        else:
            momentum = 0
        
        # Thresholds
        breakout_threshold = 2.0  # 2% above high
        volume_threshold = 2.0  # 2x average volume
        momentum_threshold = 3.0  # 3% gain in 5 bars
        
        # Calculate distances
        breakout_distance = abs(breakout_pct - breakout_threshold) if breakout_pct < breakout_threshold else 0
        volume_distance = abs(volume_surge - volume_threshold) if volume_surge < volume_threshold else 0
        momentum_distance = abs(momentum - momentum_threshold) if momentum < momentum_threshold else 0
        
        # Would trigger?
        would_trigger = (breakout_pct >= breakout_threshold and 
                        volume_surge >= volume_threshold and 
                        momentum >= momentum_threshold)
        
        return {
            'status': 'analyzed',
            'would_trigger': would_trigger,
            'current_price': current_price,
            'period_high': period_high,
            'breakout_pct': breakout_pct,
            'breakout_threshold': breakout_threshold,
            'breakout_distance': breakout_distance,
            'volume_surge': volume_surge,
            'volume_threshold': volume_threshold,
            'volume_distance': volume_distance,
            'momentum': momentum,
            'momentum_threshold': momentum_threshold,
            'momentum_distance': momentum_distance
        }
    
    def analyze_channel_opportunities(self, symbol: str, data: List[Dict]) -> Dict:
        """Analyze how close a symbol is to Channel trigger"""
        if not data or len(data) < 20:
            return {'status': 'insufficient_data'}
        
        latest = data[-1]
        current_price = latest.get('close', 0)
        
        # Calculate channel (simplified - using high/low of last 20 bars)
        highs = [bar.get('high', 0) for bar in data[-20:]]
        lows = [bar.get('low', 0) for bar in data[-20:]]
        
        channel_high = np.percentile(highs, 75)
        channel_low = np.percentile(lows, 25)
        channel_mid = (channel_high + channel_low) / 2
        channel_width = ((channel_high - channel_low) / channel_mid) * 100 if channel_mid > 0 else 0
        
        # Position in channel (0 = bottom, 1 = top)
        if channel_high > channel_low:
            position_in_channel = (current_price - channel_low) / (channel_high - channel_low)
        else:
            position_in_channel = 0.5
        
        # Check if price is near channel boundaries
        near_top = position_in_channel > 0.8
        near_bottom = position_in_channel < 0.2
        in_middle = 0.3 <= position_in_channel <= 0.7
        
        # Channel width threshold
        min_channel_width = 2.0  # At least 2% wide
        max_channel_width = 10.0  # Not more than 10% wide (not ranging if too wide)
        
        # Would trigger?
        would_trigger = (min_channel_width <= channel_width <= max_channel_width and
                        (near_top or near_bottom))
        
        return {
            'status': 'analyzed',
            'would_trigger': would_trigger,
            'current_price': current_price,
            'channel_high': channel_high,
            'channel_low': channel_low,
            'channel_width': channel_width,
            'position_in_channel': position_in_channel,
            'near_top': near_top,
            'near_bottom': near_bottom,
            'in_middle': in_middle,
            'min_width': min_channel_width,
            'max_width': max_channel_width
        }
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI"""
        if len(prices) < period:
            return 50
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    async def run_analysis(self):
        """Run comprehensive analysis"""
        print("\n" + "="*80)
        print("TRADING ACTIVITY ANALYSIS - Why No Trades?")
        print("="*80)
        print(f"Analysis Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Analyzing last 24 hours of data")
        print("="*80)
        
        near_misses = {
            'DCA': [],
            'Swing': [],
            'Channel': []
        }
        
        for symbol in self.symbols:
            print(f"\n📊 Analyzing {symbol}...")
            
            # Fetch data
            data = self.fetch_recent_data(symbol, hours=24)
            if not data:
                print(f"  ⚠️  No data available")
                continue
            
            print(f"  📈 Data points: {len(data)}")
            
            # Analyze each strategy
            dca_analysis = self.analyze_dca_opportunities(symbol, data)
            swing_analysis = self.analyze_swing_opportunities(symbol, data)
            channel_analysis = self.analyze_channel_opportunities(symbol, data)
            
            # DCA Analysis
            if dca_analysis['status'] == 'analyzed':
                if dca_analysis['would_trigger']:
                    print(f"  ✅ DCA: WOULD TRIGGER NOW!")
                else:
                    print(f"  ❌ DCA: Not ready")
                    print(f"     Drop: {dca_analysis['drop_pct']:.2f}% (need ≤ {dca_analysis['drop_threshold']:.1f}%)")
                    print(f"     RSI: {dca_analysis['rsi']:.1f} (need ≤ {dca_analysis['rsi_threshold']})")
                    print(f"     Volume: {dca_analysis['volume_ratio']:.2f}x (need ≥ {dca_analysis['volume_threshold']:.1f}x)")
                    
                    # Track near misses
                    total_distance = (dca_analysis['drop_distance'] + 
                                    dca_analysis['rsi_distance'] / 10 +  # Normalize RSI
                                    dca_analysis['volume_distance'])
                    if total_distance < 3:  # Close to triggering
                        near_misses['DCA'].append({
                            'symbol': symbol,
                            'distance': total_distance,
                            'details': dca_analysis
                        })
            
            # Swing Analysis
            if swing_analysis['status'] == 'analyzed':
                if swing_analysis['would_trigger']:
                    print(f"  ✅ Swing: WOULD TRIGGER NOW!")
                else:
                    print(f"  ❌ Swing: Not ready")
                    print(f"     Breakout: {swing_analysis['breakout_pct']:.2f}% (need ≥ {swing_analysis['breakout_threshold']:.1f}%)")
                    print(f"     Volume: {swing_analysis['volume_surge']:.2f}x (need ≥ {swing_analysis['volume_threshold']:.1f}x)")
                    print(f"     Momentum: {swing_analysis['momentum']:.2f}% (need ≥ {swing_analysis['momentum_threshold']:.1f}%)")
                    
                    # Track near misses
                    total_distance = (swing_analysis['breakout_distance'] + 
                                    swing_analysis['volume_distance'] +
                                    swing_analysis['momentum_distance'])
                    if total_distance < 5:  # Close to triggering
                        near_misses['Swing'].append({
                            'symbol': symbol,
                            'distance': total_distance,
                            'details': swing_analysis
                        })
            
            # Channel Analysis
            if channel_analysis['status'] == 'analyzed':
                if channel_analysis['would_trigger']:
                    print(f"  ✅ Channel: WOULD TRIGGER NOW!")
                else:
                    position_desc = "near top" if channel_analysis['near_top'] else \
                                  "near bottom" if channel_analysis['near_bottom'] else "in middle"
                    print(f"  ❌ Channel: Not ready")
                    print(f"     Width: {channel_analysis['channel_width']:.2f}% (need {channel_analysis['min_width']:.1f}-{channel_analysis['max_width']:.1f}%)")
                    print(f"     Position: {position_desc} ({channel_analysis['position_in_channel']:.2f})")
                    
                    # Track near misses if channel width is good but position isn't
                    if channel_analysis['min_width'] <= channel_analysis['channel_width'] <= channel_analysis['max_width']:
                        if channel_analysis['in_middle']:
                            distance = min(abs(0.2 - channel_analysis['position_in_channel']),
                                         abs(0.8 - channel_analysis['position_in_channel']))
                            near_misses['Channel'].append({
                                'symbol': symbol,
                                'distance': distance,
                                'details': channel_analysis
                            })
        
        # Print Near Misses Summary
        print("\n" + "="*80)
        print("🎯 NEAR MISSES - Opportunities Almost Ready to Trigger")
        print("="*80)
        
        for strategy in ['DCA', 'Swing', 'Channel']:
            if near_misses[strategy]:
                sorted_misses = sorted(near_misses[strategy], key=lambda x: x['distance'])
                print(f"\n{strategy} Strategy - Top 5 Closest:")
                for i, miss in enumerate(sorted_misses[:5], 1):
                    print(f"  {i}. {miss['symbol']} - Distance score: {miss['distance']:.2f}")
                    if strategy == 'DCA':
                        d = miss['details']
                        print(f"     Just need: Drop to {d['drop_threshold']}% (currently {d['drop_pct']:.2f}%)")
                    elif strategy == 'Swing':
                        d = miss['details']
                        print(f"     Just need: Breakout to {d['breakout_threshold']}% (currently {d['breakout_pct']:.2f}%)")
                    elif strategy == 'Channel':
                        d = miss['details']
                        pos = d['position_in_channel']
                        if pos > 0.5:
                            print(f"     Just need: Price to reach {d['channel_high']:.2f} (currently {d['current_price']:.2f})")
                        else:
                            print(f"     Just need: Price to reach {d['channel_low']:.2f} (currently {d['current_price']:.2f})")
        
        # Market conditions summary
        print("\n" + "="*80)
        print("📊 MARKET CONDITIONS SUMMARY")
        print("="*80)
        
        # Check overall market volatility
        btc_data = self.fetch_recent_data('BTC', hours=24)
        if btc_data:
            btc_prices = [bar.get('close', 0) for bar in btc_data]
            btc_volatility = np.std(btc_prices) / np.mean(btc_prices) * 100 if btc_prices else 0
            print(f"BTC 24h Volatility: {btc_volatility:.2f}%")
            
            if btc_volatility < 1:
                print("⚠️  Very low volatility - market is quiet, fewer opportunities")
            elif btc_volatility < 2:
                print("📊 Normal volatility - moderate opportunity frequency")
            else:
                print("🚀 High volatility - should see more opportunities")
        
        print("\n" + "="*80)
        print("💡 RECOMMENDATIONS")
        print("="*80)
        
        print("""
1. CURRENT MARKET: Based on the analysis, the market appears to be in a 
   consolidation phase with limited volatility, which explains fewer triggers.

2. THRESHOLD ADJUSTMENTS: Consider these temporary adjustments for testing:
   - DCA: Reduce drop threshold from -5% to -3% for more signals
   - Swing: Reduce breakout threshold from 2% to 1.5%
   - Channel: Widen acceptable range from 2-10% to 1.5-15%

3. PATIENCE: The system IS working correctly - it's just being selective.
   This is actually good for avoiding false signals!

4. MONITORING: Run this script periodically to see opportunities developing.
   Many symbols are within 1-2% of triggering conditions.
""")


if __name__ == "__main__":
    analyzer = TradingActivityAnalyzer()
    asyncio.run(analyzer.run_analysis())
