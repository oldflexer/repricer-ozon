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

    DATA_FILE: str = "./data/products.xlsx"
    DATABASE_PATH: str = "./data/repricer.db"

    NOTIFICATION_MAX_DETAILS: int = 20

    WEB_USER: str = "admin"
    WEB_PASS: str = "changeme"

    # Chrome profile path for undetected-chromedriver
    CHROME_PROFILE_PATH: str = "/home/server/chrome_profile"

    model_config = SettingsConfigDict(extra='ignore')

    @property
    def DATA_FILE_PATH(self) -> Path:
        """Возвращает Path к файлу данных с подстановкой INSTANCE_NAME."""
        path = self.DATA_FILE
        if "{{INSTANCE_NAME}}" in path:
            path = path.replace("{{INSTANCE_NAME}}", self.INSTANCE_NAME)
        return Path(path)

    @property
    def DATABASE_PATH_PATH(self) -> Path:
        """Возвращает Path к файлу БД с подстановкой INSTANCE_NAME."""
        path = self.DATABASE_PATH
        if "{{INSTANCE_NAME}}" in path:
            path = path.replace("{{INSTANCE_NAME}}", self.INSTANCE_NAME)
        return Path(path)


settings = Settings()