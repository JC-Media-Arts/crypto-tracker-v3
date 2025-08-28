"""Paper trading configuration with loosened thresholds"""

PAPER_TRADING_CONFIG = {
    "ml_confidence_threshold": 0.55,
    "min_signal_strength": 0.6,
    "required_confirmations": 2,
    "position_size_multiplier": 1.5,
    "max_positions": 50,  # Total max positions across all strategies
    "max_positions_per_strategy": 50,  # Max positions per individual strategy
    "risk_per_trade": 0.02,
    "stop_loss_percentage": 0.02,
    "take_profit_percentage": 0.05,
    "trailing_stop": True,
    "trailing_stop_percentage": 0.015,
    "strategies": {
        "DCA": {
            "enabled": True,
            "min_confidence": 0.5,
            "grid_levels": 5,
            "grid_spacing": 0.02,
            "max_grids_per_symbol": 3,
            "volume_threshold": 100000,
            "drop_threshold": -2.5,  # Changed from -4.0 to capture more opportunities
            "volume_requirement": 0.85,  # Changed from 1.0 (moderate adjustment)
        },
        "SWING": {
            "enabled": True,
            "min_confidence": 0.50,  # Changed from 0.55 (aggressive adjustment)
            "take_profit": 0.05,
            "stop_loss": 0.02,
            "breakout_confirmation": 0.015,
            "volume_surge": 1.3,  # Changed from 1.5 to capture more signals
            "breakout_threshold": 1.010,  # Changed from 1.015 (1% breakout)
            "rsi_min": 45,  # Changed from 50 (aggressive adjustment)
            "rsi_max": 75,  # Changed from 70 (aggressive adjustment)
            "min_score": 40,  # Changed from 50 (aggressive adjustment)
        },
        "CHANNEL": {
            "enabled": True,
            "min_confidence": 0.75,  # Increased from 0.65 to be VERY selective
            "entry_threshold": 0.9,
            "exit_threshold": 0.1,
            "channel_width_min": 0.03,  # Increased from 0.02 - wider channels only
            "channel_touches": 5,  # Increased from 3 - need more confirmations
            "buy_zone": 0.02,  # Changed from 0.05 to 0.02 - only bottom 2% of channel!
            "sell_zone": 0.98,  # Changed from 0.95 to 0.98 - only extreme tops
            "channel_strength_min": 0.90,  # Increased from 0.80 to 0.90 - only strongest channels
        },
    },
    "timeframes": {"primary": "15m", "confirmation": "1h", "trend": "4h"},
    "filters": {
        "min_volume_24h": 100000,
        "min_price": 0.01,
        "max_spread": 0.005,
        "avoid_news_hours": False,
        "trade_weekends": True,
    },
    "updated_at": "2025-12-27T16:58:00.000000",  # CHANNEL EMERGENCY FIX: buy_zone 2%, strength 0.90, confidence 0.75
}
