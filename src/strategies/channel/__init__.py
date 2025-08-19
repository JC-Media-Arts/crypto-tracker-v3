"""
Channel Trading Strategy Module
Identifies and trades price channels in all market conditions
"""

from .detector import ChannelDetector
from .executor import ChannelExecutor

__all__ = ['ChannelDetector', 'ChannelExecutor']
