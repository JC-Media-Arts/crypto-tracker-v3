"""Application settings and configuration management."""

import os
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Polygon.io
    polygon_api_key: str = Field(..., env="POLYGON_API_KEY")

    # Supabase
    supabase_url: str = Field(..., env="SUPABASE_URL")
    supabase_key: str = Field(..., env="SUPABASE_KEY")

    # Kraken
    kraken_api_key: str = Field(..., env="KRAKEN_API_KEY")
    kraken_api_secret: str = Field(..., env="KRAKEN_API_SECRET")

    # Slack
    slack_webhook_url: str = Field(..., env="SLACK_WEBHOOK_URL")
    slack_bot_token: str = Field(..., env="SLACK_BOT_TOKEN")
    slack_app_token: Optional[str] = Field(None, env="SLACK_APP_TOKEN")
    slack_signing_secret: Optional[str] = Field(None, env="SLACK_SIGNING_SECRET")

    # Trading Configuration
    position_size: float = Field(100.0, env="POSITION_SIZE")
    max_positions: int = Field(5, env="MAX_POSITIONS")
    stop_loss_pct: float = Field(5.0, env="STOP_LOSS_PCT")
    take_profit_pct: float = Field(10.0, env="TAKE_PROFIT_PCT")
    min_confidence: float = Field(0.60, env="MIN_CONFIDENCE")

    # System
    timezone: str = Field("America/Los_Angeles", env="TIMEZONE")
    environment: str = Field("development", env="ENVIRONMENT")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    feature_update_interval: int = Field(120, env="FEATURE_UPDATE_INTERVAL")  # seconds

    # Optional API keys for future use
    github_api_key: Optional[str] = Field(None, env="GITHUB_API_KEY")
    lunarcrush_api_key: Optional[str] = Field(None, env="LUNARCRUSH_API_KEY")
    coingecko_api_key: Optional[str] = Field(None, env="COINGECKO_API_KEY")

    # Paths - using model_validator for initialization
    @property
    def project_root(self) -> str:
        return os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )

    @property
    def data_dir(self) -> str:
        path = os.path.join(self.project_root, "data")
        os.makedirs(path, exist_ok=True)
        return path

    @property
    def logs_dir(self) -> str:
        path = os.path.join(self.project_root, "logs")
        os.makedirs(path, exist_ok=True)
        return path

    @property
    def models_dir(self) -> str:
        path = os.path.join(self.project_root, "models")
        os.makedirs(path, exist_ok=True)
        return path

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == "production"

    @property
    def is_testing(self) -> bool:
        """Check if running in testing mode."""
        return self.environment == "testing"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
