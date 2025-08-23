"""
Simple position sizer for Phase 1 recovery
Fixed position sizes, no ML or market regime adjustments
"""

from typing import Dict, Optional
from loguru import logger


class SimplePositionSizer:
    """Simple fixed position sizing for recovery phase"""

    def __init__(self, config: Dict = None):
        """Initialize with simple config"""
        config = config or {}

        # Fixed position sizes from recovery config
        self.base_position_usd = config.get("base_position_usd", 50)
        self.max_positions = config.get("max_positions", 10)
        self.max_position_pct = config.get(
            "max_position_pct", 0.1
        )  # Max 10% per position

        logger.info(
            f"Simple Position Sizer: ${self.base_position_usd} per trade, max {self.max_positions} positions"
        )

    def calculate_position_size(
        self,
        symbol: str,
        portfolio_value: float,
        market_data: Dict = None,
        ml_confidence: Optional[float] = None,
    ) -> float:
        """
        Calculate position size - just returns fixed amount

        Args:
            symbol: Trading symbol
            portfolio_value: Available capital
            market_data: Ignored in simple mode
            ml_confidence: Ignored in simple mode

        Returns:
            Fixed position size in USD
        """
        # Ensure we don't exceed available capital
        max_allowed = portfolio_value * self.max_position_pct
        position_size = min(self.base_position_usd, max_allowed)

        # Ensure minimum viable position
        if position_size < 10:
            logger.warning(
                f"Position size too small for {symbol}: ${position_size:.2f}"
            )
            return 0

        return position_size
