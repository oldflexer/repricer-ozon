"""
Web UI (Streamlit) settings.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class UiSettings(BaseSettings):
    """Web dashboard authentication and settings."""

    model_config = SettingsConfigDict(extra="ignore")

    WEB_USER: str = Field(default="admin", description="Login for Streamlit dashboard")
    WEB_PASS: str = Field(default="", description="Plain text password (will be migrated to hash on first run)")
    WEB_PASS_HASH: str = Field(default="", description="Bcrypt hash of the password")
    
    # Session settings
    SESSION_TIMEOUT_MINUTES: int = Field(default=60, description="Session timeout in minutes")
    SESSION_SECRET_KEY: str = Field(default="", description="Secret key for session signing")
