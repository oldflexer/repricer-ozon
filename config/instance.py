"""
Instance/multi-tenancy settings.
"""

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class InstanceSettings(BaseSettings):
    """Instance identification and multi-tenancy settings."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    INSTANCE_NAME: str = Field(default="Ozon", description="Instance name (used in file names, logs, dashboard title)")
    DATA_FILE: str = Field(default="./data/products_{{INSTANCE_NAME}}.xlsx", description="Path to Excel data file (supports {{INSTANCE_NAME}} template)")

    @property
    def DATA_FILE_PATH(self) -> Path:
        """Returns Path to data file with INSTANCE_NAME substitution."""
        path = self.DATA_FILE
        if "{{INSTANCE_NAME}}" in path:
            path = path.replace("{{INSTANCE_NAME}}", self.INSTANCE_NAME)
        return Path(path)