# Changelog

Все заметные изменения в этом проекте.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/),
проект следует [Semantic Versioning](https://semver.org/lang/ru/).

## [1.1.0] - 2026-09-11

### Добавлено
- **scripts/manual_login.py** — скрипт для ручного логина в Ozon Seller с сохранением профиля Chrome (5 минут таймаут, обработка SIGINT/SIGTERM)
- **Инфраструктура деплоя** (`deploy/`):
  - `deploy.sh` — скрипт развёртывания на сервере
  - `deploy/cron.template` — базовый cron-шаблон
  - `deploy/parser.cron.template` — cron для парсера конкурентов
  - `deploy/repricer-web.service.template` — systemd сервис для Streamlit дашборда
  - `deploy/disable_auto_add.cron.template` — cron для отключения автодобавления в акции
  - `deploy/update_price_timer.cron.template` — cron для обновления таймера актуальности цены
  - `deploy/repricer.cron.template` — cron для репрайсинга
- **RealPriceSyncService** — синхронизация реальных цен из шаблона Ozon ДО и ПОСЛЕ репрайсинга
- **UpdatePriceTimerUseCase** и скрипт `actions_update_price_timer.py` — обновление таймера актуальности минимальной цены через API
- **Pre-commit hooks** (`.pre-commit-config.yaml`) — ruff, mypy, black, isort, trailing-whitespace, end-of-file-fixer

### Изменено
- Обновлён `.gitignore` — добавлены исключения для логов, бэкапов, кэшей, профиля Chrome
- Обновлён `.env.example` — добавлены новые переменные окружения
- VS Code настройки (`.vscode/`) — launch.json, settings.json для отладки

### Исправлено
- **ChromeDriver version mismatch** — зафиксирована версия `version_main=152` в `infrastructure/chrome_driver.py`
- **Streamlit asyncio.run() error** — заменено на thread-based `_run_async_in_thread_sync()` в `ui/sidebar.py`
- **Migration 003 duplicate column error** — добавлена проверка существования колонки перед `ALTER TABLE` в `infrastructure/db/repository.py`
- **Missing update_discount_coef method** — добавлен метод в `ProductRepository` (`infrastructure/db/repositories/product_repo.py`)
- **Mypy type error** — добавлен `# type: ignore[no-any-return]` в `ui/sidebar.py`

## [1.0.0] - 2026-08-19

### Добавлено
- **Pipeline Pattern** для репрайсинга (9 изолированных шагов в core/pipeline/)
- **Rich Domain Model** в core/domain/ (Product, PricingStrategy, Value Objects, OzonPricingRules)
- **Protocol-based DI** в core/protocols/ (6 интерфейсов: IApiClient, ILoader, INotifier, 5 Repository Protocols)
- **RealPriceSyncService** — синхронизация реальных цен из шаблона Ozon ДО и ПОСЛЕ репрайсинга
- **UpdatePriceTimerUseCase** и скрипт actions_update_price_timer.py — обновление таймера актуальности минимальной цены
- **Dependency Injector** контейнер (core/container.py) с lifecycle management
- **Domain Model**: Product, PricingStrategy, Value Objects (SKU, Money, Percentage, DiscountCoefficient, TimeInterval), OzonPricingRules
- **Pipeline Steps**: LoadProducts, EnrichProductIds, FetchPricingData, CalculatePrices, PersistToExcel, SubmitPricesToOzon, SaveHistory, SendReport, CleanupDatabase

### Изменено
- Рефакторинг PriceUpdateCoordinator -> Pipeline Pattern
- Рефакторинг PricingOrchestrator -> Legacy (оставлен для совместимости)
- Рефакторинг orchestrator.py -> Legacy
- DI контейнер переведён на dependency-injector
- Репозиторий разбит на 7 миксинов

### Исправлено
- Конкурентный доступ к SQLite (WAL mode + busy_timeout)
- Изоляция логгеров парсера (selenium, uc, wdm)
- Сохранение стилей Excel при точечной записи (openpyxl)

## [0.9.0] - 2026-08-14

### Добавлено
- Базовая архитектура с PriceUpdateCoordinator
- Парсер конкурентов (undetected-chromedriver)
- Отключение автодобавления в акции
- Streamlit дашборд (7 страниц)
- Alembic миграции (2 версии)
- Email уведомления с CSV

## [0.8.0] - 2026-07-22

### Добавлено
- Инициализация проекта
- Ozon API клиент (v3, v5, v1)
- SQLite схема (6 таблиц)
- Базовый репрайсинг через API
