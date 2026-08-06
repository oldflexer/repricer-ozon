"""
Main application settings - composes all sub-settings modules.

This is the single entry point for accessing all configuration.
"""

from pathlib import Path
from typing import Optional

import pytz
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

from config.api import ApiSettings
from config.db import DatabaseSettings
from config.email import EmailSettings
from config.instance import InstanceSettings
from config.parser import ParserSettings
from config.pricing import PricingSettings
from config.ui import UiSettings

# ------------------------------------------------------------------
# 1. Base configuration
# ------------------------------------------------------------------

TIMEZONE = pytz.timezone("Europe/Moscow")
"""Application timezone (Moscow)."""

BASE_DIR = Path(__file__).resolve().parent.parent
"""Project root directory."""

load_dotenv(BASE_DIR / ".env")
"""Load environment variables from .env file."""


# ------------------------------------------------------------------
# 2. Composed Settings class
# ------------------------------------------------------------------

class Settings(
    InstanceSettings,
    ApiSettings,
    DatabaseSettings,
    EmailSettings,
    PricingSettings,
    ParserSettings,
    UiSettings,
):
    """
    Composed settings from all modules.

    Uses multiple inheritance to combine all setting groups.
    Environment variables are loaded once and distributed to appropriate
    sub-classes based on their env_prefix configuration.
    """

    model_config = SettingsConfigDict(extra="ignore", env_nested_delimiter="__")


# ------------------------------------------------------------------
# 3. Global settings instance
# ------------------------------------------------------------------

settings = Settings()
"""Global settings instance for application-wide use."""