"""
Ozon API settings.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    """Ozon Seller API configuration."""

    model_config = SettingsConfigDict(env_prefix="OZON_", extra="ignore")

    CLIENT_ID: str | None = Field(default=None, description="Client ID for Ozon Seller API")
    API_KEY: str | None = Field(default=None, description="API Key for Ozon Seller API")
    API_URL: str = Field(default="https://api-seller.ozon.ru", description="Base URL for Ozon Seller API")

    # Request settings
    BATCH_SIZE: int = Field(default=100, description="Batch size for API requests")
    MAX_RETRIES: int = Field(default=3, description="Max retry attempts for failed requests")
    BATCH_DELAY: float = Field(default=0.2, description="Delay between batches (seconds)")
    HTTP_TIMEOUT: float = Field(default=30.0, description="HTTP request timeout (seconds)")

    # Backward compatibility properties
    @property
    def API_BATCH_SIZE(self) -> int:
        return self.BATCH_SIZE

    @property
    def API_MAX_RETRIES(self) -> int:
        return self.MAX_RETRIES

    @property
    def API_BATCH_DELAY(self) -> float:
        return self.BATCH_DELAY

    @property
    def API_HTTP_TIMEOUT(self) -> float:
        return self.HTTP_TIMEOUT

    @property
    def OZON_API_URL(self) -> str:
        return self.API_URL

    @property
    def OZON_CLIENT_ID(self) -> str | None:
        return self.CLIENT_ID

    @property
    def OZON_API_KEY(self) -> str | None:
        return self.API_KEY
