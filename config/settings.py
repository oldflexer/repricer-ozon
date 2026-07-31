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

    # ------------------------------------------------------------------
    # Настройки парсера конкурентов
    # ------------------------------------------------------------------
    # Максимальное количество конкурентов в Excel (колонки Конкурент 1..N)
    MAX_COMPETITORS: int = 5
    # Количество попыток парсинга одной страницы (при неудаче)
    PARSER_RETRIES: int = 2
    # Диапазон задержки между HTTP-запросами парсера (сек)
    PARSER_REQUEST_DELAY_MIN: float = 5.0
    PARSER_REQUEST_DELAY_MAX: float = 10.0
    # Таймаут ожидания освобождения Excel-файла (сек)
    EXCEL_LOCK_WAIT_TIMEOUT: int = 60
    # Таймаут глобальной блокировки парсера (filelock) (сек)
    PARSER_LOCK_TIMEOUT: int = 1800
    # Основная версия Chrome для undetected-chromedriver (если не определяется автоматически)
    CHROME_VERSION_MAIN: int = 150

    # ------------------------------------------------------------------
    # Настройки загрузки Excel
    # ------------------------------------------------------------------
    # Количество интервалов стратегии, читаемых из Excel (Интервал 1..N)
    SCHEDULE_INTERVALS_COUNT: int = 4

    # ------------------------------------------------------------------
    # Настройки Ozon API клиента
    # ------------------------------------------------------------------
    # Размер батча для запросов к API (product info, prices)
    API_BATCH_SIZE: int = 100
    # Количество повторных попыток при ошибках API
    API_MAX_RETRIES: int = 3
    # Задержка между батчами (сек)
    API_BATCH_DELAY: float = 0.2
    # Таймаут HTTP-запроса (сек)
    API_HTTP_TIMEOUT: float = 30.0

    # ------------------------------------------------------------------
    # Настройки репрайсинга
    # ------------------------------------------------------------------
    # Пауза (сек) после отправки цен перед запросом актуальных цен (для получения real_price)
    WAIT_AFTER_UPDATE_SECONDS: int = 10

    # ------------------------------------------------------------------
    # Настройки автоматической очистки БД
    # ------------------------------------------------------------------
    # Срок хранения данных (месяцев) – записи старше удаляются
    CLEANUP_MONTHS: int = 3
    # Минимальное количество дней между очистками (чтобы не запускать слишком часто)
    CLEANUP_DAYS_THRESHOLD: int = 1


settings = Settings()