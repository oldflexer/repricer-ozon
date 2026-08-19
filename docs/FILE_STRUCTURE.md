# Структура файлов и папок проекта repricer-ozon

`
repricer-ozon/
│
├── app.py                          # Точка входа Streamlit-дашборда
├── requirements.txt                # Python-зависимости
├── alembic.ini                     # Конфигурация Alembic (миграции БД)
├── .env                            # Переменные окружения (секреты, настройки)
├── .env.example                    # Пример .env
├── pyproject.toml                  # Конфигурация проекта (ruff, mypy, pytest, deps)
├── README.md                       # Документация проекта
│
├── config/                         # Слой конфигурации
│   ├── __init__.py
│   ├── settings.py                 # Pydantic-настройки (env, пути, константы)
│   ├── api.py                      # API-настройки (batch size, retries, timeout)
│   ├── db.py                       # DB-настройки (путь, WAL mode)
│   ├── email.py                    # SMTP-настройки
│   ├── instance.py                 # Instance-специфичные пути
│   ├── parser.py                   # Парсер-настройки (lock timeout, retries)
│   ├── pricing.py                  # Ценообразование (коэффициенты, стратегии)
│   └── ui.py                       # UI-настройки (web user/pass)
│
├── core/                           # Доменный слой (бизнес-логика)
│   ├── __init__.py
│   ├── container.py                # DI-контейнер (dependency-injector, singletons/factories)
│   ├── entities.py                 # Dataclass-модели: ProductInfo, PricingData, StrategyInterval, PriceCalculationResult
│   ├── dto.py                      # Data Transfer Objects (API-контракты)
│   ├── mappers.py                  # Мапперы entities ↔ DTO, build_price_update_request
│   ├── enums.py                    # StrategyType (IntEnum), parse_strategy_value
│   ├── repository.py               # Legacy абстракции: IProductRepository, ILoader
│   ├── price_coordinator.py        # Legacy оркестратор (оставлен для совместимости)
│   ├── orchestrator.py             # Legacy оркестратор (оставлен для совместимости)
│   ├── domain/                     # 🆕 Rich Domain Model
│   │   ├── __init__.py
│   │   ├── product.py              # Product, PricingStrategy — инкапсуляция бизнес-логики
│   │   ├── pricing_rules.py        # OzonPricingRules — все правила Ozon в одном месте
│   │   └── value_objects.py        # SKU, Money, Percentage, DiscountCoefficient, TimeInterval
│   ├── pipeline/                   # 🆕 Pipeline Pattern (основной поток репрайсинга)
│   │   ├── __init__.py
│   │   ├── orchestrator.py         # PipelineOrchestrator — выполнение последовательности шагов
│   │   └── steps.py                # 9 шагов: LoadProducts → EnrichProductIds → FetchPricingData → CalculatePrices → PersistToExcel → SubmitPricesToOzon → SaveHistory → SendReport → CleanupDatabase
│   ├── protocols/                  # 🆕 Protocol Interfaces (для DI и тестирования)
│   │   ├── __init__.py
│   │   ├── api.py                  # IApiClient
│   │   ├── loader.py               # ILoader
│   │   ├── notifier.py             # INotifier
│   │   └── repository.py           # IProductRepository, IPriceHistoryRepository, IAnalyticsRepository, IMarginalityRepository, IMaintenanceRepository
│   ├── services/                   # Бизнес-сервисы
│   │   ├── __init__.py
│   │   ├── price_calculation.py    # PriceCalculationService — алгоритм расчёта цены и маржи
│   │   ├── action_service.py       # ActionService — работа с акциями Ozon
│   │   ├── history_service.py      # HistoryService — сохранение истории и агрегатов
│   │   ├── migration_service.py    # MigrationService — запуск Alembic
│   │   └── real_price_sync.py      # RealPriceSyncService — синхронизация реальных цен из шаблона Ozon
│   └── use_cases/                  # Use Cases (точки входа в бизнес-логику)
│       ├── __init__.py
│       ├── repricing.py            # RepricingUseCase — обёртка над Pipeline
│       ├── disable_auto_add.py     # DisableAutoAddUseCase — отключение автодобавления в акции
│       ├── parse_competitor_prices.py # ParseCompetitorPricesUseCase — парсинг конкурентов
│       ├── base_parser.py          # BaseParserUseCase — базовый класс для парсеров
│       └── update_price_timer.py   # UpdatePriceTimerUseCase — обновление таймера актуальности цены
│
├── infrastructure/                 # Слой инфраструктуры (реализация протоколов)
│   ├── __init__.py
│   ├── db/                         # SQLiteRepository (разбит на миксины)
│   │   ├── __init__.py
│   │   ├── repository.py           # SQLiteRepository + run_migrations_once()
│   │   ├── connection.py           # DBConnectionMixin (PRAGMA, WAL)
│   │   ├── crud.py                 # CRUDMixin
│   │   ├── strategies.py           # StrategyMixin
│   │   ├── history.py              # HistoryMixin
│   │   ├── marginality.py          # MarginalityMixin
│   │   ├── analytics.py            # AnalyticsMixin
│   │   └── maintenance.py          # MaintenanceMixin
│   ├── excel_loader.py             # ExcelLoader — реализация ILoader (чтение/запись Excel)
│   ├── ozon_api.py                 # OzonApiClient — реализация IApiClient (v3, v5, v1)
│   ├── ozon_seller.py              # OzonSellerClient — Selenium для шаблона цен
│   ├── ozon_competitor.py          # OzonPriceParser — парсер цен конкурентов
│   ├── mail_notifier.py            # MailNotifier — реализация INotifier (email + CSV)
│   ├── logger.py                   # Structlog + TimedRotatingFileHandler
│   ├── file_utils.py               # Утилиты: блокировка Excel, безопасное сохранение
│   ├── chrome_driver.py            # ChromeDriverManager (undetected-chromedriver + fallback)
│   ├── circuit_breaker.py          # CircuitBreaker для API/парсера
│   ├── template_parser.py          # TemplateParser (zip XML + openpyxl fallback)
│   └── x_display.py                # Поиск доступного X-сервера для headless-браузера (Linux)
│
├── scripts/                        # CLI-точки входа (исполняемые скрипты)
│   ├── __init__.py
│   ├── common.py                   # Общие утилиты (сигналы, логирование)
│   ├── repricer.py                 # Запуск репрайсинга → синхронизация → Pipeline → синхронизация
│   ├── competitors_parser.py       # Запуск парсера цен конкурентов
│   ├── actions_disable_auto_add.py # Запуск отключения автодобавления (CLI, --dry-run)
│   ├── actions_update_price_timer.py # Запуск обновления таймера актуальности цены
│   ├── health_check.py             # Проверка здоровья (диск, БД, Excel)
│   └── upgrade_db.py               # Ручной запуск миграций
│
├── ui/                             # Слой представления (Streamlit UI)
│   ├── __init__.py
│   ├── app.py                      # Точка входа Streamlit, роутинг по страницам
│   ├── auth.py                     # Аутентификация в дашборде
│   ├── sidebar.py                  # Боковая панель: запуск репрайсинга/парсинга, загрузка/скачивание Excel
│   ├── cache.py                    # Кэширование Streamlit (TTL 3600с) + фабрики объектов
│   └── pages/                      # Страницы дашборда
│       ├── __init__.py
│       ├── summary.py              # Сводка (KPI, графики за 7 дней, топ-3/худшие-3)
│       ├── statistics.py           # Статистика (распределение маржи, анализ стратегий, ROI)
│       ├── analytics.py            # Аналитика (динамика, прогноз полиномиальной регрессией, отклонения индексов)
│       ├── analysis.py             # Анализ (комиссии FBS, индексы Ozon, ABC-анализ, диаграмма Парето)
│       ├── tables.py               # Просмотр всех таблиц БД в интерактивном dataframe
│       ├── requests.py             # Управление товарами (история цен, удаление)
│       └── service.py              # Сервис (heatmap, работа с БД, диагностика, смена пароля)
│
├── static/                         # Статические ресурсы
│   ├── favicon.ico
│   └── styles.css                  # CSS-стили для Streamlit
│
├── migrations/                     # Миграции Alembic
│   ├── env.py                      # Конфигурация окружения Alembic
│   ├── script.py.mako              # Шаблон файла миграции
│   └── versions/
│       ├── 001_initial_schema.py   # Схема БД: product, strategy, product_strategy, *_history, maintenance
│       └── 002_add_daily_aggregates_and_logs.py  # Таблицы product_price_daily, price_calculation_logs
│
├── data/                           # runtime-данные (создаётся автоматически)
│   ├── products_{{INSTANCE_NAME}}.xlsx               # Входной Excel-файл с товарами
│   └── repricer_{{INSTANCE_NAME}}.db                 # SQLite база данных
│
├── logs/                           # Лог-файлы (создаётся автоматически)
│   ├── repricer-{INSTANCE}.log     # Логи репрайсера (ротация по дням, 7 бэкапов)
│   └── parser-{INSTANCE}.log       # Логи парсера (ротация по дням, 7 бэкапов)
│
├── tests/                          # Unit- и интеграционные тесты
│   ├── __init__.py
│   ├── test_api_client.py
│   ├── test_database.py
│   ├── test_entities.py
│   ├── test_excel_loader.py
│   ├── test_file_utils.py
│   ├── test_integration.py
│   ├── test_loader.py
│   ├── test_mail_notifier.py
│   ├── test_ozon_parser.py
│   ├── test_services.py
│   ├── test_update_competitor_prices.py
│   ├── test_update_price_timer.py
│   └── test_use_cases.py
│
└── .streamlit/
    └── config.toml                 # Конфигурация Streamlit-сервера
`
