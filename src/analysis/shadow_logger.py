"""
Shadow Logger Module
Captures what each shadow variation would do for every scan
Hooks into the existing scan system with minimal performance impact
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from decimal import Decimal
from loguru import logger
import json
import asyncio
from dataclasses import dataclass

from src.config.shadow_config import ShadowConfig


@dataclass
class ShadowDecision:
    """Represents a shadow variation's decision"""
    variation_name: str
    would_take_trade: bool
    shadow_confidence: float
    shadow_position_size: float
    shadow_entry_price: float
    shadow_take_profit: float
    shadow_stop_loss: float
    shadow_hold_hours: float
    parameters_used: Dict[str, Any]


class ShadowLogger:
    """
    Logs what each shadow variation would do for every scan
    Integrates with existing scan_history system
    """
    
    def __init__(self, supabase_client, ml_predictor=None):
        """
        Initialize the shadow logger
        
        Args:
            supabase_client: Supabase client for database operations
            ml_predictor: ML predictor for getting predictions with different thresholds
        """
        self.supabase = supabase_client
        self.ml_predictor = ml_predictor
        self.batch = []  # For batch inserts
        self.batch_size = 50  # Insert in batches
        self.active_variations = self._load_active_variations()
        
    def _load_active_variations(self) -> List[Dict]:
        """Load active shadow variations from configuration"""
        try:
            # Get variations from database config table
            result = self.supabase.table('shadow_configuration')\
                .select('*')\
                .eq('is_active', True)\
                .order('priority_order')\
                .execute()
            
            if result.data:
                return result.data
            
            # Fallback to config file
            variations = []
            for name in ShadowConfig.get_active_variations():
                var = ShadowConfig.VARIATIONS[name]
                variations.append({
                    'variation_name': name,
                    'variation_config': {
                        'type': var.type,
                        'parameters': var.parameters,
                        'description': var.description
                    }
                })
            return variations
            
        except Exception as e:
            logger.error(f"Error loading shadow variations: {e}")
            return []
    
    async def log_shadow_decisions(self,
                                  scan_id: int,
                                  symbol: str,
                                  strategy_name: str,
                                  features: Dict,
                                  ml_predictions: Dict,
                                  ml_confidence: float,
                                  current_price: float,
                                  base_parameters: Dict) -> List[ShadowDecision]:
        """
        Log what each shadow variation would do for this scan
        
        Args:
            scan_id: ID from scan_history table
            symbol: Trading symbol
            strategy_name: Strategy type ('DCA', 'SWING', 'CHANNEL')
            features: Calculated features at scan time
            ml_predictions: ML model predictions
            ml_confidence: ML model confidence
            current_price: Current price of the asset
            base_parameters: Current production parameters
            
        Returns:
            List of shadow decisions made
        """
        decisions = []
        
        try:
            for variation in self.active_variations:
                # Calculate what this variation would do
                decision = await self._evaluate_variation(
                    variation=variation,
                    symbol=symbol,
                    strategy_name=strategy_name,
                    features=features,
                    ml_predictions=ml_predictions,
                    ml_confidence=ml_confidence,
                    current_price=current_price,
                    base_parameters=base_parameters
                )
                
                if decision:
                    decisions.append(decision)
                    
                    # Prepare database record
                    record = self._prepare_shadow_record(
                        scan_id=scan_id,
                        decision=decision,
                        strategy_name=strategy_name,
                        current_price=current_price
                    )
                    
                    self.batch.append(record)
                    
            # Insert if batch is full
            if len(self.batch) >= self.batch_size:
                await self.flush()
                
        except Exception as e:
            logger.error(f"Error logging shadow decisions: {e}")
            
        return decisions
    
    async def _evaluate_variation(self,
                                 variation: Dict,
                                 symbol: str,
                                 strategy_name: str,
                                 features: Dict,
                                 ml_predictions: Dict,
                                 ml_confidence: float,
                                 current_price: float,
                                 base_parameters: Dict) -> Optional[ShadowDecision]:
        """
        Evaluate what a specific variation would do
        """
        try:
            var_config = variation['variation_config']
            var_type = var_config.get('type', 'scenario')
            
            if var_type == 'champion':
                # Champion uses current production parameters
                return self._evaluate_champion(
                    variation_name=variation['variation_name'],
                    ml_predictions=ml_predictions,
                    ml_confidence=ml_confidence,
                    current_price=current_price,
                    base_parameters=base_parameters
                )
                
            elif var_type == 'scenario':
                # Scenario variations override specific parameters
                return self._evaluate_scenario(
                    variation_name=variation['variation_name'],
                    scenario_params=var_config.get('parameters', {}),
                    ml_predictions=ml_predictions,
                    ml_confidence=ml_confidence,
                    current_price=current_price,
                    base_parameters=base_parameters,
                    features=features,
                    strategy_name=strategy_name
                )
                
            elif var_type == 'isolated':
                # Isolated variations test specific parameter values
                return await self._evaluate_isolated(
                    variation_name=variation['variation_name'],
                    test_parameter=var_config.get('parameters', {}).get('test_parameter'),
                    test_values=var_config.get('parameters', {}).get('test_values', []),
                    ml_predictions=ml_predictions,
                    ml_confidence=ml_confidence,
                    current_price=current_price,
                    base_parameters=base_parameters,
                    strategy_name=strategy_name
                )
                
        except Exception as e:
            logger.error(f"Error evaluating variation {variation.get('variation_name')}: {e}")
            return None
    
    def _evaluate_champion(self,
                          variation_name: str,
                          ml_predictions: Dict,
                          ml_confidence: float,
                          current_price: float,
                          base_parameters: Dict) -> ShadowDecision:
        """Evaluate using current production parameters"""
        
        # Champion uses exact production thresholds
        confidence_threshold = base_parameters.get('min_confidence', 0.60)
        would_take = ml_confidence >= confidence_threshold
        
        return ShadowDecision(
            variation_name=variation_name,
            would_take_trade=would_take,
            shadow_confidence=ml_confidence,
            shadow_position_size=base_parameters.get('position_size', 100),
            shadow_entry_price=current_price,
            shadow_take_profit=ml_predictions.get('take_profit_pct', 10.0),
            shadow_stop_loss=ml_predictions.get('stop_loss_pct', 5.0),
            shadow_hold_hours=ml_predictions.get('hold_hours', 24),
            parameters_used=base_parameters.copy()
        )
    
    def _evaluate_scenario(self,
                          variation_name: str,
                          scenario_params: Dict,
                          ml_predictions: Dict,
                          ml_confidence: float,
                          current_price: float,
                          base_parameters: Dict,
                          features: Dict,
                          strategy_name: str) -> ShadowDecision:
        """Evaluate a scenario variation"""
        
        # Merge scenario parameters with base
        params = base_parameters.copy()
        
        # Handle specific scenario logic
        if variation_name == 'BEAR_MARKET':
            params['confidence_threshold'] = scenario_params.get('confidence_threshold', 0.55)
            params['position_size_multiplier'] = scenario_params.get('position_size_multiplier', 1.5)
            params['stop_loss_percent'] = scenario_params.get('stop_loss_percent', 0.06)
            params['take_profit_multiplier'] = scenario_params.get('take_profit_multiplier', 1.2)
            
        elif variation_name == 'BULL_MARKET':
            params['confidence_threshold'] = scenario_params.get('confidence_threshold', 0.65)
            params['position_size_multiplier'] = scenario_params.get('position_size_multiplier', 0.5)
            params['stop_loss_percent'] = scenario_params.get('stop_loss_percent', 0.04)
            params['take_profit_multiplier'] = scenario_params.get('take_profit_multiplier', 0.8)
            
        elif variation_name == 'ML_TRUST':
            params['confidence_threshold'] = 0.50  # Lower threshold, trust ML
            params['use_ml_predictions_raw'] = True
            params['take_profit_multiplier'] = 1.0  # Use ML exactly
            
        elif variation_name == 'QUICK_EXITS':
            params['take_profit_multiplier'] = scenario_params.get('take_profit_multiplier', 0.8)
            params['max_hold_hours'] = scenario_params.get('max_hold_hours', 24)
            
        elif variation_name == 'VOLATILITY_SIZED':
            # Calculate volatility-based sizing
            volatility = features.get('volatility_24h', 0.03)
            if volatility < scenario_params.get('vol_threshold_low', 0.02):
                params['position_size_multiplier'] = scenario_params.get('low_vol_multiplier', 1.5)
            elif volatility > scenario_params.get('vol_threshold_high', 0.05):
                params['position_size_multiplier'] = scenario_params.get('high_vol_multiplier', 0.5)
            else:
                params['position_size_multiplier'] = 1.0
        
        # Apply scenario parameters
        params.update(scenario_params)
        
        # Calculate decision with scenario parameters
        confidence_threshold = params.get('confidence_threshold', 0.60)
        would_take = ml_confidence >= confidence_threshold
        
        # Calculate position size
        base_size = base_parameters.get('position_size', 100)
        size_mult = params.get('position_size_multiplier', 1.0)
        position_size = base_size * size_mult
        
        # Calculate targets
        tp_mult = params.get('take_profit_multiplier', 1.0)
        take_profit = ml_predictions.get('take_profit_pct', 10.0) * tp_mult
        
        stop_loss = params.get('stop_loss_percent', 0.05) * 100  # Convert to percentage
        if params.get('use_ml_predictions_raw'):
            stop_loss = ml_predictions.get('stop_loss_pct', 5.0)
        
        # Handle strategy-specific parameters
        if strategy_name == 'DCA' and 'dca_drop_threshold' in params:
            params['entry_threshold'] = params['dca_drop_threshold']
            
        return ShadowDecision(
            variation_name=variation_name,
            would_take_trade=would_take,
            shadow_confidence=ml_confidence,
            shadow_position_size=position_size,
            shadow_entry_price=current_price,
            shadow_take_profit=take_profit,
            shadow_stop_loss=stop_loss,
            shadow_hold_hours=params.get('max_hold_hours', ml_predictions.get('hold_hours', 24)),
            parameters_used=params
        )
    
    async def _evaluate_isolated(self,
                                variation_name: str,
                                test_parameter: str,
                                test_values: List,
                                ml_predictions: Dict,
                                ml_confidence: float,
                                current_price: float,
                                base_parameters: Dict,
                                strategy_name: str) -> Optional[ShadowDecision]:
        """
        Evaluate isolated parameter variations
        Creates multiple sub-variations for each test value
        """
        # For isolated tests, we'll create the primary variation
        # Additional test values will be handled separately
        
        if not test_values:
            return None
            
        # Use the first test value for this variation
        test_value = test_values[0]
        
        params = base_parameters.copy()
        
        # Apply the test parameter
        if test_parameter == 'confidence_threshold':
            params['confidence_threshold'] = test_value
            would_take = ml_confidence >= test_value
            
        elif test_parameter == 'dca_drop_threshold':
            params['dca_drop_threshold'] = test_value
            # This would need actual price drop calculation
            would_take = ml_confidence >= base_parameters.get('min_confidence', 0.60)
            
        else:
            params[test_parameter] = test_value
            would_take = ml_confidence >= base_parameters.get('min_confidence', 0.60)
        
        return ShadowDecision(
            variation_name=f"{variation_name}_{test_value}",
            would_take_trade=would_take,
            shadow_confidence=ml_confidence,
            shadow_position_size=base_parameters.get('position_size', 100),
            shadow_entry_price=current_price,
            shadow_take_profit=ml_predictions.get('take_profit_pct', 10.0),
            shadow_stop_loss=ml_predictions.get('stop_loss_pct', 5.0),
            shadow_hold_hours=ml_predictions.get('hold_hours', 24),
            parameters_used=params
        )
    
    def _prepare_shadow_record(self,
                              scan_id: int,
                              decision: ShadowDecision,
                              strategy_name: str,
                              current_price: float) -> Dict:
        """Prepare a shadow variation record for database insertion"""
        
        params = decision.parameters_used
        
        return {
            'scan_id': scan_id,
            'variation_name': decision.variation_name,
            'variation_type': self._get_variation_type(decision.variation_name),
            
            # Decision parameters
            'confidence_threshold': params.get('confidence_threshold'),
            'position_size_multiplier': params.get('position_size_multiplier', 1.0),
            'stop_loss_percent': params.get('stop_loss_percent', 0.05) * 100,
            'take_profit_multiplier': params.get('take_profit_multiplier', 1.0),
            
            # Strategy-specific parameters
            'dca_drop_threshold': params.get('dca_drop_threshold') if strategy_name == 'DCA' else None,
            'dca_grid_levels': params.get('grid_levels', 5) if strategy_name == 'DCA' else None,
            'dca_grid_spacing': params.get('grid_spacing', 0.01) * 100 if strategy_name == 'DCA' else None,
            'swing_breakout_threshold': params.get('breakout_threshold') if strategy_name == 'SWING' else None,
            'swing_volume_multiplier': params.get('volume_multiplier') if strategy_name == 'SWING' else None,
            'channel_boundary_percent': params.get('boundary_percent') if strategy_name == 'CHANNEL' else None,
            
            # Shadow decision
            'would_take_trade': decision.would_take_trade,
            'shadow_confidence': decision.shadow_confidence,
            'shadow_position_size': decision.shadow_position_size,
            'shadow_entry_price': decision.shadow_entry_price,
            
            # Predicted targets
            'shadow_take_profit': decision.shadow_take_profit,
            'shadow_stop_loss': decision.shadow_stop_loss,
            'shadow_hold_hours': decision.shadow_hold_hours,
            
            'created_at': datetime.utcnow().isoformat()
        }
    
    def _get_variation_type(self, variation_name: str) -> str:
        """Get the type of a variation"""
        if variation_name == 'CHAMPION':
            return 'champion'
        elif '_' in variation_name and any(char.isdigit() for char in variation_name):
            return 'isolated_param'
        else:
            return 'scenario'
    
    async def flush(self):
        """Flush batch to database"""
        if not self.batch:
            return
            
        try:
            result = self.supabase.table('shadow_variations').insert(self.batch).execute()
            logger.debug(f"Flushed {len(self.batch)} shadow variations to database")
            self.batch = []
        except Exception as e:
            logger.error(f"Error flushing shadow variations: {e}")
            self.batch = []  # Clear anyway to prevent memory issues
    
    def get_shadow_consensus(self, decisions: List[ShadowDecision]) -> Dict:
        """
        Calculate consensus metrics from shadow decisions
        
        Returns:
            Dict with consensus score and other metrics
        """
        if not decisions:
            return {
                'consensus_score': 0,
                'shadows_taking': 0,
                'total_shadows': 0,
                'avg_confidence': 0
            }
        
        taking_trade = [d for d in decisions if d.would_take_trade]
        
        return {
            'consensus_score': len(taking_trade) / len(decisions),
            'shadows_taking': len(taking_trade),
            'total_shadows': len(decisions),
            'avg_confidence': sum(d.shadow_confidence for d in taking_trade) / len(taking_trade) if taking_trade else 0,
            'variations_taking': [d.variation_name for d in taking_trade],
            'variations_skipping': [d.variation_name for d in decisions if not d.would_take_trade]
        }
    
    async def log_quick_decision(self,
                                symbol: str,
                                strategy_name: str,
                                ml_confidence: float,
                                current_price: float,
                                base_parameters: Dict) -> Dict:
        """
        Quick evaluation for real-time decision support
        Returns consensus without logging to database
        """
        decisions = []
        
        for variation in self.active_variations[:5]:  # Only check top 5 for speed
            decision = await self._evaluate_variation(
                variation=variation,
                symbol=symbol,
                strategy_name=strategy_name,
                features={},
                ml_predictions={'take_profit_pct': 10, 'stop_loss_pct': 5, 'hold_hours': 24},
                ml_confidence=ml_confidence,
                current_price=current_price,
                base_parameters=base_parameters
            )
            if decision:
                decisions.append(decision)
        
        return self.get_shadow_consensus(decisions)
