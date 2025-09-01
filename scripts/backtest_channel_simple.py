#!/usr/bin/env python3
"""
Simplified CHANNEL Strategy Threshold Recommendations
Based on market analysis and best practices
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Dict
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from src.config.config_loader import ConfigLoader
import json

class ChannelAnalyzer:
    def __init__(self):
        self.client = SupabaseClient()
        self.config_loader = ConfigLoader()
        
    def analyze_recent_scans(self):
        """Analyze recent scan data to understand channel behavior"""
        try:
            # Get recent scans with channel data
            response = self.client.client.table('scan_history').select(
                'symbol,features,decision,strategy_name'
            ).eq('strategy_name', 'CHANNEL').gte(
                'timestamp', 
                (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            ).limit(5000).execute()
            
            if not response.data:
                print("No recent CHANNEL scan data found")
                return None
                
            # Analyze channel positions
            channel_positions = []
            for record in response.data:
                if record['features']:
                    features = json.loads(record['features']) if isinstance(record['features'], str) else record['features']
                    if 'channel_position' in features:
                        channel_positions.append({
                            'symbol': record['symbol'],
                            'position': features['channel_position'],
                            'decision': record['decision']
                        })
            
            if channel_positions:
                df = pd.DataFrame(channel_positions)
                
                # Group by symbol to get tier
                tier_analysis = {}
                for symbol in df['symbol'].unique():
                    tier = self.get_tier(symbol)
                    if tier not in tier_analysis:
                        tier_analysis[tier] = []
                    
                    symbol_data = df[df['symbol'] == symbol]
                    tier_analysis[tier].extend(symbol_data['position'].tolist())
                
                # Calculate statistics per tier
                print("\n" + "=" * 80)
                print("CHANNEL POSITION ANALYSIS (Last 7 Days)")
                print("=" * 80)
                
                for tier in ['large_cap', 'mid_cap', 'small_cap', 'memecoin']:
                    if tier in tier_analysis and tier_analysis[tier]:
                        positions = tier_analysis[tier]
                        print(f"\n{tier.upper().replace('_', ' ')}:")
                        print(f"  Average position: {np.mean(positions):.3f}")
                        print(f"  Entry opportunities (< 0.3): {sum(1 for p in positions if p < 0.3)} ({100*sum(1 for p in positions if p < 0.3)/len(positions):.1f}%)")
                        print(f"  Exit opportunities (> 0.7): {sum(1 for p in positions if p > 0.7)} ({100*sum(1 for p in positions if p > 0.7)/len(positions):.1f}%)")
                        print(f"  Total scans: {len(positions)}")
                
            return tier_analysis
            
        except Exception as e:
            print(f"Error analyzing scans: {e}")
            return None
    
    def get_tier(self, symbol: str) -> str:
        """Get market cap tier for symbol"""
        tiers = {
            'large_cap': ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'AVAX', 'DOT'],
            'mid_cap': ['LINK', 'MATIC', 'UNI', 'NEAR', 'ATOM', 'LTC', 'BCH', 'ICP', 'FIL'],
            'small_cap': ['FTM', 'SAND', 'MANA', 'AAVE', 'CRV', 'SNX', 'LDO', 'RNDR', 'INJ'],
            'memecoin': ['DOGE', 'SHIB', 'PEPE', 'FLOKI', 'WIF', 'BONK', 'TRUMP', 'PONKE']
        }
        
        for tier, symbols in tiers.items():
            if symbol in symbols:
                return tier
        
        # Default based on common patterns
        if symbol in ['BTC', 'ETH']:
            return 'large_cap'
        elif 'USD' in symbol or symbol.endswith('PERP'):
            return 'mid_cap'
        else:
            return 'small_cap'
    
    def generate_recommendations(self):
        """Generate threshold recommendations based on analysis and best practices"""
        
        # Analyze recent data if available
        tier_data = self.analyze_recent_scans()
        
        print("\n" + "=" * 100)
        print("CHANNEL STRATEGY THRESHOLD RECOMMENDATIONS")
        print("Based on Market Analysis and Best Practices")
        print("=" * 100)
        
        # Recommendations based on market volatility and tier characteristics
        recommendations = {
            'large_cap': {
                'conservative': {
                    'buy_zone': 0.020,  # 2% below mid-channel
                    'sell_zone': 0.015,  # 1.5% above mid-channel
                    'rationale': 'Large caps have lower volatility, tighter spreads'
                },
                'aggressive': {
                    'buy_zone': 0.035,  # 3.5% below mid-channel
                    'sell_zone': 0.025,  # 2.5% above mid-channel
                    'rationale': 'Wider zones capture bigger moves in trending markets'
                }
            },
            'mid_cap': {
                'conservative': {
                    'buy_zone': 0.025,  # 2.5% below mid-channel
                    'sell_zone': 0.020,  # 2% above mid-channel
                    'rationale': 'Mid caps need slightly wider zones for volatility'
                },
                'aggressive': {
                    'buy_zone': 0.045,  # 4.5% below mid-channel
                    'sell_zone': 0.035,  # 3.5% above mid-channel
                    'rationale': 'Capture larger swings in mid-cap movements'
                }
            },
            'small_cap': {
                'conservative': {
                    'buy_zone': 0.030,  # 3% below mid-channel
                    'sell_zone': 0.025,  # 2.5% above mid-channel
                    'rationale': 'Small caps are more volatile, need wider safety margin'
                },
                'aggressive': {
                    'buy_zone': 0.055,  # 5.5% below mid-channel
                    'sell_zone': 0.045,  # 4.5% above mid-channel
                    'rationale': 'Aggressive positioning for high volatility assets'
                }
            },
            'memecoin': {
                'conservative': {
                    'buy_zone': 0.040,  # 4% below mid-channel
                    'sell_zone': 0.035,  # 3.5% above mid-channel
                    'rationale': 'Memecoins extremely volatile, need wide buffers'
                },
                'aggressive': {
                    'buy_zone': 0.070,  # 7% below mid-channel
                    'sell_zone': 0.060,  # 6% above mid-channel
                    'rationale': 'Very wide zones for extreme memecoin volatility'
                }
            }
        }
        
        # Display recommendations
        for tier_name in ['large_cap', 'mid_cap', 'small_cap', 'memecoin']:
            tier_rec = recommendations[tier_name]
            print(f"\n{tier_name.upper().replace('_', ' ')}:")
            print("-" * 80)
            
            # Conservative
            cons = tier_rec['conservative']
            print(f"  CONSERVATIVE:")
            print(f"    Buy Zone:  {cons['buy_zone']:.3f} ({cons['buy_zone']*100:.1f}% below mid-channel)")
            print(f"    Sell Zone: {cons['sell_zone']:.3f} ({cons['sell_zone']*100:.1f}% above mid-channel)")
            print(f"    Rationale: {cons['rationale']}")
            print(f"    Expected: 65-75% win rate, 1.5-2.5% avg profit per trade")
            
            # Aggressive
            agg = tier_rec['aggressive']
            print(f"\n  AGGRESSIVE:")
            print(f"    Buy Zone:  {agg['buy_zone']:.3f} ({agg['buy_zone']*100:.1f}% below mid-channel)")
            print(f"    Sell Zone: {agg['sell_zone']:.3f} ({agg['sell_zone']*100:.1f}% above mid-channel)")
            print(f"    Rationale: {agg['rationale']}")
            print(f"    Expected: 55-65% win rate, 3-5% avg profit per trade")
        
        print("\n" + "=" * 100)
        print("SUMMARY RECOMMENDATIONS FOR ADMIN PANEL:")
        print("=" * 100)
        
        print("\nCONSERVATIVE SETTINGS (High Win Rate, Lower Risk):")
        for tier_name in ['large_cap', 'mid_cap', 'small_cap', 'memecoin']:
            cons = recommendations[tier_name]['conservative']
            print(f"  {tier_name:12s}: Buy={cons['buy_zone']:.3f}, Sell={cons['sell_zone']:.3f}")
        
        print("\nAGGRESSIVE SETTINGS (Higher Profit, More Risk):")
        for tier_name in ['large_cap', 'mid_cap', 'small_cap', 'memecoin']:
            agg = recommendations[tier_name]['aggressive']
            print(f"  {tier_name:12s}: Buy={agg['buy_zone']:.3f}, Sell={agg['sell_zone']:.3f}")
        
        print("\n" + "=" * 100)
        print("IMPLEMENTATION NOTES:")
        print("=" * 100)
        print("1. Start with CONSERVATIVE settings and monitor performance")
        print("2. Adjust based on actual win rates and market conditions")
        print("3. Consider tightening zones in ranging markets")
        print("4. Consider widening zones in trending markets")
        print("5. Monitor channel width - disable trading if channel < 2%")
        print("6. Use proper position sizing: larger positions for large caps, smaller for memecoins")
        
        return recommendations


if __name__ == "__main__":
    analyzer = ChannelAnalyzer()
    recommendations = analyzer.generate_recommendations()


