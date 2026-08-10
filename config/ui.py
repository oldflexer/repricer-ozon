"""
Web UI (Streamlit) settings.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class UiSettings(BaseSettings):
    """Web dashboard authentication and settings."""

    model_config = SettingsConfigDict(env_prefix="WEB_", extra="ignore")

    USER: str = Field(default="admin", description="Login for Streamlit dashboard")
    PASS: str = Field(default="changeme", description="Password for Streamlit dashboard")
