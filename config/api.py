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

        # Retry backoff settings
    RETRY_BACKOFF_BASE: float = Field(
        default=1.0, description="Base for exponential backoff (delay = base ** (attempt - 1))"
    )

    # Circuit Breaker settings for Ozon API
    API_CB_FAILURE_THRESHOLD: int = Field(
        default=5, description="Failure threshold for Ozon API circuit breaker"
    )
    API_CB_RECOVERY_TIMEOUT: float = Field(
        default=30.0, description="Recovery timeout for Ozon API circuit breaker (seconds)"
    )
    API_CB_SUCCESS_THRESHOLD: int = Field(
        default=2, description="Success threshold for Ozon API circuit breaker"
    )

        # Circuit Breaker settings for Ozon Parser
    PARSER_CB_FAILURE_THRESHOLD: int = Field(
        default=3, description="Failure threshold for Ozon Parser circuit breaker"
    )
    PARSER_CB_RECOVERY_TIMEOUT: float = Field(
        default=60.0, description="Recovery timeout for Ozon Parser circuit breaker (seconds)"
    )
    PARSER_CB_SUCCESS_THRESHOLD: int = Field(
        default=1, description="Success threshold for Ozon Parser circuit breaker"
    )

    # Price timer update batch size
    API_TIMER_BATCH_SIZE: int = Field(
        default=1000, description="Batch size for updating price timer (maximum 1000 per Ozon API)"
    )
