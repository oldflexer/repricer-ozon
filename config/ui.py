"""
Web UI (Streamlit) settings.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class UiSettings(BaseSettings):
    """Web dashboard authentication and settings."""

    model_config = SettingsConfigDict(extra="ignore")

    WEB_USER: str = Field(default="admin", description="Login for Streamlit dashboard")
    WEB_PASS: str = Field(default="changeme", description="Password for Streamlit dashboard")
