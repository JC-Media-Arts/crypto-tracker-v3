"""
Swing Trading Strategy Module
Identifies momentum and breakout opportunities for multi-day trades
"""

from .detector import SwingDetector
from .analyzer import SwingAnalyzer

__all__ = ["SwingDetector", "SwingAnalyzer"]
