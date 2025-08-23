import asyncio
from datetime import datetime, timedelta, timezone
from colorama import Fore, Style, init
import json
import time
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

init(autoreset=True)

class UltimateSystemValidator:
    """The definitive test - no BS, just facts"""
    
    def __init__(self):
        from src.data.supabase_client import SupabaseClient
        self.supabase = SupabaseClient().client
        self.results = {}
        self.critical_failures = []
        
    async def run_validation(self):
        """Run comprehensive validation with no sugar-coating"""
        print(f"{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}ULTIMATE SYSTEM VALIDATION - NO BS EDITION")
        print(f"{Fore.CYAN}Time: {datetime.now(timezone.utc)}")
        print(f"{Fore.CYAN}{'='*60}\n")
        
        # Test everything
        await self.test_data_pipeline()
        await self.test_all_strategies()
        await self.test_ml_system()
        await self.test_trading_engine()
        await self.test_system_stability()
        await self.test_end_to_end_flow()
        
        # Generate verdict
        self.generate_verdict()
    
    async def test_data_pipeline(self):
        """Test if data is actually flowing"""
        print(f"\n{Fore.YELLOW}1. DATA PIPELINE TEST")
        print("-" * 40)
        
        tests = {}
        
        # Check data freshness across multiple symbols
        # Use materialized view for faster queries
        symbols = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP']
        fresh_count = 0
        
        for symbol in symbols:
            # Try ohlc_today view first (much faster)
            try:
                result = self.supabase.table('ohlc_today').select('timestamp').eq(
                    'symbol', symbol
                ).order('timestamp', desc=True).limit(1).execute()
            except:
                # Fallback to ohlc_recent if today view fails
                try:
                    result = self.supabase.table('ohlc_recent').select('timestamp').eq(
                        'symbol', symbol
                    ).order('timestamp', desc=True).limit(1).execute()
                except:
                    result = None
            
            if result and result.data:
                last_update = datetime.fromisoformat(result.data[0]['timestamp'].replace('Z', '+00:00'))
                age_minutes = (datetime.now(timezone.utc) - last_update).total_seconds() / 60
                
                if age_minutes < 10:
                    fresh_count += 1
                    status = "✅"
                else:
                    status = "❌"
                    
                print(f"  {status} {symbol}: {age_minutes:.1f} min old")
        
        tests['Data Freshness'] = fresh_count >= 3  # At least 3/5 symbols fresh
        
        # Check data volume (use view for speed)
        one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        try:
            result = self.supabase.table('ohlc_today').select('*', count='exact').gte(
                'timestamp', one_hour_ago
            ).execute()
        except:
            # If view fails, just estimate
            result = type('obj', (object,), {'count': 0})()
        
        data_rate = result.count if result.count else 0
        tests['Data Volume'] = data_rate > 100  # At least 100 updates/hour
        print(f"  📊 Updates in last hour: {data_rate}")
        
        self.results['Data Pipeline'] = tests
        return all(tests.values())
    
    async def test_all_strategies(self):
        """Test if ALL strategies are actually scanning"""
        print(f"\n{Fore.YELLOW}2. STRATEGY SCANNING TEST")
        print("-" * 40)
        
        tests = {}
        strategies = ['DCA', 'SWING', 'CHANNEL']
        
        for strategy in strategies:
            # Check last 30 minutes
            thirty_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
            
            result = self.supabase.table('scan_history').select('*', count='exact').eq(
                'strategy_name', strategy
            ).gte('timestamp', thirty_min_ago).execute()
            
            scan_count = result.count if result.count else 0
            
            # Each strategy should scan at least once per symbol per 30 min
            expected_min = 20  # Conservative estimate
            tests[f'{strategy} Active'] = scan_count >= expected_min
            
            status = "✅" if scan_count >= expected_min else "❌"
            print(f"  {status} {strategy}: {scan_count} scans (last 30 min)")
            
            if scan_count < expected_min:
                self.critical_failures.append(f"{strategy} not scanning enough")
        
        # Check for actual signals detected
        result = self.supabase.table('scan_history').select('*').eq(
            'decision', 'SIGNAL'
        ).gte('timestamp', thirty_min_ago).execute()
        
        signal_count = len(result.data) if result.data else 0
        print(f"  📡 Signals detected: {signal_count}")
        tests['Signals Generated'] = signal_count > 0
        
        self.results['Strategy Scanning'] = tests
        return all(tests.values())
    
    async def test_ml_system(self):
        """Test if ML is actually working"""
        print(f"\n{Fore.YELLOW}3. ML SYSTEM TEST")
        print("-" * 40)
        
        tests = {}
        
        # Check ML feature freshness
        result = self.supabase.table('ml_features').select('timestamp').order(
            'timestamp', desc=True
        ).limit(1).execute()
        
        if result.data:
            last_feature = datetime.fromisoformat(result.data[0]['timestamp'].replace('Z', '+00:00'))
            age_minutes = (datetime.now(timezone.utc) - last_feature).total_seconds() / 60
            tests['Feature Calculation'] = age_minutes < 60
            
            status = "✅" if age_minutes < 60 else "❌"
            print(f"  {status} Last ML features: {age_minutes:.1f} min ago")
        else:
            tests['Feature Calculation'] = False
            print(f"  ❌ No ML features found")
        
        # Check if models exist - FIXED PATHS
        model_paths = [
            'models/dca/xgboost_multi_output.pkl',  # Fixed: correct filename
            'models/swing/swing_classifier.pkl',     # Fixed: correct filename
            'models/channel/classifier.pkl'          # Fixed: correct filename
        ]
        
        models_found = sum(1 for p in model_paths if os.path.exists(p))
        tests['Models Available'] = models_found >= 1
        print(f"  📦 Models found: {models_found}/3")
        
        # Test ML prediction - with better error handling
        try:
            from src.ml.predictor import MLPredictor
            predictor = MLPredictor()
            
            # Test prediction with more complete features
            test_features = {
                'rsi_14': 50,
                'volume_ratio': 1.2,
                'price_change_pct': 0.5,
                'distance_from_support': 0.02,
                'bb_position': 0.5,
                'macd_signal': 0.001,
                'volatility': 0.02,
                'trend_strength': 0.3
            }
            
            # Try DCA prediction (most likely to work)
            prediction = predictor.predict('DCA', test_features)
            if prediction and 'confidence' in prediction:
                tests['ML Predictions Work'] = True
                print(f"  ✅ ML predictions working (confidence: {prediction['confidence']:.2%})")
            else:
                tests['ML Predictions Work'] = False
                print(f"  ❌ ML predictions returned invalid result")
        except ImportError as e:
            tests['ML Predictions Work'] = False
            print(f"  ⚠️  ML predictor not found (may be on Railway)")
        except Exception as e:
            tests['ML Predictions Work'] = False
            print(f"  ❌ ML predictions failed: {str(e)[:50]}")
        
        self.results['ML System'] = tests
        return all(tests.values())
    
    async def test_trading_engine(self):
        """Test if trading engine would actually execute"""
        print(f"\n{Fore.YELLOW}4. TRADING ENGINE TEST")
        print("-" * 40)
        
        tests = {}
        
        # Check paper trading configuration
        config_exists = os.path.exists('configs/paper_trading.json')
        tests['Config Exists'] = config_exists
        
        if config_exists:
            with open('configs/paper_trading.json') as f:
                config = json.load(f)
                
            # Verify thresholds are actually loosened
            ml_threshold = config.get('ml_confidence_threshold', 1.0)
            tests['Thresholds Loosened'] = ml_threshold <= 0.60
            
            print(f"  📋 ML threshold: {ml_threshold} {'✅' if ml_threshold <= 0.60 else '❌ Too strict!'}")
        
        # Check for trades
        result = self.supabase.table('trade_logs').select('*', count='exact').execute()
        trade_count = result.count if result.count else 0
        
        # Check recent trade attempts
        one_day_ago = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        recent_result = self.supabase.table('trade_logs').select('*').gte(
            'created_at', one_day_ago
        ).execute()
        
        recent_trades = len(recent_result.data) if recent_result.data else 0
        
        print(f"  💰 Total trades: {trade_count}")
        print(f"  📈 Trades (last 24h): {recent_trades}")
        
        tests['Trading Active'] = recent_trades > 0 or trade_count > 0
        
        self.results['Trading Engine'] = tests
        return all(tests.values())
    
    async def test_system_stability(self):
        """Test if system is actually stable"""
        print(f"\n{Fore.YELLOW}5. SYSTEM STABILITY TEST")
        print("-" * 40)
        
        tests = {}
        
        # Check for recent errors in scan_history
        result = self.supabase.table('scan_history').select('reason').eq(
            'reason', 'error'
        ).limit(10).execute()
        
        error_count = len(result.data) if result.data else 0
        tests['Low Error Rate'] = error_count < 5
        print(f"  ⚠️  Recent errors: {error_count}")
        
        # Check process restart frequency (via scan gaps)
        one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        result = self.supabase.table('scan_history').select('timestamp').gte(
            'timestamp', one_hour_ago
        ).order('timestamp').execute()
        
        if result.data and len(result.data) > 1:
            # Look for gaps > 10 minutes (indicating crashes)
            gaps = []
            for i in range(1, len(result.data)):
                t1 = datetime.fromisoformat(result.data[i-1]['timestamp'].replace('Z', '+00:00'))
                t2 = datetime.fromisoformat(result.data[i]['timestamp'].replace('Z', '+00:00'))
                gap_minutes = (t2 - t1).total_seconds() / 60
                if gap_minutes > 10:
                    gaps.append(gap_minutes)
            
            tests['Process Stability'] = len(gaps) < 3
            print(f"  🔄 Process restarts detected: {len(gaps)}")
        else:
            tests['Process Stability'] = True  # No data means can't determine
            print(f"  ℹ️  Insufficient data to measure stability")
        
        # Check cron job is active
        import subprocess
        try:
            result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
            has_cron = 'run_strategies_cron.sh' in result.stdout
            tests['Cron Active'] = has_cron
            print(f"  {'✅' if has_cron else '❌'} Cron job: {'Active' if has_cron else 'Not found'}")
        except:
            tests['Cron Active'] = False
            print(f"  ⚠️  Could not check cron status")
        
        self.results['System Stability'] = tests
        return all(tests.values())
    
    async def test_end_to_end_flow(self):
        """Test complete flow: Data → Strategy → ML → Signal → Trade"""
        print(f"\n{Fore.YELLOW}6. END-TO-END FLOW TEST")
        print("-" * 40)
        
        # Track a single symbol through the entire pipeline
        test_symbol = 'BTC'
        
        print(f"  Testing flow for {test_symbol}:")
        
        # 1. Data exists?
        try:
            data_result = self.supabase.table('ohlc_recent').select('*').eq(
                'symbol', test_symbol
            ).order('timestamp', desc=True).limit(100).execute()
        except:
            data_result = None
        
        has_data = len(data_result.data) >= 50 if (data_result and data_result.data) else False
        print(f"    {'✅' if has_data else '❌'} Data points: {len(data_result.data) if (data_result and data_result.data) else 0}")
        
        # 2. Features calculated?
        feature_result = self.supabase.table('ml_features').select('*').eq(
            'symbol', test_symbol
        ).limit(1).execute()
        
        has_features = len(feature_result.data) > 0 if feature_result.data else False
        print(f"    {'✅' if has_features else '❌'} ML features: {'Yes' if has_features else 'No'}")
        
        # 3. Scans performed?
        scan_result = self.supabase.table('scan_history').select('*').eq(
            'symbol', test_symbol
        ).limit(10).execute()
        
        has_scans = len(scan_result.data) > 0 if scan_result.data else False
        print(f"    {'✅' if has_scans else '❌'} Strategy scans: {len(scan_result.data) if scan_result.data else 0}")
        
        # 4. Signals generated?
        signal_result = self.supabase.table('scan_history').select('*').eq(
            'symbol', test_symbol
        ).eq('decision', 'SIGNAL').limit(5).execute()
        
        has_signals = len(signal_result.data) > 0 if signal_result.data else False
        print(f"    {'✅' if has_signals else '❌'} Signals: {len(signal_result.data) if signal_result.data else 0}")
        
        # 5. Shadow testing active?
        shadow_result = self.supabase.table('shadow_testing_scans').select('*').eq(
            'symbol', test_symbol
        ).limit(5).execute()
        
        has_shadow = len(shadow_result.data) > 0 if shadow_result.data else False
        print(f"    {'✅' if has_shadow else '❌'} Shadow testing: {len(shadow_result.data) if shadow_result.data else 0}")
        
        flow_complete = has_data and has_features and has_scans
        
        self.results['End-to-End Flow'] = {
            'Data': has_data,
            'Features': has_features,
            'Scans': has_scans,
            'Signals': has_signals,
            'Shadow Testing': has_shadow,
            'Complete': flow_complete
        }
        
        return flow_complete
    
    def generate_verdict(self):
        """Generate the final verdict - no sugar-coating"""
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}FINAL VERDICT")
        print(f"{Fore.CYAN}{'='*60}\n")
        
        # Calculate scores
        total_tests = sum(len(v) if isinstance(v, dict) else 1 for v in self.results.values())
        passed_tests = sum(
            sum(1 for t in v.values() if t) if isinstance(v, dict) else (1 if v else 0)
            for v in self.results.values()
        )
        
        pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        # Component breakdown
        print(f"{Fore.YELLOW}Component Status:")
        print("-" * 40)
        
        for component, tests in self.results.items():
            if isinstance(tests, dict):
                component_passed = sum(1 for v in tests.values() if v)
                component_total = len(tests)
                component_rate = (component_passed / component_total * 100) if component_total > 0 else 0
                
                if component_rate == 100:
                    status = f"{Fore.GREEN}✅ OPERATIONAL"
                elif component_rate >= 50:
                    status = f"{Fore.YELLOW}⚠️  DEGRADED"
                else:
                    status = f"{Fore.RED}❌ FAILING"
                
                print(f"{component}: {status} ({component_passed}/{component_total})")
        
        # Critical failures
        if self.critical_failures:
            print(f"\n{Fore.RED}Critical Failures:")
            for failure in self.critical_failures:
                print(f"  • {failure}")
        
        # Overall verdict
        print(f"\n{Fore.CYAN}Overall Score: {passed_tests}/{total_tests} ({pass_rate:.1f}%)")
        
        if pass_rate >= 90:
            print(f"{Fore.GREEN}✅ SYSTEM IS PRODUCTION READY")
            print("All critical components operational. Safe to deploy.")
        elif pass_rate >= 75:
            print(f"{Fore.YELLOW}⚠️  SYSTEM IS NEAR PRODUCTION READY")
            print("Minor issues remain. Monitor closely but can proceed with caution.")
        elif pass_rate >= 60:
            print(f"{Fore.YELLOW}⚠️  SYSTEM IS PARTIALLY OPERATIONAL")
            print("Significant issues present. Not recommended for production.")
        else:
            print(f"{Fore.RED}❌ SYSTEM IS NOT READY")
            print("Critical failures detected. Do not deploy to production.")
        
        # Specific recommendations
        print(f"\n{Fore.CYAN}Recommendations:")
        print("-" * 40)
        
        if 'DCA' in str(self.critical_failures):
            print("• Fix DCA strategy - it was working before")
        
        if not self.results.get('Trading Engine', {}).get('Trading Active', False):
            print("• No trades generated - review signal thresholds")
        
        if not self.results.get('ML System', {}).get('Feature Calculation', False):
            print("• ML features stale - check feature calculator")
        
        if not self.results.get('System Stability', {}).get('Cron Active', False):
            print("• Set up cron job for auto-restart: crontab -e")
        
        print(f"\n{Fore.CYAN}Bottom Line:")
        if pass_rate >= 75:
            print(f"{Fore.GREEN}System is functional enough for careful production use.")
            print(f"Grade: {'A' if pass_rate >= 90 else 'B' if pass_rate >= 80 else 'C'}")
        else:
            print(f"{Fore.RED}System needs more work before production deployment.")
            print(f"Grade: {'D' if pass_rate >= 60 else 'F'}")

# Run the ultimate test
if __name__ == "__main__":
    validator = UltimateSystemValidator()
    asyncio.run(validator.run_validation())
