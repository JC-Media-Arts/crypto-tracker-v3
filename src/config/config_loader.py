"""
Unified configuration loader for paper trading system.
Single source of truth for all trading parameters.
Now with Supabase support for Railway deployment.
"""

import json
import os
from typing import Dict, Any, Optional, List
from pathlib import Path
from loguru import logger
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class ConfigLoader:
    """Loads and manages the unified paper trading configuration."""

    _instance = None
    _config = None
    _config_path = None
    _last_loaded = None
    _supabase_client = None

    def __new__(cls, config_path: Optional[str] = None):
        """Singleton pattern to ensure single config instance."""
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
        return cls._instance

    def __init__(self, config_path: Optional[str] = None):
        """Initialize the config loader.

        Args:
            config_path: Path to config file. Defaults to configs/paper_trading_config_unified.json
        """
        if config_path:
            self._config_path = Path(config_path)
        elif not self._config_path:
            # Default path relative to project root
            project_root = Path(__file__).parent.parent.parent
            self._config_path = (
                project_root / "configs" / "paper_trading_config_unified.json"
            )
        
        # Initialize Supabase client if not already done
        if not self._supabase_client:
            self._init_supabase()
    
    def _init_supabase(self):
        """Initialize Supabase client."""
        try:
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_KEY")
            
            if supabase_url and supabase_key:
                self._supabase_client = create_client(supabase_url, supabase_key)
                logger.info("Supabase client initialized for config management")
            else:
                logger.warning("Supabase credentials not found, using file-based config only")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            self._supabase_client = None
    
    def _load_from_supabase(self) -> Optional[Dict[str, Any]]:
        """Load configuration from Supabase.
        
        Returns:
            Configuration dictionary or None if not available
        """
        if not self._supabase_client:
            return None
        
        try:
            # Get active configuration from Supabase
            response = self._supabase_client.table("trading_config").select("*").eq("config_key", "active").eq("is_valid", True).execute()
            
            if response.data and len(response.data) > 0:
                config_data = response.data[0]["config_data"]
                logger.info(f"Loaded configuration from Supabase (version: {config_data.get('version', 'unknown')})")
                return config_data
            else:
                logger.debug("No active configuration found in Supabase")
                return None
                
        except Exception as e:
            logger.error(f"Error loading config from Supabase: {e}")
            return None
    
    def _save_to_supabase(self, config: Dict[str, Any]) -> bool:
        """Save configuration to Supabase.
        
        Args:
            config: Configuration dictionary to save
            
        Returns:
            True if successful, False otherwise
        """
        if not self._supabase_client:
            return False
        
        try:
            # Check if active config exists
            response = self._supabase_client.table("trading_config").select("id").eq("config_key", "active").execute()
            
            config_version = config.get("version", "1.0.0")
            
            if response.data and len(response.data) > 0:
                # Update existing config
                update_response = self._supabase_client.table("trading_config").update({
                    "config_version": config_version,
                    "config_data": config,
                    "updated_by": "ConfigLoader",
                    "update_source": "admin_panel",
                    "is_valid": True
                }).eq("config_key", "active").execute()
            else:
                # Insert new config
                insert_response = self._supabase_client.table("trading_config").insert({
                    "config_key": "active",
                    "config_version": config_version,
                    "config_data": config,
                    "updated_by": "ConfigLoader",
                    "update_source": "admin_panel",
                    "is_valid": True
                }).execute()
            
            logger.info(f"Saved configuration to Supabase (version: {config_version})")
            return True
            
        except Exception as e:
            logger.error(f"Error saving config to Supabase: {e}")
            return False

    def load(self, force_reload: bool = False) -> Dict[str, Any]:
        """Load configuration from Supabase first, then file as fallback.

        Args:
            force_reload: Force reload even if already loaded

        Returns:
            Configuration dictionary
        """
        # Check if we need to reload (config changed or forced)
        if not force_reload and self._config is not None:
            # For cached config, check if we should refresh (every 60 seconds)
            if self._last_loaded:
                time_since_load = (datetime.now() - self._last_loaded).total_seconds()
                if time_since_load < 60:  # Cache for 60 seconds
                    return self._config

        # Try loading from Supabase first
        config_from_supabase = self._load_from_supabase()
        if config_from_supabase:
            self._config = config_from_supabase
            self._last_loaded = datetime.now()
            
            # Also save to local file for backup
            try:
                with open(self._config_path, "w") as f:
                    json.dump(self._config, f, indent=2)
                logger.debug("Synced Supabase config to local file")
            except Exception as e:
                logger.warning(f"Could not sync config to local file: {e}")
            
            return self._config
        
        # Fallback to file-based config if Supabase is not available
        logger.info("Falling back to file-based configuration")
        try:
            with open(self._config_path, "r") as f:
                self._config = json.load(f)
                self._last_loaded = datetime.now()
                logger.info(f"Loaded configuration from {self._config_path}")
                logger.debug(
                    f"Config version: {self._config.get('version', 'unknown')}"
                )
                
                # Try to sync to Supabase if available
                if self._supabase_client:
                    if self._save_to_supabase(self._config):
                        logger.info("Synced local config to Supabase")
                
                return self._config
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {self._config_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise

    def get(self, key_path: str, default: Any = None) -> Any:
        """Get a configuration value using dot notation.

        Args:
            key_path: Dot-separated path to config value (e.g., 'strategies.DCA.min_confidence')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        if self._config is None:
            self.load()

        keys = key_path.split(".")
        value = self._config

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default

        return value

    def get_strategy_config(self, strategy: str) -> Dict[str, Any]:
        """Get configuration for a specific strategy.

        Args:
            strategy: Strategy name (DCA, SWING, CHANNEL)

        Returns:
            Strategy configuration dictionary
        """
        return self.get(f"strategies.{strategy}", {})

    def get_tier_config(self, symbol: str) -> str:
        """Get market cap tier for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Tier name (large_cap, mid_cap, small_cap, memecoin)
        """
        if self._config is None:
            self.load()

        tiers = self._config.get("market_cap_tiers", {})

        for tier_name, symbols in tiers.items():
            if symbol in symbols:
                return tier_name

        # Default to small_cap if not found
        return "small_cap"

    def get_exit_params(self, strategy: str, symbol: str) -> Dict[str, float]:
        """Get exit parameters for a strategy and symbol.

        Args:
            strategy: Strategy name
            symbol: Trading symbol

        Returns:
            Dictionary with take_profit, stop_loss, trailing_stop, trailing_activation
        """
        tier = self.get_tier_config(symbol)
        strategy_config = self.get_strategy_config(strategy)

        exits_by_tier = strategy_config.get("exits_by_tier", {})
        tier_exits = exits_by_tier.get(tier, {})

        # Return with defaults if not found
        return {
            "take_profit": tier_exits.get("take_profit", 0.05),
            "stop_loss": tier_exits.get("stop_loss", 0.05),
            "trailing_stop": tier_exits.get("trailing_stop", 0.02),
            "trailing_activation": tier_exits.get("trailing_activation", 0.02),
        }
    
    def get_entry_thresholds(self, strategy: str, symbol: str) -> Dict[str, Any]:
        """Get entry/detection thresholds for a strategy and symbol.
        
        Args:
            strategy: Strategy name (DCA, SWING, CHANNEL)
            symbol: Trading symbol
            
        Returns:
            Dictionary with tier-specific detection thresholds
        """
        tier = self.get_tier_config(symbol)
        strategy_config = self.get_strategy_config(strategy)
        
        # Check for tier-specific thresholds first
        thresholds_by_tier = strategy_config.get("detection_thresholds_by_tier", {})
        if thresholds_by_tier and tier in thresholds_by_tier:
            return thresholds_by_tier[tier]
        
        # Fall back to global detection thresholds
        return strategy_config.get("detection_thresholds", {})

    def is_trading_enabled(self) -> bool:
        """Check if trading is globally enabled (kill switch)."""
        return self.get("global_settings.trading_enabled", False)

    def is_strategy_enabled(self, strategy: str) -> bool:
        """Check if a specific strategy is enabled."""
        return self.get(f"strategies.{strategy}.enabled", False)

    def get_position_sizing_config(self) -> Dict[str, Any]:
        """Get position sizing configuration."""
        return self.get("position_management.position_sizing", {})

    def get_market_protection_config(self) -> Dict[str, Any]:
        """Get market protection configuration."""
        return self.get("market_protection", {})

    def reload(self) -> Dict[str, Any]:
        """Force reload configuration from file."""
        return self.load(force_reload=True)

    def save(self, config: Dict[str, Any]) -> bool:
        """Save configuration to both Supabase and file.

        Args:
            config: Configuration dictionary to save

        Returns:
            True if successful
        """
        try:
            # Update version and timestamp
            config["version"] = config.get("version", "1.0.0")
            config["last_updated"] = datetime.now().isoformat()

            # Save to Supabase first (primary storage)
            supabase_success = self._save_to_supabase(config)
            
            # Always save to file as well (backup and local development)
            file_success = False
            try:
                with open(self._config_path, "w") as f:
                    json.dump(config, f, indent=2, sort_keys=False)
                file_success = True
                logger.info(f"Saved configuration to {self._config_path}")
            except Exception as e:
                logger.error(f"Error saving configuration to file: {e}")

            # Update internal state
            self._config = config
            self._last_loaded = datetime.now()

            # Consider successful if either storage method worked
            success = supabase_success or file_success
            if success:
                logger.info(f"Configuration saved (Supabase: {supabase_success}, File: {file_success})")
            else:
                logger.error("Failed to save configuration to both Supabase and file")

            return success

        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False

    @property
    def config(self) -> Dict[str, Any]:
        """Get the full configuration dictionary."""
        if self._config is None:
            self.load()
        return self._config

    @property
    def config_path(self) -> Path:
        """Get the configuration file path."""
        return self._config_path

    def save_config_change(
        self,
        section: str,
        field: str,
        old_value: Any,
        new_value: Any,
        change_type: str = "manual",
        changed_by: Optional[str] = None,
        description: Optional[str] = None,
    ) -> bool:
        """Save a configuration change to the database for tracking.

        Args:
            section: Configuration section (e.g., 'strategies.DCA.thresholds')
            field: Field name that changed
            old_value: Previous value
            new_value: New value
            change_type: Type of change (manual, admin_panel, api, system)
            changed_by: User or system that made the change
            description: Human-readable description

        Returns:
            True if saved successfully
        """
        try:
            from src.data.supabase_client import SupabaseClient

            db = SupabaseClient()

            # Get current full config
            current_config = self.load()

            # Prepare the record
            record = {
                "change_type": change_type,
                "changed_by": changed_by,
                "change_description": description,
                "config_version": current_config.get("version", "1.0.0"),
                "config_section": section,
                "field_name": field,
                "old_value": json.dumps(old_value) if old_value is not None else None,
                "new_value": json.dumps(new_value) if new_value is not None else None,
                "full_config_after": json.dumps(current_config),
                "environment": current_config.get("global_settings", {}).get(
                    "environment", "paper"
                ),
            }

            # Insert into database
            result = db.client.table("config_history").insert(record).execute()

            if result.data:
                logger.info(f"Configuration change logged: {section}.{field}")
                return True
            else:
                logger.error(f"Failed to log configuration change: {section}.{field}")
                return False

        except Exception as e:
            logger.error(f"Error saving configuration change: {e}")
            return False

    def validate_config(self, config: Dict[str, Any], updates: Optional[Dict[str, Any]] = None) -> Dict[str, List[str]]:
        """Validate configuration values and relationships.
        
        Args:
            config: Full configuration dictionary to validate
            updates: Optional dictionary of updates to validate before applying
            
        Returns:
            Dictionary with 'errors' and 'warnings' lists
        """
        errors = []
        warnings = []
        
        # If updates provided, create a test config with updates applied
        if updates:
            test_config = json.loads(json.dumps(config))  # Deep copy
            for path, new_value in updates.items():
                parts = path.split(".")
                target = test_config
                for part in parts[:-1]:
                    if part not in target:
                        target[part] = {}
                    target = target[part]
                target[parts[-1]] = new_value
            config = test_config
        
        # Validate global settings
        if config.get("global_settings", {}).get("initial_balance", 0) <= 0:
            errors.append("Initial balance must be greater than 0")
            
        # Validate position management
        pos_mgmt = config.get("position_management", {})
        if pos_mgmt.get("max_positions_per_strategy", 0) > pos_mgmt.get("max_positions_total", 100):
            errors.append("Max positions per strategy cannot exceed total max positions")
        
        if pos_mgmt.get("max_positions_per_symbol", 0) > pos_mgmt.get("max_positions_per_strategy", 50):
            warnings.append("Max positions per symbol exceeds max per strategy - may never be reached")
            
        base_size = pos_mgmt.get("position_sizing", {}).get("base_position_size_usd", 50)
        if base_size < 10:
            errors.append("Base position size must be at least $10")
        elif base_size < 25:
            warnings.append("Base position size below $25 may result in poor fee ratios")
            
        # Validate strategy exit parameters
        strategies = config.get("strategies", {})
        for strategy_name, strategy_config in strategies.items():
            if not isinstance(strategy_config, dict):
                continue
                
            exits_by_tier = strategy_config.get("exits_by_tier", {})
            for tier, exits in exits_by_tier.items():
                if not isinstance(exits, dict):
                    continue
                    
                tp = exits.get("take_profit", 0)
                sl = exits.get("stop_loss", 0)
                trail = exits.get("trailing_stop", 0)
                
                # Basic boundary checks
                if tp <= 0 or tp > 1.0:  # 0-100%
                    errors.append(f"{strategy_name}/{tier}: Take profit must be between 0% and 100%")
                if sl <= 0 or sl > 0.5:  # 0-50%
                    errors.append(f"{strategy_name}/{tier}: Stop loss must be between 0% and 50%")
                if trail < 0 or trail > sl:
                    errors.append(f"{strategy_name}/{tier}: Trailing stop cannot exceed stop loss")
                
                # Check minimum profitability (TP must cover fees and slippage)
                min_fees = 0.003  # 0.3% minimum fees + slippage
                if tp < min_fees * 2:
                    errors.append(f"{strategy_name}/{tier}: Take profit ({tp*100:.1f}%) too low to cover fees (~{min_fees*100:.1f}%)")
                elif tp < min_fees * 3:
                    warnings.append(f"{strategy_name}/{tier}: Take profit ({tp*100:.1f}%) provides minimal profit after fees")
                    
        # Validate market protection
        market_protection = config.get("market_protection", {})
        if market_protection.get("enabled"):
            regime = market_protection.get("enhanced_regime", {})
            
            panic = regime.get("panic_threshold", -0.1)
            caution = regime.get("caution_threshold", -0.05)
            euphoria = regime.get("euphoria_threshold", 0.05)
            
            if panic >= caution:
                errors.append("Panic threshold must be more negative than caution threshold")
            if caution >= 0:
                errors.append("Caution threshold must be negative")
            if euphoria <= 0:
                errors.append("Euphoria threshold must be positive")
                
            # Validate volatility thresholds
            vol = market_protection.get("volatility_thresholds", {})
            if vol.get("panic", 12) <= vol.get("high", 8):
                errors.append("Panic volatility must be higher than high volatility")
            if vol.get("high", 8) <= vol.get("moderate", 5):
                errors.append("High volatility must be higher than moderate volatility")
                
            # Validate trade limiter
            limiter = market_protection.get("trade_limiter", {})
            if limiter.get("max_consecutive_stops", 3) < 1:
                errors.append("Max consecutive stops must be at least 1")
            if limiter.get("max_consecutive_stops", 3) > 10:
                warnings.append("Max consecutive stops > 10 may never trigger protection")
                
            # Validate cooldowns
            cooldowns = limiter.get("cooldown_hours_by_tier", {})
            if cooldowns.get("large_cap", 4) > cooldowns.get("mid_cap", 6):
                warnings.append("Large cap cooldown exceeds mid cap - unusual configuration")
                
        # Validate risk management limits
        risk_mgmt = config.get("risk_management", {})
        if risk_mgmt:
            daily_loss_pct = risk_mgmt.get("max_daily_loss_pct", 10)
            if daily_loss_pct <= 0 or daily_loss_pct > 50:
                errors.append("Max daily loss % must be between 0% and 50%")
                
            drawdown = risk_mgmt.get("max_drawdown", 20)
            if drawdown <= daily_loss_pct:
                warnings.append("Max drawdown should typically exceed daily loss limit")
                
            risk_per_trade = risk_mgmt.get("risk_per_trade", 2)
            if risk_per_trade <= 0 or risk_per_trade > 10:
                errors.append("Risk per trade must be between 0% and 10%")
                
        return {"errors": errors, "warnings": warnings}

    def update_config(
        self,
        updates: Dict[str, Any],
        change_type: str = "manual",
        changed_by: Optional[str] = None,
        description: Optional[str] = None,
        validate: bool = True,
    ) -> Dict[str, Any]:
        """Update configuration and save changes to file and database.

        Args:
            updates: Dictionary of updates in dot notation (e.g., {'strategies.DCA.drop_threshold': -3.0})
            change_type: Type of change
            changed_by: User or system making the change
            description: Description of the changes
            validate: Whether to validate before applying

        Returns:
            Dictionary with 'success' boolean and optional 'errors'/'warnings' lists
        """
        try:
            # Load current config
            config = self.load()
            old_config = json.loads(json.dumps(config))  # Deep copy
            
            # Validate if requested
            if validate:
                validation = self.validate_config(config, updates)
                if validation["errors"]:
                    logger.error(f"Configuration validation failed: {validation['errors']}")
                    return {
                        "success": False,
                        "errors": validation["errors"],
                        "warnings": validation["warnings"]
                    }
                elif validation["warnings"]:
                    logger.warning(f"Configuration warnings: {validation['warnings']}")

            # Track all changes
            changes = []

            # Apply updates
            for path, new_value in updates.items():
                # Split path into parts
                parts = path.split(".")

                # Navigate to the target location
                target = config
                for part in parts[:-1]:
                    if part not in target:
                        target[part] = {}
                    target = target[part]

                # Save old value
                old_value = target.get(parts[-1])

                # Update value
                target[parts[-1]] = new_value

                # Track change
                changes.append(
                    {
                        "section": ".".join(parts[:-1]),
                        "field": parts[-1],
                        "old_value": old_value,
                        "new_value": new_value,
                    }
                )

            # Update version and timestamp
            config["version"] = self._increment_version(config.get("version", "1.0.0"))
            config["last_updated"] = datetime.now().isoformat()

            # Save to file
            with open(self._config_path, "w") as f:
                json.dump(config, f, indent=2)

            # Log each change to database
            success = True
            for change in changes:
                if not self.save_config_change(
                    section=change["section"],
                    field=change["field"],
                    old_value=change["old_value"],
                    new_value=change["new_value"],
                    change_type=change_type,
                    changed_by=changed_by,
                    description=description,
                ):
                    success = False

            # Reload config
            self.reload()

            logger.info(f"Configuration updated: {len(changes)} changes applied")
            return {
                "success": success,
                "changes": len(changes),
                "warnings": validation.get("warnings", []) if validate else []
            }

        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
            return {
                "success": False,
                "errors": [str(e)]
            }

    def _increment_version(self, version: str) -> str:
        """Increment version number (e.g., 1.0.0 -> 1.0.1)"""
        try:
            parts = version.split(".")
            parts[-1] = str(int(parts[-1]) + 1)
            return ".".join(parts)
        except:
            return "1.0.1"

    def get_config_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent configuration change history from database.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of configuration change records
        """
        try:
            from src.data.supabase_client import SupabaseClient

            db = SupabaseClient()

            result = (
                db.client.table("config_history")
                .select("*")
                .order("change_timestamp", desc=True)
                .limit(limit)
                .execute()
            )

            return result.data if result.data else []

        except Exception as e:
            logger.error(f"Error fetching configuration history: {e}")
            return []


# Convenience functions for backward compatibility
def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration (backward compatible function).

    Args:
        config_path: Optional path to config file

    Returns:
        Configuration dictionary
    """
    loader = ConfigLoader(config_path)
    return loader.load()


def get_config() -> ConfigLoader:
    """Get the singleton ConfigLoader instance.

    Returns:
        ConfigLoader instance
    """
    return ConfigLoader()
