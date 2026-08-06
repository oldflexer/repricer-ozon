"""
Настройки приложения (конфигурация).

Загружает переменные окружения из файла `.env` и предоставляет
доступ к ним через единый объект `settings`.

Поддерживается мультитенантность: пути к файлам данных и БД могут
содержать шаблон `{{INSTANCE_NAME}}`, который заменяется на
значение переменной `INSTANCE_NAME`.
"""

from pathlib import Path
from typing import Optional

import pytz
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# ------------------------------------------------------------------
# 1. Базовая конфигурация (часовой пояс, корень проекта, загрузка .env)
# ------------------------------------------------------------------

TIMEZONE = pytz.timezone("Europe/Moscow")
"""Часовой пояс, используемый в приложении (Москва)."""

BASE_DIR = Path(__file__).resolve().parent.parent
"""Корневая директория проекта."""

load_dotenv(BASE_DIR / ".env")
"""Загрузка переменных окружения из файла .env."""


# ------------------------------------------------------------------
# 2. Класс настроек
# ------------------------------------------------------------------

class Settings(BaseSettings):
    """
    Настройки приложения, загружаемые из переменных окружения.

    Все поля имеют значения по умолчанию, которые могут быть
    переопределены через .env-файл.
    """

    # ---------- Экземпляр (мультитенантность) ----------
    INSTANCE_NAME: str = "Ozon"
    """Имя инстанса (используется в именах файлов, логов, заголовках дашборда)."""

    # ---------- Ozon Seller API ----------
    OZON_CLIENT_ID: Optional[str] = None
    """Client-ID для Ozon Seller API."""

    OZON_API_KEY: Optional[str] = None
    """API-ключ для Ozon Seller API."""

    OZON_API_URL: str = "https://api-seller.ozon.ru"
    """Базовый URL Ozon Seller API."""

    # ---------- Email-уведомления ----------
    SMTP_HOST: str = "smtp.yandex.ru"
    """SMTP-сервер для отправки email-уведомлений."""

    SMTP_PORT: int = 587
    """Порт SMTP-сервера."""

    SMTP_USER: str = ""
    """Имя пользователя для SMTP-авторизации."""

    SMTP_PASSWORD: str = ""
    """Пароль для SMTP-авторизации (или пароль приложения)."""

    SENDER_EMAIL: str = ""
    """Email-адрес отправителя."""

    RECIPIENT_EMAIL: str = ""
    """Email-адрес получателя уведомлений."""

    NOTIFICATION_MAX_DETAILS: int = 20
    """Максимальное количество товаров для детализации в письме; при превышении отправляется CSV."""

    # ---------- Коэффициенты расчёта цен ----------
    COEFFICIENT_OZON: float = 0.5
    """Коэффициент для товаров без индексов (по умолчанию 0.5)."""

    OLD_PRICE_MULTIPLIER: float = 1.5
    """Коэффициент для расчёта old_price (цена до скидки)."""

    PRICE_ROUND_UP_TO: int = 100
    """Шаг округления old_price вверх (кратность)."""

    MANAGE_ELASTIC_BOOSTING: bool = False
    """Отправлять ли параметр manage_elastic_boosting_through_price = true."""

    # ---------- Файлы данных ----------
    DATA_FILE: str = "./data/products.xlsx"
    """Путь к Excel-файлу с товарами (может содержать {{INSTANCE_NAME}})."""

    DATABASE_PATH: str = "./data/repricer.db"
    """Путь к SQLite-базе данных (может содержать {{INSTANCE_NAME}})."""

    # ---------- Аутентификация веб-интерфейса ----------
    WEB_USER: str = "admin"
    """Логин для доступа к Streamlit-дашборду."""

    WEB_PASS: str = "changeme"
    """Пароль для доступа к Streamlit-дашборду."""

    # ---------- Парсер конкурентов ----------
    CHROME_PROFILE_PATH: str = "/home/server/chrome_profile"
    """Путь к профилю Chrome для undetected-chromedriver."""

    MAX_COMPETITORS: int = 5
    """Максимальное количество конкурентов в Excel (колонки Конкурент 1..N)."""

    PARSER_RETRIES: int = 2
    """Количество попыток парсинга одной страницы при неудаче."""

    PARSER_REQUEST_DELAY_MIN: float = 5.0
    """Минимальная задержка между HTTP-запросами парсера (сек)."""

    PARSER_REQUEST_DELAY_MAX: float = 10.0
    """Максимальная задержка между HTTP-запросами парсера (сек)."""

    EXCEL_LOCK_WAIT_TIMEOUT: int = 60
    """Таймаут ожидания освобождения Excel-файла (сек)."""

    PARSER_LOCK_TIMEOUT: int = 1800
    """Таймаут глобальной блокировки парсера (filelock) (сек)."""

    CHROME_VERSION_MAIN: int = 150
    """Основная версия Chrome для драйвера (если не определяется автоматически)."""

    # Названия колонок конкурентов в Excel (для локализации/настройки)
    COMPETITOR_URL_COLUMN_PREFIX: str = "Конкурент"
    """Префикс названия колонки с URL конкурента (например, 'Конкурент 1')."""

    COMPETITOR_PRICE_COLUMN_PREFIX: str = "Цена"
    """Префикс названия колонки с ценой конкурента (например, 'Цена 1')."""

    # ---------- Загрузка Excel ----------
    SCHEDULE_INTERVALS_COUNT: int = 4
    """Количество интервалов стратегии, читаемых из Excel (Интервал 1..N)."""

    # ---------- Ozon API ----------
    API_BATCH_SIZE: int = 100
    """Размер батча для запросов к API (product info, prices)."""

    API_MAX_RETRIES: int = 3
    """Количество повторных попыток при ошибках API."""

    API_BATCH_DELAY: float = 0.2
    """Задержка между батчами при массовых запросах (сек)."""

    API_HTTP_TIMEOUT: float = 30.0
    """Таймаут HTTP-запроса к API (сек)."""

    # ---------- Репрайсинг ----------
    WAIT_AFTER_UPDATE_SECONDS: int = 10
    """
    Пауза (сек) после отправки цен перед запросом актуальных цен
    (для получения real_price).
    """

    # ---------- Очистка БД ----------
    CLEANUP_MONTHS: int = 3
    """Срок хранения данных в БД (месяцев) – записи старше удаляются."""

    CLEANUP_DAYS_THRESHOLD: int = 1
    """Минимальное количество дней между автоматическими очистками."""

    # ---------- Дополнительная конфигурация Pydantic ----------
    model_config = SettingsConfigDict(extra="ignore")
    """Разрешаем игнорировать лишние переменные окружения."""

    # ---------- Свойства для путей с подстановкой ----------
    @property
    def DATA_FILE_PATH(self) -> Path:
        """
        Возвращает Path к файлу данных с подстановкой INSTANCE_NAME.

        Если в пути присутствует шаблон {{INSTANCE_NAME}}, он заменяется
        на значение атрибута INSTANCE_NAME.
        """
        path = self.DATA_FILE
        if "{{INSTANCE_NAME}}" in path:
            path = path.replace("{{INSTANCE_NAME}}", self.INSTANCE_NAME)
        return Path(path)

    @property
    def DATABASE_PATH_PATH(self) -> Path:
        """
        Возвращает Path к файлу БД с подстановкой INSTANCE_NAME.

        Если в пути присутствует шаблон {{INSTANCE_NAME}}, он заменяется
        на значение атрибута INSTANCE_NAME.
        """
        path = self.DATABASE_PATH
        if "{{INSTANCE_NAME}}" in path:
            path = path.replace("{{INSTANCE_NAME}}", self.INSTANCE_NAME)
        return Path(path)


# ------------------------------------------------------------------
# 3. Глобальный объект настроек
# ------------------------------------------------------------------

settings = Settings()
"""Единственный экземпляр настроек для использования во всём приложении."""