"""
Competitor parser settings.
"""

import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_chrome_profile_path() -> str:
    """Returns platform-appropriate default Chrome profile path."""
    if os.name == "nt":  # Windows
        # Use LOCALAPPDATA for Windows
        local_app_data = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return str(Path(local_app_data) / "Google" / "Chrome" / "User Data" / "Default")
    else:  # Linux/macOS
        # Default Linux path (can be overridden by CHROME_PROFILE_PATH env var)
        return "/home/server/chrome_profile"


class ParserSettings(BaseSettings):
    """Competitor price parser configuration."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    CHROME_PROFILE_PATH: str = Field(default_factory=_default_chrome_profile_path, description="Path to Chrome profile for undetected-chromedriver (auto-detected by OS)")
    MAX_COMPETITORS: int = Field(default=5, description="Maximum number of competitors in Excel (columns Конкурент 1..N)")
    PARSER_RETRIES: int = Field(default=2, description="Number of retry attempts for parsing a single page")
    PARSER_REQUEST_DELAY_MIN: float = Field(default=5.0, description="Minimum delay between parser HTTP requests (seconds)")
    PARSER_REQUEST_DELAY_MAX: float = Field(default=10.0, description="Maximum delay between parser HTTP requests (seconds)")
    EXCEL_LOCK_WAIT_TIMEOUT: int = Field(default=60, description="Timeout waiting for Excel file to be released (seconds)")
    PARSER_LOCK_TIMEOUT: int = Field(default=1800, description="Global parser lock timeout (filelock) (seconds)")
    CHROME_VERSION_MAIN: int = Field(default=150, description="Main Chrome version for driver (fallback if auto-detect fails)")

    # Column name prefixes (for localization)
    COMPETITOR_URL_COLUMN_PREFIX: str = Field(default="Конкурент", description="Prefix for competitor URL column names (e.g., 'Конкурент 1')")

    COMPETITOR_PRICE_COLUMN_PREFIX: str = Field(default="цена", description="Prefix for competitor price column names (e.g., 'Цена 1')")