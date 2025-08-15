"""Configuration module for crypto-tracker-v3."""

# Railway deployment fix - Force rebuild
# Version: 2.0.0
# Updated: 2025-08-14 21:00 PST

from .settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
