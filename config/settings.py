"""
Main application settings - composes all sub-settings modules.
"""

import os
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
BASE_DIR = Path(__file__).resolve().parent.parent

# Загружаем .env в os.environ
load_dotenv(BASE_DIR / ".env", encoding="utf-8")

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
    # Убрали env_file и env_file_encoding — читаем из os.environ
    model_config = SettingsConfigDict(
        extra="ignore",
    )

    @property
    def DATABASE_PATH_PATH(self) -> Path:
        path = self.DATABASE_PATH
        if "{{INSTANCE_NAME}}" in path:
            path = path.replace("{{INSTANCE_NAME}}", self.INSTANCE_NAME)
        return Path(path)

    @property
    def DATA_FILE_PATH(self) -> Path:
        path = self.DATA_FILE
        if "{{INSTANCE_NAME}}" in path:
            path = path.replace("{{INSTANCE_NAME}}", self.INSTANCE_NAME)
        return Path(path)

# ------------------------------------------------------------------
# 3. Global settings instance
# ------------------------------------------------------------------

# Теперь без явной передачи аргументов — всё из os.environ
settings = Settings()