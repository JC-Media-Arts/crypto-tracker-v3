"""
Shadow Performance Analyzer
Aggregates shadow outcomes, calculates performance metrics, and generates recommendations
"""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from decimal import Decimal
from loguru import logger
import json
import numpy as np
import pandas as pd
from scipy import stats
from dataclasses import dataclass

from src.config.shadow_config import ShadowConfig


@dataclass
class PerformanceMetrics:
    """Performance metrics for a shadow variation"""
    variation_name: str
    timeframe: str
    strategy_name: str
    total_opportunities: int
    trades_taken: int
    trades_completed: int
    wins: int
    losses: int
    timeouts: int
    win_rate: float
    avg_pnl_percentage: float
    total_pnl_percentage: float
    best_trade_pnl: float
    worst_trade_pnl: float
    sharpe_ratio: float
    max_drawdown: float
    avg_hold_hours: float
    outperformance_vs_champion: float
    confidence_level: str  # 'HIGH', 'MEDIUM', 'LOW'
    statistical_significance: float  # p-value


@dataclass
class AdjustmentRecommendation:
    """Recommended parameter adjustment"""
    strategy_name: str
    parameter_name: str
    current_value: float
    recommended_value: float
    variation_source: str
    confidence_level: str
    evidence_trades: int
    outperformance: float
    p_value: float
    reason: str


class ShadowAnalyzer:
    """
    Analyzes shadow performance and generates adjustment recommendations
    """
    
    def __init__(self, supabase_client):
        """
        Initialize the shadow analyzer
        
        Args:
            supabase_client: Supabase client for database operations
        """
        self.supabase = supabase_client
        self.timeframes = ['24h', '3d', '7d', '30d']
        self.min_trades_for_analysis = 10
        
    async def analyze_performance(self) -> Dict[str, List[PerformanceMetrics]]:
        """
        Main analysis function - calculates performance for all variations
        
        Returns:
            Dictionary of performance metrics by timeframe
        """
        performance_by_timeframe = {}
        
        try:
            for timeframe in self.timeframes:
                metrics = await self._calculate_timeframe_performance(timeframe)
                performance_by_timeframe[timeframe] = metrics
                
                # Save to database
                for metric in metrics:
                    await self._save_performance_metrics(metric)
                    
            logger.info(f"Analyzed performance for {len(self.timeframes)} timeframes")
            
        except Exception as e:
            logger.error(f"Error analyzing performance: {e}")
            
        return performance_by_timeframe
    
    async def _calculate_timeframe_performance(self, timeframe: str) -> List[PerformanceMetrics]:
        """
        Calculate performance metrics for a specific timeframe
        """
        metrics_list = []
        
        # Get time cutoff
        hours = self._timeframe_to_hours(timeframe)
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        try:
            # Get all variations
            variations = await self._get_active_variations()
            
            for variation in variations:
                # Calculate for overall
                overall_metrics = await self._calculate_variation_performance(
                    variation_name=variation,
                    strategy_name='OVERALL',
                    cutoff_time=cutoff_time,
                    timeframe=timeframe
                )
                if overall_metrics:
                    metrics_list.append(overall_metrics)
                
                # Calculate per strategy
                for strategy in ['DCA', 'SWING', 'CHANNEL']:
                    strategy_metrics = await self._calculate_variation_performance(
                        variation_name=variation,
                        strategy_name=strategy,
                        cutoff_time=cutoff_time,
                        timeframe=timeframe
                    )
                    if strategy_metrics:
                        metrics_list.append(strategy_metrics)
                        
        except Exception as e:
            logger.error(f"Error calculating {timeframe} performance: {e}")
            
        return metrics_list
    
    async def _calculate_variation_performance(self,
                                              variation_name: str,
                                              strategy_name: str,
                                              cutoff_time: datetime,
                                              timeframe: str) -> Optional[PerformanceMetrics]:
        """
        Calculate performance metrics for a specific variation
        """
        try:
            # Get shadow outcomes for this variation
            query = self.supabase.table('shadow_outcomes')\
                .select('*, shadow_variations!inner(*)')\
                .eq('shadow_variations.variation_name', variation_name)\
                .gte('evaluated_at', cutoff_time.isoformat())
            
            if strategy_name != 'OVERALL':
                # Join with scan_history to filter by strategy
                query = query.eq('shadow_variations.scan_history.strategy_name', strategy_name)
            
            result = query.execute()
            
            if not result.data or len(result.data) < self.min_trades_for_analysis:
                return None
            
            outcomes = result.data
            
            # Calculate metrics
            completed = [o for o in outcomes if o['outcome_status'] != 'PENDING']
            if not completed:
                return None
            
            wins = [o for o in completed if o['outcome_status'] == 'WIN']
            losses = [o for o in completed if o['outcome_status'] == 'LOSS']
            timeouts = [o for o in completed if o['outcome_status'] == 'TIMEOUT']
            
            pnl_values = [float(o['pnl_percentage']) for o in completed]
            hold_times = [float(o['actual_hold_hours']) for o in completed if o['actual_hold_hours']]
            
            # Calculate statistics
            win_rate = len(wins) / len(completed) if completed else 0
            avg_pnl = np.mean(pnl_values) if pnl_values else 0
            total_pnl = np.sum(pnl_values) if pnl_values else 0
            
            # Calculate Sharpe ratio (annualized)
            if len(pnl_values) > 1:
                returns_std = np.std(pnl_values)
                if returns_std > 0:
                    # Assuming daily returns, annualize with sqrt(365)
                    sharpe_ratio = (avg_pnl / returns_std) * np.sqrt(365)
                else:
                    sharpe_ratio = 0
            else:
                sharpe_ratio = 0
            
            # Calculate max drawdown
            cumulative_returns = np.cumsum(pnl_values) if pnl_values else [0]
            running_max = np.maximum.accumulate(cumulative_returns)
            drawdown = (cumulative_returns - running_max) / (running_max + 100)  # Add 100 to avoid division by zero
            max_drawdown = np.min(drawdown) if len(drawdown) > 0 else 0
            
            # Get champion performance for comparison
            champion_performance = await self._get_champion_performance(strategy_name, timeframe)
            outperformance = 0
            p_value = 1.0
            
            if champion_performance and variation_name != 'CHAMPION':
                outperformance = win_rate - champion_performance['win_rate']
                
                # Calculate statistical significance
                if len(completed) >= 30:  # Need sufficient samples
                    # Use binomial test for win rate difference
                    p_value = self._calculate_significance(
                        wins_a=len(wins),
                        total_a=len(completed),
                        wins_b=champion_performance['wins'],
                        total_b=champion_performance['total']
                    )
            
            # Determine confidence level
            confidence_level = self._determine_confidence_level(
                trade_count=len(completed),
                outperformance=outperformance,
                p_value=p_value,
                days=self._timeframe_to_days(timeframe)
            )
            
            return PerformanceMetrics(
                variation_name=variation_name,
                timeframe=timeframe,
                strategy_name=strategy_name,
                total_opportunities=len(outcomes),
                trades_taken=len([o for o in outcomes if o.get('shadow_variations', {}).get('would_take_trade')]),
                trades_completed=len(completed),
                wins=len(wins),
                losses=len(losses),
                timeouts=len(timeouts),
                win_rate=win_rate,
                avg_pnl_percentage=avg_pnl,
                total_pnl_percentage=total_pnl,
                best_trade_pnl=max(pnl_values) if pnl_values else 0,
                worst_trade_pnl=min(pnl_values) if pnl_values else 0,
                sharpe_ratio=sharpe_ratio,
                max_drawdown=max_drawdown,
                avg_hold_hours=np.mean(hold_times) if hold_times else 0,
                outperformance_vs_champion=outperformance,
                confidence_level=confidence_level,
                statistical_significance=p_value
            )
            
        except Exception as e:
            logger.error(f"Error calculating performance for {variation_name}: {e}")
            return None
    
    async def generate_recommendations(self) -> List[AdjustmentRecommendation]:
        """
        Generate parameter adjustment recommendations based on shadow performance
        
        Returns:
            List of adjustment recommendations
        """
        recommendations = []
        
        try:
            # Get recent performance (last 3 days for stability)
            performance = await self._calculate_timeframe_performance('3d')
            
            # Group by strategy
            by_strategy = {}
            for metric in performance:
                if metric.strategy_name != 'OVERALL':
                    if metric.strategy_name not in by_strategy:
                        by_strategy[metric.strategy_name] = []
                    by_strategy[metric.strategy_name].append(metric)
            
            # Find best performers per strategy
            for strategy, metrics in by_strategy.items():
                # Sort by outperformance
                metrics.sort(key=lambda x: x.outperformance_vs_champion, reverse=True)
                
                # Check top performer
                if metrics and metrics[0].outperformance_vs_champion > 0:
                    best = metrics[0]
                    
                    # Generate recommendations based on variation type
                    recs = await self._generate_variation_recommendations(
                        best_performer=best,
                        strategy=strategy
                    )
                    recommendations.extend(recs)
            
            # Sort recommendations by confidence and outperformance
            recommendations.sort(
                key=lambda x: (
                    self._confidence_to_score(x.confidence_level),
                    x.outperformance
                ),
                reverse=True
            )
            
            # Limit to top 3 recommendations
            recommendations = recommendations[:3]
            
            logger.info(f"Generated {len(recommendations)} adjustment recommendations")
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            
        return recommendations
    
    async def _generate_variation_recommendations(self,
                                                 best_performer: PerformanceMetrics,
                                                 strategy: str) -> List[AdjustmentRecommendation]:
        """
        Generate specific recommendations based on the best performing variation
        """
        recommendations = []
        
        try:
            # Get current production parameters
            current_params = await self._get_current_parameters(strategy)
            
            # Get variation configuration
            variation_config = ShadowConfig.VARIATIONS.get(best_performer.variation_name)
            if not variation_config:
                return recommendations
            
            # Generate recommendations based on variation type
            if best_performer.variation_name == 'BEAR_MARKET':
                if best_performer.confidence_level in ['HIGH', 'MEDIUM']:
                    recommendations.append(AdjustmentRecommendation(
                        strategy_name=strategy,
                        parameter_name='confidence_threshold',
                        current_value=current_params.get('min_confidence', 0.60),
                        recommended_value=0.55,
                        variation_source=best_performer.variation_name,
                        confidence_level=best_performer.confidence_level,
                        evidence_trades=best_performer.trades_completed,
                        outperformance=best_performer.outperformance_vs_champion,
                        p_value=best_performer.statistical_significance,
                        reason=f"Bear market variation outperforming by {best_performer.outperformance:.1%}"
                    ))
                    
            elif best_performer.variation_name == 'BULL_MARKET':
                if best_performer.confidence_level in ['HIGH', 'MEDIUM']:
                    recommendations.append(AdjustmentRecommendation(
                        strategy_name=strategy,
                        parameter_name='confidence_threshold',
                        current_value=current_params.get('min_confidence', 0.60),
                        recommended_value=0.65,
                        variation_source=best_performer.variation_name,
                        confidence_level=best_performer.confidence_level,
                        evidence_trades=best_performer.trades_completed,
                        outperformance=best_performer.outperformance_vs_champion,
                        p_value=best_performer.statistical_significance,
                        reason=f"Bull market variation outperforming by {best_performer.outperformance:.1%}"
                    ))
                    
            elif 'DCA_DROPS' in best_performer.variation_name:
                # Extract the test value from variation name
                if '_' in best_performer.variation_name:
                    test_value = float(best_performer.variation_name.split('_')[-1])
                    recommendations.append(AdjustmentRecommendation(
                        strategy_name=strategy,
                        parameter_name='dca_drop_threshold',
                        current_value=current_params.get('dca_drop_threshold', 0.05),
                        recommended_value=test_value,
                        variation_source=best_performer.variation_name,
                        confidence_level=best_performer.confidence_level,
                        evidence_trades=best_performer.trades_completed,
                        outperformance=best_performer.outperformance_vs_champion,
                        p_value=best_performer.statistical_significance,
                        reason=f"DCA drop {test_value:.1%} outperforming by {best_performer.outperformance:.1%}"
                    ))
                    
            elif best_performer.variation_name == 'QUICK_EXITS':
                if best_performer.confidence_level in ['HIGH', 'MEDIUM']:
                    recommendations.append(AdjustmentRecommendation(
                        strategy_name=strategy,
                        parameter_name='take_profit_multiplier',
                        current_value=current_params.get('take_profit_multiplier', 1.0),
                        recommended_value=0.8,
                        variation_source=best_performer.variation_name,
                        confidence_level=best_performer.confidence_level,
                        evidence_trades=best_performer.trades_completed,
                        outperformance=best_performer.outperformance_vs_champion,
                        p_value=best_performer.statistical_significance,
                        reason=f"Quick exits improving win rate by {best_performer.outperformance:.1%}"
                    ))
                    
        except Exception as e:
            logger.error(f"Error generating variation recommendations: {e}")
            
        return recommendations
    
    async def _get_active_variations(self) -> List[str]:
        """Get list of active variation names"""
        try:
            result = self.supabase.table('shadow_configuration')\
                .select('variation_name')\
                .eq('is_active', True)\
                .execute()
            
            if result.data:
                return [v['variation_name'] for v in result.data]
                
            # Fallback to config
            return ShadowConfig.get_active_variations()
            
        except Exception as e:
            logger.error(f"Error getting active variations: {e}")
            return []
    
    async def _get_champion_performance(self, strategy_name: str, timeframe: str) -> Optional[Dict]:
        """Get champion performance for comparison"""
        try:
            result = self.supabase.table('shadow_performance')\
                .select('*')\
                .eq('variation_name', 'CHAMPION')\
                .eq('strategy_name', strategy_name)\
                .eq('timeframe', timeframe)\
                .single()\
                .execute()
            
            if result.data:
                return {
                    'win_rate': float(result.data['win_rate']),
                    'wins': int(result.data['wins']),
                    'total': int(result.data['trades_completed']),
                    'avg_pnl': float(result.data['avg_pnl_percentage'])
                }
                
        except Exception as e:
            logger.error(f"Error getting champion performance: {e}")
            
        return None
    
    async def _get_current_parameters(self, strategy: str) -> Dict:
        """Get current production parameters for a strategy"""
        # This would typically fetch from your configuration
        # For now, return defaults
        return {
            'min_confidence': 0.60,
            'position_size': 100,
            'stop_loss_pct': 5.0,
            'take_profit_pct': 10.0,
            'dca_drop_threshold': 0.05,
            'take_profit_multiplier': 1.0
        }
    
    async def _save_performance_metrics(self, metrics: PerformanceMetrics) -> bool:
        """Save performance metrics to database"""
        try:
            record = {
                'variation_name': metrics.variation_name,
                'timeframe': metrics.timeframe,
                'strategy_name': metrics.strategy_name,
                'total_opportunities': metrics.total_opportunities,
                'trades_taken': metrics.trades_taken,
                'trades_completed': metrics.trades_completed,
                'wins': metrics.wins,
                'losses': metrics.losses,
                'timeouts': metrics.timeouts,
                'win_rate': metrics.win_rate,
                'avg_pnl_percentage': metrics.avg_pnl_percentage,
                'total_pnl_percentage': metrics.total_pnl_percentage,
                'best_trade_pnl': metrics.best_trade_pnl,
                'worst_trade_pnl': metrics.worst_trade_pnl,
                'sharpe_ratio': metrics.sharpe_ratio,
                'max_drawdown': metrics.max_drawdown,
                'avg_hold_hours': metrics.avg_hold_hours,
                'outperformance_vs_champion': metrics.outperformance_vs_champion,
                'confidence_level': metrics.confidence_level,
                'statistical_significance': metrics.statistical_significance,
                'last_updated': datetime.utcnow().isoformat()
            }
            
            # Upsert (update if exists, insert if not)
            result = self.supabase.table('shadow_performance').upsert(record).execute()
            
            return bool(result.data)
            
        except Exception as e:
            logger.error(f"Error saving performance metrics: {e}")
            return False
    
    def _timeframe_to_hours(self, timeframe: str) -> int:
        """Convert timeframe string to hours"""
        mapping = {
            '24h': 24,
            '3d': 72,
            '7d': 168,
            '30d': 720
        }
        return mapping.get(timeframe, 24)
    
    def _timeframe_to_days(self, timeframe: str) -> int:
        """Convert timeframe string to days"""
        return self._timeframe_to_hours(timeframe) // 24
    
    def _calculate_significance(self, wins_a: int, total_a: int, wins_b: int, total_b: int) -> float:
        """
        Calculate statistical significance of performance difference
        Uses two-proportion z-test
        """
        if total_a == 0 or total_b == 0:
            return 1.0
            
        p1 = wins_a / total_a
        p2 = wins_b / total_b
        
        # Pooled proportion
        p_pool = (wins_a + wins_b) / (total_a + total_b)
        
        # Standard error
        se = np.sqrt(p_pool * (1 - p_pool) * (1/total_a + 1/total_b))
        
        if se == 0:
            return 1.0
            
        # Z-score
        z = (p1 - p2) / se
        
        # Two-tailed p-value
        p_value = 2 * (1 - stats.norm.cdf(abs(z)))
        
        return p_value
    
    def _determine_confidence_level(self,
                                   trade_count: int,
                                   outperformance: float,
                                   p_value: float,
                                   days: int) -> str:
        """Determine confidence level based on evidence"""
        
        for tier_name, tier_config in ShadowConfig.CONFIDENCE_TIERS.items():
            if (trade_count >= tier_config['min_trades'] and
                outperformance >= tier_config['min_outperformance'] and
                p_value <= tier_config['max_p_value'] and
                days >= tier_config['min_days']):
                return tier_name
                
        return 'LOW'
    
    def _confidence_to_score(self, confidence_level: str) -> int:
        """Convert confidence level to numeric score for sorting"""
        scores = {'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}
        return scores.get(confidence_level, 0)
    
    async def get_top_performers(self, timeframe: str = '7d', top_n: int = 3) -> List[PerformanceMetrics]:
        """
        Get top performing variations
        
        Args:
            timeframe: Timeframe to analyze
            top_n: Number of top performers to return
            
        Returns:
            List of top performing variations
        """
        try:
            result = self.supabase.table('shadow_performance')\
                .select('*')\
                .eq('timeframe', timeframe)\
                .eq('strategy_name', 'OVERALL')\
                .neq('variation_name', 'CHAMPION')\
                .order('outperformance_vs_champion', desc=True)\
                .limit(top_n)\
                .execute()
            
            if result.data:
                return [self._dict_to_metrics(d) for d in result.data]
                
        except Exception as e:
            logger.error(f"Error getting top performers: {e}")
            
        return []
    
    def _dict_to_metrics(self, data: Dict) -> PerformanceMetrics:
        """Convert dictionary to PerformanceMetrics object"""
        return PerformanceMetrics(
            variation_name=data['variation_name'],
            timeframe=data['timeframe'],
            strategy_name=data['strategy_name'],
            total_opportunities=data['total_opportunities'],
            trades_taken=data['trades_taken'],
            trades_completed=data['trades_completed'],
            wins=data['wins'],
            losses=data['losses'],
            timeouts=data['timeouts'],
            win_rate=float(data['win_rate']),
            avg_pnl_percentage=float(data['avg_pnl_percentage']),
            total_pnl_percentage=float(data['total_pnl_percentage']),
            best_trade_pnl=float(data['best_trade_pnl']),
            worst_trade_pnl=float(data['worst_trade_pnl']),
            sharpe_ratio=float(data['sharpe_ratio']),
            max_drawdown=float(data['max_drawdown']),
            avg_hold_hours=float(data['avg_hold_hours']),
            outperformance_vs_champion=float(data['outperformance_vs_champion']),
            confidence_level=data['confidence_level'],
            statistical_significance=float(data['statistical_significance'])
        )
