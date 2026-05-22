# PLAN.md — План рефакторинга и улучшения архитектуры репрайсера Ozon

## 🎯 Цель

Повысить надёжность, производительность, тестируемость и удобство сопровождения проекта, сохранив полную совместимость с текущей логикой работы (API Ozon, SQLite, Streamlit).

---

## 🔥 Этап 1. Быстрые победы

### 1.1 Вынос констант и коэффициентов в конфиг

- Добавить в `settings.py` и `.env`:
  - `OLD_PRICE_MULTIPLIER = 1.5` (коэффициент для расчёта old_price)
  - `PRICE_ROUND_UP_TO = 100` (шаг округления old_price до сотен)
  - `MANAGE_ELASTIC_BOOSTING = False` (флаг для API)
- Создать функцию `calculate_old_price(price, manual_old_price, multiplier, round_to)` в `core/services.py`.

### 1.2 Оптимизация разбора стратегий

- В `core/entities.py` добавить в `StrategyInterval` поля:
  - `start_time: time`
  - `end_time: time`
- При загрузке Excel (`loader.py`) сразу парсить строки в объекты `time`, избегая повторного `strptime` в `services.py`.

### 1.3 Хелпер для обновления Excel

- В `infrastructure/loader.py` добавить метод:

      def _build_excel_updates(product, result, marginality_week, marginality_month, old_price_update) -> Dict

  чтобы централизовать формирование словаря обновлений.

### 1.4 Добавление индексов в БД (миграция)

- Написать миграцию (ручную или через Alembic) для создания индексов:

      CREATE INDEX IF NOT EXISTS idx_product_sku ON product(sku);
      CREATE INDEX IF NOT EXISTS idx_history_product_timestamp ON product_price_history(product_id, timestamp);
      CREATE INDEX IF NOT EXISTS idx_marginality_product_timestamp ON product_marginality_history(product_id, timestamp);

### 1.5 Централизация конфигурации через Pydantic

- Установить `pydantic-settings`.
- Создать `class Settings(BaseSettings)` в `config/settings.py`, загружающий все переменные из `.env`.
- Заменить `os.getenv` везде на `settings.XXX`.

### 1.6 Docstring для публичных методов

- Добавить описания для:
  - `RepricingUseCase.execute`
  - `PriceCalculationService.calculate`
  - `OzonApiClient.get_product_prices`, `update_prices`
  - `SQLiteRepository.*` (ключевые методы)

---

## ⚙️ Этап 2. Структурные улучшения

### 2.1 Разделение RepricingUseCase на подсервисы

- Создать новый класс `PricingOrchestrator` (или разбить `execute` на приватные методы):
  - `_load_products`
  - `_fetch_product_ids`
  - `_fetch_prices`
  - `_calculate_prices`
  - `_send_updates`
  - `_fetch_real_prices`
  - `_save_history`
  - `_build_report`
- Это позволит легко тестировать каждый шаг.

### 2.2 Внедрение DTO и мапперов

- Создать модуль `core/dto.py` с dataclasses:
  - `ProductEntity` (чистая доменная модель)
  - `ProductViewModel` (для UI)
  - `PriceUpdateRequest` (для API)
- Написать функции `to_entity`, `to_view_model`, `to_api_request`.

### 2.3 Переход на SQLAlchemy Core + Alembic

- Установить `sqlalchemy`, `alembic`.
- Создать метаданные таблиц в `infrastructure/db_meta.py`.
- Написать миграции:
  - `001_initial` (создание всех таблиц)
  - `002_add_real_customer_price` (добавление колонок)
- Переписать `SQLiteRepository` на использование SQLAlchemy Core (session_scope, connection).
- Интегрировать Alembic в `__init__` репозитория (`alembic upgrade head`).

### 2.4 Асинхронный Ozon API клиент

- Заменить `requests` на `httpx.AsyncClient`.
- Изменить сигнатуру методов на `async def`.
- В `RepricingUseCase` (или новом Orchestrator) сделать `execute` асинхронным.
- Использовать `asyncio.gather` для параллельных запросов внутри `get_product_prices`.
- Добавить семафор для ограничения числа одновременных запросов (чтобы не превышать лимиты Ozon).

### 2.5 Улучшение нотификации

- В `mail_notifier.py`:
  - Если количество товаров > `NOTIFICATION_MAX_DETAILS` (20, вынести в конфиг), отправлять только сводку и прикреплять CSV-файл с деталями.
  - Использовать `email.mime.base` для вложения.
- Удалить старый метод `notify_cycle_complete`.

### 2.6 Интеграционные тесты

- Написать тесты для `PricingOrchestrator` (или `use_cases`) с:
  - In‑memory SQLite.
  - Мок-сервер для Ozon API (например, `pytest-httpx`).
- Проверить сценарии:
  - dry‑run (без отправки)
  - успешная отправка всех товаров
  - частичная неудача (ошибка API)
  - отсутствие индексов → fallback на COEFFICIENT_OZON

---

## 🚀 Этап 3. Долгосрочные и опциональные улучшения

### 3.1 Docker и CI/CD

- Создать `Dockerfile` на основе `python:3.11-slim`:
  - Копирование кода
  - Установка зависимостей
  - Запуск `alembic upgrade head` при старте
- Написать `docker-compose.yml` с volume для SQLite файла.
- Добавить GitHub Actions workflow:
  - Линтинг (`flake8`, `black`)
  - Тесты (`pytest`)
  - Сборка Docker образа (при push в `main` или по тегу)

### 3.2 Компонентизация Streamlit UI

- Вынести CSS в отдельный файл `styles.css`.
- Создать функции:
  - `render_sidebar()` – боковая панель
  - `render_product_table(products)`
  - `render_history_table()`
  - `render_price_chart(selected)`
  - `render_statistics()`
- Добавить UI-тесты с `pytest-streamlit` или Playwright.

### 3.3 Кэширование цен (опционально)

- Для товаров, у которых индексы меняются редко, добавить кэш (например, `cachetools.TTLCache` с TTL=300 секунд).
- При получении цен сначала проверять кэш, при отправке – инвалидировать.

### 3.4 Структурированное логирование

- Установить `structlog`.
- Настроить вывод в JSON для логов (консоль + файл).
- Добавить поля `request_id`, `sku`, `product_id` в ключевые точки.

### 3.5 Абстракция для работы с Excel (ILoader)

- Создать интерфейс `ILoader` в `core/repository.py`.
- Реализовать `ExcelLoader` (текущий `DataLoader`).
- В будущем можно будет легко добавить загрузку из CSV, Google Sheets.

### 3.6 Мониторинг метрик

- Интегрировать `prometheus_client`.
- Собирать метрики:
  - `repricer_products_loaded`
  - `repricer_prices_updated_total`
  - `repricer_api_errors_total`
  - `repricer_cycle_duration_seconds`

---

*Последнее обновление: 2026-05-22*