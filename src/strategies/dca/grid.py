"""
DCA Grid Calculator

Calculates optimal grid levels for DCA entries:
- Distributes orders below current price
- Adjusts spacing based on ML confidence
- Validates risk parameters
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from loguru import logger


class GridCalculator:
    """Calculates DCA grid levels and sizes."""

    def __init__(self, config: Dict):
        """
        Initialize Grid Calculator.

        Args:
            config: Strategy configuration dictionary
        """
        self.config = config

    def calculate_grid(
        self,
        current_price: float,
        ml_confidence: float,
        support_levels: List[float],
        total_capital: float = None,
    ) -> Dict:
        """
        Calculate DCA grid levels.

        Args:
            current_price: Current market price
            ml_confidence: ML model confidence (0-1)
            support_levels: List of support levels
            total_capital: Total capital to allocate (uses config default if None)

        Returns:
            Dictionary with grid configuration
        """
        if total_capital is None:
            total_capital = self.config["base_size"] * self.config["grid_levels"]

        # Adjust parameters based on ML confidence
        grid_params = self._adjust_for_confidence(ml_confidence)

        # Calculate grid levels
        levels = self._calculate_levels(
            current_price, support_levels, grid_params["levels"], grid_params["spacing"]
        )

        # Calculate position sizes
        sizes = self._calculate_sizes(
            total_capital, grid_params["levels"], ml_confidence
        )

        # Create grid structure
        grid = {
            "levels": [],
            "total_investment": total_capital,
            "average_entry": 0,
            "stop_loss": 0,
            "take_profit": 0,
            "parameters": grid_params,
        }

        # Build grid levels
        for i, (price, size) in enumerate(zip(levels, sizes)):
            grid["levels"].append(
                {
                    "level": i + 1,
                    "price": round(price, 8),
                    "size": round(size, 2),
                    "size_crypto": round(size / price, 8),
                    "status": "PENDING",
                    "filled_at": None,
                    "order_id": None,
                }
            )

        # Calculate average entry and risk levels
        grid["average_entry"] = self._calculate_average_entry(grid["levels"])
        grid["stop_loss"] = grid["average_entry"] * (1 + self.config["stop_loss"] / 100)
        grid["take_profit"] = grid["average_entry"] * (
            1 + self.config["take_profit"] / 100
        )

        logger.info(
            f"Created DCA grid with {len(levels)} levels, confidence: {ml_confidence:.2f}"
        )

        return grid

    def _adjust_for_confidence(self, confidence: float) -> Dict:
        """
        Adjust grid parameters based on ML confidence.

        Args:
            confidence: ML model confidence (0-1)

        Returns:
            Adjusted parameters
        """
        base_levels = self.config["grid_levels"]
        base_spacing = self.config["grid_spacing"]

        if confidence >= 0.75:
            # High confidence: tighter grid, more levels
            return {
                "levels": min(base_levels + 1, 7),
                "spacing": base_spacing * 0.8,
                "size_multiplier": 1.2,
            }
        elif confidence >= 0.65:
            # Medium confidence: standard grid
            return {
                "levels": base_levels,
                "spacing": base_spacing,
                "size_multiplier": 1.0,
            }
        else:
            # Low confidence: wider grid, fewer levels
            return {
                "levels": max(base_levels - 1, 3),
                "spacing": base_spacing * 1.3,
                "size_multiplier": 0.8,
            }

    def _calculate_levels(
        self,
        current_price: float,
        support_levels: List[float],
        num_levels: int,
        spacing_pct: float,
    ) -> List[float]:
        """
        Calculate grid price levels.

        Args:
            current_price: Current market price
            support_levels: List of support levels
            num_levels: Number of grid levels
            spacing_pct: Percentage spacing between levels

        Returns:
            List of price levels
        """
        levels = []

        # Start slightly below current price (0.5% buffer)
        start_price = current_price * 0.995

        # Calculate levels with exponential spacing
        for i in range(num_levels):
            # Each level is spacing_pct% below the previous
            price = start_price * (1 - spacing_pct / 100) ** i

            # Snap to support if close (within 0.5%)
            for support in support_levels:
                if abs(price - support) / support < 0.005:
                    price = support
                    break

            levels.append(price)

        return levels

    def _calculate_sizes(
        self, total_capital: float, num_levels: int, confidence: float
    ) -> List[float]:
        """
        Calculate position sizes for each level.

        Args:
            total_capital: Total capital to allocate
            num_levels: Number of grid levels
            confidence: ML confidence for weighting

        Returns:
            List of position sizes in USD
        """
        if confidence >= 0.7:
            # High confidence: weight towards upper levels
            weights = np.linspace(1.3, 0.7, num_levels)
        else:
            # Low confidence: equal weighting
            weights = np.ones(num_levels)

        # Normalize weights
        weights = weights / weights.sum()

        # Calculate sizes
        sizes = weights * total_capital

        # Ensure minimum size ($10)
        sizes = np.maximum(sizes, 10)

        # Re-normalize if needed
        if sizes.sum() > total_capital:
            sizes = sizes * (total_capital / sizes.sum())

        return sizes.tolist()

    def _calculate_average_entry(self, levels: List[Dict]) -> float:
        """Calculate weighted average entry price."""
        total_cost = sum(level["size"] for level in levels)
        total_amount = sum(level["size_crypto"] for level in levels)

        if total_amount > 0:
            return total_cost / total_amount
        return levels[0]["price"]

    def validate_grid(self, grid: Dict, account_balance: float) -> Tuple[bool, str]:
        """
        Validate grid against risk parameters.

        Args:
            grid: Grid configuration
            account_balance: Available account balance

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check capital requirement
        if grid["total_investment"] > account_balance:
            return (
                False,
                f"Insufficient balance: need ${grid['total_investment']:.2f}, have ${account_balance:.2f}",
            )

        # Check minimum order sizes
        for level in grid["levels"]:
            if level["size"] < 10:  # $10 minimum
                return (
                    False,
                    f"Order size too small at level {level['level']}: ${level['size']:.2f}",
                )

        # Check stop loss distance
        stop_distance = (
            abs(grid["stop_loss"] - grid["average_entry"]) / grid["average_entry"]
        )
        if stop_distance > 0.15:  # Max 15% stop
            return False, f"Stop loss too far: {stop_distance:.1%}"

        return True, "Grid validated successfully"

    def update_grid_level(
        self, grid: Dict, level_index: int, status: str, filled_at: str = None
    ) -> Dict:
        """
        Update status of a grid level.

        Args:
            grid: Grid configuration
            level_index: Index of level to update
            status: New status ('FILLED', 'CANCELLED', etc.)
            filled_at: Timestamp when filled

        Returns:
            Updated grid
        """
        if 0 <= level_index < len(grid["levels"]):
            grid["levels"][level_index]["status"] = status
            if filled_at:
                grid["levels"][level_index]["filled_at"] = filled_at

            # Recalculate average entry if filled
            if status == "FILLED":
                filled_levels = [l for l in grid["levels"] if l["status"] == "FILLED"]
                if filled_levels:
                    grid["average_entry"] = self._calculate_average_entry(filled_levels)
                    grid["stop_loss"] = grid["average_entry"] * (
                        1 + self.config["stop_loss"] / 100
                    )
                    grid["take_profit"] = grid["average_entry"] * (
                        1 + self.config["take_profit"] / 100
                    )

        return grid
