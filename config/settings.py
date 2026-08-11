"""
Main application settings - composes all sub-settings modules.
"""

from pathlib import Path

import pytz
from dotenv import load_dotenv
from pydantic_settings import SettingsConfigDict

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
        """Returns Path to database file with INSTANCE_NAME substitution."""
        path = self.DATABASE_PATH
        if "{{INSTANCE_NAME}}" in path:
            path = path.replace("{{INSTANCE_NAME}}", self.INSTANCE_NAME)
        return Path(path)

    @property
    def DATA_FILE_PATH(self) -> Path:
        """Returns Path to Excel data file with INSTANCE_NAME substitution."""
        path = self.DATA_FILE
        if "{{INSTANCE_NAME}}" in path:
            path = path.replace("{{INSTANCE_NAME}}", self.INSTANCE_NAME)
        return Path(path)


# ------------------------------------------------------------------
# 3. Global settings instance
# ------------------------------------------------------------------

# Теперь без явной передачи аргументов — всё из os.environ
settings = Settings()
"""Global settings instance for application-wide use."""
