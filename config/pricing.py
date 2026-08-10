"""
Pricing calculation settings.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PricingSettings(BaseSettings):
    """Pricing calculation coefficients and parameters."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    COEFFICIENT_OZON: float = Field(
        default=0.5, description="Default discount coefficient for products without indexes"
    )
    OLD_PRICE_MULTIPLIER: float = Field(
        default=1.5, description="Multiplier for calculating old_price (price before discount)"
    )
    PRICE_ROUND_UP_TO: int = Field(
        default=100, description="Rounding step for old_price (round up to nearest)"
    )
    MANAGE_ELASTIC_BOOSTING: bool = Field(
        default=False, description="Send manage_elastic_boosting_through_price=true to Ozon"
    )
    WAIT_AFTER_UPDATE_SECONDS: int = Field(
        default=10, description="Pause after price update before fetching actual prices (seconds)"
    )

    # Strategy settings
    SCHEDULE_INTERVALS_COUNT: int = Field(
        default=4, description="Number of strategy intervals to read from Excel"
    )
