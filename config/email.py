"""
Email notification settings.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EmailSettings(BaseSettings):
    """Email/SMTP configuration for notifications."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    SMTP_HOST: str = Field(default="smtp.yandex.ru", description="SMTP server host")
    SMTP_PORT: int = Field(default=587, description="SMTP server port")
    SMTP_USER: str = Field(default="", description="SMTP username")
    SMTP_PASSWORD: str = Field(default="", description="SMTP password (or app password)")
    SENDER_EMAIL: str = Field(default="", description="Sender email address")
    RECIPIENT_EMAIL: str = Field(default="", description="Recipient email address")
    NOTIFICATION_MAX_DETAILS: int = Field(
        default=20, description="Max products to detail in email; excess goes to CSV attachment"
    )
