"""
Competitor parser settings.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ParserSettings(BaseSettings):
    """Competitor price parser configuration."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    CHROME_PROFILE_PATH: str = Field(default="/home/server/chrome_profile", description="Path to Chrome profile for undetected-chromedriver")
    MAX_COMPETITORS: int = Field(default=5, description="Maximum number of competitors in Excel (columns Конкурент 1..N)")
    PARSER_RETRIES: int = Field(default=2, description="Number of retry attempts for parsing a single page")
    PARSER_REQUEST_DELAY_MIN: float = Field(default=5.0, description="Minimum delay between parser HTTP requests (seconds)")
    PARSER_REQUEST_DELAY_MAX: float = Field(default=10.0, description="Maximum delay between parser HTTP requests (seconds)")
    EXCEL_LOCK_WAIT_TIMEOUT: int = Field(default=60, description="Timeout waiting for Excel file to be released (seconds)")
    PARSER_LOCK_TIMEOUT: int = Field(default=1800, description="Global parser lock timeout (filelock) (seconds)")
    CHROME_VERSION_MAIN: int = Field(default=150, description="Main Chrome version for driver (fallback if auto-detect fails)")

    # Column name prefixes (for localization)
    COMPETITOR_URL_COLUMN_PREFIX: str = Field(default="Конкурент", description="Prefix for competitor URL column names (e.g., 'Конкурент 1')")
    COMPETITOR_PRICE_COLUMN_PREFIX: str = Field(default="Цена", description="Prefix for competitor price column names (e.g., 'Цена 1')")