"""Machine Learning module for price prediction - Version 2."""

# Railway deployment fix - NEW FILE to bypass cache
# Version: 2.0.0
# Updated: 2025-08-14 22:00 PST

# Export names without importing to avoid circular dependencies
__all__ = ["MLPredictor", "FeatureCalculator", "ModelTrainer"]

# DO NOT ADD ANY IMPORTS HERE - This causes circular import issues
