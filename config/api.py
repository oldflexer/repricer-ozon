"""
Ozon API settings.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    """Ozon Seller API configuration."""

    model_config = SettingsConfigDict(extra="ignore")

    # Ozon API
    OZON_CLIENT_ID: str | None = Field(default=None, description="Client ID for Ozon Seller API")
    OZON_API_KEY: str | None = Field(default=None, description="API Key for Ozon Seller API")
    OZON_API_URL: str = Field(default="https://api-seller.ozon.ru", description="Base URL for Ozon Seller API")

    # Request settings
    API_BATCH_SIZE: int = Field(default=100, description="Batch size for API requests")
    API_MAX_RETRIES: int = Field(default=3, description="Max retry attempts for failed requests")
    API_BATCH_DELAY: float = Field(default=0.2, description="Delay between batches (seconds)")
    API_HTTP_TIMEOUT: float = Field(default=30.0, description="HTTP request timeout (seconds)")