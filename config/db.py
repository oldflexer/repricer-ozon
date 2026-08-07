"""
Database settings.
"""

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from config.instance import InstanceSettings


class DatabaseSettings(BaseSettings):
    """SQLite database configuration."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    DATABASE_PATH: str = Field(default="./data/repricer_{{INSTANCE_NAME}}.db", description="Path to SQLite database file")
    CLEANUP_MONTHS: int = Field(default=3, description="Data retention period in months")
    CLEANUP_DAYS_THRESHOLD: int = Field(default=1, description="Minimum days between auto cleanups")

    @property
    def DATABASE_PATH_PATH(self) -> Path:
            """Returns Path to database file with INSTANCE_NAME substitution."""
            # INSTANCE_NAME is inherited from InstanceSettings via multiple inheritance in main Settings
            path = self.DATABASE_PATH
            if "{{INSTANCE_NAME}}" in path:
                path = path.replace("{{INSTANCE_NAME}}", self.INSTANCE_NAME)
            return Path(path)