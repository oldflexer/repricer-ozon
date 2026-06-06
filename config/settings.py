# config/settings.py
from pathlib import Path
from dotenv import load_dotenv
import pytz
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

TIMEZONE = pytz.timezone('Europe/Moscow')

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


class Settings(BaseSettings):
    INSTANCE_NAME: str = "Ozon"
    
    OZON_CLIENT_ID: Optional[str] = None
    OZON_API_KEY: Optional[str] = None
    OZON_API_URL: str = "https://api-seller.ozon.ru"

    SMTP_HOST: str = "smtp.yandex.ru"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SENDER_EMAIL: str = ""
    RECIPIENT_EMAIL: str = ""

    COEFFICIENT_OZON: float = 0.5
    OLD_PRICE_MULTIPLIER: float = 1.5
    PRICE_ROUND_UP_TO: int = 100
    MANAGE_ELASTIC_BOOSTING: bool = False

    DATA_FILE: Path = BASE_DIR / "data" / "products.xlsx"
    DATABASE_PATH: Path = BASE_DIR / "data" / "repricer.db"

    NOTIFICATION_MAX_DETAILS: int = 20

    WEB_USER: str = "admin"
    WEB_PASS: str = "changeme"

    model_config = SettingsConfigDict(extra='ignore')


settings = Settings()