"""
Comprehensive SWING strategy analysis - why no trades are triggering.
"""
import os
from datetime import datetime, timedelta, timezone
from supabase import create_client
from dotenv import load_dotenv
import pandas as pd
import numpy as np
import json

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def analyze_current_swing_config():
    """Show current SWING configuration."""
    print("="*80)
    print("CURRENT SWING CONFIGURATION")
    print("="*80)
    
    with open('configs/paper_trading_config_unified.json', 'r') as f:
        config = json.load(f)
    
    swing_config = config['strategies']['SWING']
    
    print("\nDefault Detection Thresholds:")
    for key, value in swing_config['detection_thresholds'].items():
        print(f"  {key}: {value}")
    
    print("\nTiered Detection Thresholds:")
    if 'detection_thresholds_by_tier' in swing_config:
        for tier, settings in swing_config['detection_thresholds_by_tier'].items():
            print(f"\n  {tier.upper()}:")
            print(f"    Breakout threshold: {settings.get('breakout_threshold', 'N/A')} (price above 20-day high)")
            print(f"    Volume surge: {settings.get('volume_surge', 'N/A')}x average")
            print(f"    RSI range: {settings.get('rsi_min', 'N/A')}-{settings.get('rsi_max', 'N/A')}")
            print(f"    Min score: {settings.get('min_score', 'N/A')}")

def analyze_swing_scans():
    """Analyze SWING scan history to see why trades aren't triggering."""
    
    print("\n" + "="*80)
    print("SWING SCAN HISTORY ANALYSIS (Last 30 Days)")
    print("="*80)
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    
    # Get SWING scans
    response = supabase.table('scan_history').select('*').eq(
        'strategy_name', 'SWING'
    ).gte('timestamp', cutoff.isoformat()).limit(5000).execute()
    
    if not response.data:
        print("\nNo SWING scans found in last 30 days - strategy may not be scanning")
        return None
    
    scans = pd.DataFrame(response.data)
    print(f"\nFound {len(scans)} SWING scans in last 30 days")
    
    # Check for signals
    signals = scans[scans['signal_detected'] == True] if 'signal_detected' in scans.columns else pd.DataFrame()
    print(f"Signals detected: {len(signals)}")
    
    # Analyze signal strength distribution
    if 'signal_strength' in scans.columns:
        strengths = scans['signal_strength'].dropna()
        if len(strengths) > 0:
            print(f"\nSignal Strength Distribution:")
            print(f"  Max: {strengths.max():.3f}")
            print(f"  75th percentile: {strengths.quantile(0.75):.3f}")
            print(f"  Median: {strengths.median():.3f}")
            print(f"  25th percentile: {strengths.quantile(0.25):.3f}")
            print(f"  Min: {strengths.min():.3f}")
            print(f"  Signals > 0.5: {(strengths > 0.5).sum()}")
    
    # Parse features to understand what's happening
    breakouts = []
    volume_surges = []
    rsi_values = []
    scores = []
    
    for idx, row in scans.iterrows():
        if row.get('features'):
            features = row['features'] if isinstance(row['features'], dict) else json.loads(row['features'])
            
            if 'price_vs_20d_high' in features:
                breakouts.append(features['price_vs_20d_high'])
            if 'volume_surge' in features:
                volume_surges.append(features['volume_surge'])
            if 'rsi' in features:
                rsi_values.append(features['rsi'])
            if 'swing_score' in features:
                scores.append(features['swing_score'])
    
    if breakouts:
        breakouts = np.array(breakouts)
        print(f"\nPrice vs 20-day High (1.0 = at high, >1.0 = breakout):")
        print(f"  Max: {breakouts.max():.3f}")
        print(f"  95th percentile: {np.percentile(breakouts, 95):.3f}")
        print(f"  90th percentile: {np.percentile(breakouts, 90):.3f}")
        print(f"  75th percentile: {np.percentile(breakouts, 75):.3f}")
        print(f"  Median: {np.median(breakouts):.3f}")
        print(f"  Above 1.01 (current threshold): {(breakouts > 1.01).sum()} ({(breakouts > 1.01).sum()/len(breakouts)*100:.1f}%)")
        print(f"  Above 1.005: {(breakouts > 1.005).sum()} ({(breakouts > 1.005).sum()/len(breakouts)*100:.1f}%)")
        print(f"  Above 1.00: {(breakouts > 1.00).sum()} ({(breakouts > 1.00).sum()/len(breakouts)*100:.1f}%)")
    
    if volume_surges:
        surges = np.array(volume_surges)
        print(f"\nVolume Surge Distribution (vs average):")
        print(f"  Max: {surges.max():.2f}x")
        print(f"  75th percentile: {np.percentile(surges, 75):.2f}x")
        print(f"  Median: {np.median(surges):.2f}x")
        print(f"  Above 1.3x (threshold): {(surges > 1.3).sum()} ({(surges > 1.3).sum()/len(surges)*100:.1f}%)")
        print(f"  Above 1.0x: {(surges > 1.0).sum()} ({(surges > 1.0).sum()/len(surges)*100:.1f}%)")
    
    if rsi_values:
        rsis = np.array(rsi_values)
        print(f"\nRSI Distribution:")
        print(f"  Max: {rsis.max():.1f}")
        print(f"  75th percentile: {np.percentile(rsis, 75):.1f}")
        print(f"  Median: {np.median(rsis):.1f}")
        print(f"  25th percentile: {np.percentile(rsis, 25):.1f}")
        print(f"  In range 45-75: {((rsis >= 45) & (rsis <= 75)).sum()} ({((rsis >= 45) & (rsis <= 75)).sum()/len(rsis)*100:.1f}%)")
    
    return scans

def analyze_market_conditions():
    """Analyze recent market conditions to understand SWING context."""
    
    print("\n" + "="*80)
    print("MARKET CONDITIONS ANALYSIS (Last 30 Days)")
    print("="*80)
    
    # Get BTC price data as market proxy
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    
    response = supabase.table('ohlc_data').select('*').eq(
        'symbol', 'BTC'
    ).eq('timeframe', '1h').gte(
        'timestamp', cutoff.isoformat()
    ).order('timestamp').execute()
    
    if response.data:
        btc = pd.DataFrame(response.data)
        btc['timestamp'] = pd.to_datetime(btc['timestamp'])
        
        # Calculate metrics
        start_price = btc['close'].iloc[0]
        end_price = btc['close'].iloc[-1]
        high_price = btc['high'].max()
        low_price = btc['low'].min()
        
        total_return = ((end_price - start_price) / start_price) * 100
        max_drawdown = ((low_price - high_price) / high_price) * 100
        
        print(f"\nBTC Performance (Market Proxy):")
        print(f"  30-day return: {total_return:+.1f}%")
        print(f"  Max drawdown: {max_drawdown:.1f}%")
        print(f"  Current vs 30d high: {((end_price - high_price) / high_price * 100):.1f}%")
        
        # Check for breakouts
        rolling_high = btc['high'].rolling(window=480).max()  # 20 days of hourly data
        breakouts = btc[btc['close'] > rolling_high * 1.01]
        
        print(f"\n  Breakout days (>1% above 20d high): {len(breakouts) / 24:.0f} days")
        
        if total_return > 10:
            print("\n  Market Status: BULLISH - Good for SWING trades")
        elif total_return > 0:
            print("\n  Market Status: NEUTRAL/MILD BULL - Limited SWING opportunities")
        else:
            print("\n  Market Status: BEARISH - SWING should be active")
    else:
        print("\nNo BTC data found for market analysis")

def analyze_swing_paper_trades():
    """Check if any SWING trades have been attempted."""
    
    print("\n" + "="*80)
    print("SWING PAPER TRADING ATTEMPTS")
    print("="*80)
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    
    response = supabase.table('paper_trades').select('*').eq(
        'strategy_name', 'SWING'
    ).gte('created_at', cutoff.isoformat()).execute()
    
    if response.data:
        trades = pd.DataFrame(response.data)
        print(f"\nFound {len(trades)} SWING trades in last 30 days")
        
        # Analyze by symbol
        print("\nTrades by symbol:")
        for symbol, count in trades['symbol'].value_counts().head(10).items():
            print(f"  {symbol}: {count}")
    else:
        print("\nNo SWING trades found in last 30 days")
        print("Strategy is not triggering any trades!")

def generate_recommendations():
    """Generate recommendations for SWING strategy."""
    
    print("\n" + "="*80)
    print("SWING STRATEGY RECOMMENDATIONS")
    print("="*80)
    
    print("""
The SWING strategy is designed for momentum/breakout trading, which requires:
1. Price breaking above recent highs (20-day high)
2. Volume surge confirmation
3. Proper RSI positioning (not overbought)

### LIKELY ISSUES:

1. **Breakout Threshold Too High (1.01 = 1% above high)**
   - In mild bull markets, prices rarely break 1% above highs
   - Most breakouts are 0.5-0.8% initially
   
2. **Volume Requirements Too Strict**
   - 1.3x volume surge is significant
   - Many valid breakouts have 1.1-1.2x volume

3. **Market Conditions Not Favorable**
   - SWING works best in trending markets
   - Current market may be ranging/consolidating

### RECOMMENDED ADJUSTMENTS:

#### Option 1: AGGRESSIVE (Generate Signals in Current Market)
```json
{
  "large_cap": {
    "breakout_threshold": 1.003,  // 0.3% above high (was 1.008)
    "volume_surge": 1.1,          // (was 1.2)
    "rsi_min": 40,                // (was 45)
    "rsi_max": 80,                // (was 75)
    "min_score": 30               // (was 35)
  },
  "mid_cap": {
    "breakout_threshold": 1.005,  // 0.5% above high (was 1.01)
    "volume_surge": 1.15,         // (was 1.3)
    "rsi_min": 40,
    "rsi_max": 80,
    "min_score": 35               // (was 40)
  },
  "small_cap": {
    "breakout_threshold": 1.008,  // 0.8% above high (was 1.015)
    "volume_surge": 1.2,          // (was 1.4)
    "rsi_min": 35,                // (was 40)
    "rsi_max": 85,                // (was 80)
    "min_score": 40               // (was 45)
  },
  "memecoin": {
    "breakout_threshold": 1.01,   // 1% above high (was 1.02)
    "volume_surge": 1.3,          // (was 1.5)
    "rsi_min": 30,                // (was 35)
    "rsi_max": 90,
    "min_score": 45               // (was 50)
  }
}
```

#### Option 2: MODERATE (Balanced Approach)
- Lower breakout thresholds by 0.5% across the board
- Reduce volume requirements by 0.1-0.2x
- Widen RSI ranges slightly

#### Option 3: CONSIDER DISABLING
- If market is ranging/consolidating, SWING won't work well
- Focus on CHANNEL and DCA strategies
- Re-enable when clear trends emerge

### TESTING APPROACH:
1. Start with aggressive settings for 1 week
2. Monitor if signals are generated
3. Check signal quality (do prices continue up after breakout?)
4. Adjust based on results
""")

if __name__ == "__main__":
    analyze_current_swing_config()
    scans = analyze_swing_scans()
    analyze_market_conditions()
    analyze_swing_paper_trades()
    generate_recommendations()
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print("""
SWING strategy is not triggering because:
1. Breakout thresholds are too high for current market conditions
2. We're likely in a ranging/mild bull market, not strong trending
3. Volume requirements may be too strict

To generate SWING signals, you need to either:
- Lower breakout thresholds significantly (1.01 → 1.003-1.005)
- Wait for stronger trending market conditions
- Consider if SWING is appropriate for current market

Since you want ML data, I recommend trying the aggressive settings temporarily.
""")
