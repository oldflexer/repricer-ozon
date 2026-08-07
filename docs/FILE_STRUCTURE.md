# Структура файлов и папок проекта `repricer-ozon`

```
repricer-ozon/
│
├── app.py                          # Точка входа Streamlit-дашборда
├── requirements.txt                # Python-зависимости
├── alembic.ini                     # Конфигурация Alembic (миграции БД)
├── .env                            # Переменные окружения (секреты, настройки)
├── .env.example                    # Пример .env
├── README.md                        # Документация проекта
│
├── config/                         # Слой конфигурации
│   └── settings.py                 # Pydantic-настройки (env, пути, константы)
│
├── core/                           # Доменный слой (бизнес-логика)
│   ├── __init__.py
│   ├── entities.py                 # Dataclass-модели: ProductInfo, PricingData, StrategyInterval, PriceCalculationResult
│   ├── dto.py                      # Data Transfer Objects (внешний контракт)
│   ├── mappers.py                  # Мапперы entities ↔ DTO, DTO → API-request
│   ├── repository.py               # Абстрактные интерфейсы: IProductRepository, ILoader
│   ├── orchestrator.py             # PricingOrchestrator — делегирует в PriceUpdateCoordinator
│   ├── price_coordinator.py        # PriceUpdateCoordinator — оркестратор репрайсинга (основной поток)
│   ├── services/                   # Бизнес-сервисы
│   │   ├── __init__.py
│   │   ├── price_calculation.py    # PriceCalculationService — алгоритм расчёта цены и маржи
│   │   └── action_service.py       # ActionService — работа с акциями Ozon (auto-add)
│   └── use_cases/                  # Use Case-ы (точки входа в бизнес-логику)
│       ├── __init__.py
│       ├── repricing.py            # RepricingUseCase — обёртка над Orchestrator
│       └── disable_auto_add.py     # DisableAutoAddUseCase — отключение автодобавления в акции
│
├── infrastructure/                 # Слой инфраструктуры (реализация)
│   ├── db.py                       # SQLiteRepository — реализация IProductRepository + run_migrations_once()
│   ├── excel_loader.py             # ExcelLoader — реализация ILoader (чтение/запись Excel)
│   ├── ozon_api.py                 # OzonApiClient — клиент Ozon Seller API (v3, v5, v1)
│   ├── ozon_parser.py              # OzonPriceParser — парсер цен конкурентов через undetected-chromedriver
│   ├── mail_notifier.py            # MailNotifier — отправка email-отчётов
│   ├── logger.py                   # Настройка логирования (structlog + TimedRotatingFileHandler)
│   ├── file_utils.py               # Утилиты: блокировка Excel, безопасное сохранение
│   └── x_display.py                # Поиск доступного X-сервера для headless-браузера (Linux)
│
├── scripts/                        # CLI-точки входа (исполняемые скрипты)
│   ├── repricer.py                 # Запуск репрайсинга (CLI, --dry-run)
│   ├── parser.py                   # Запуск парсера цен конкурентов (CLI, --dry-run)
│   └── disable_auto_add.py         # Запуск отключения автодобавления (CLI, --dry-run)
│
├── ui/                             # Слой представления (Streamlit UI)
│   ├── __init__.py
│   ├── auth.py                     # Аутентификация в дашборде
│   ├── sidebar.py                  # Боковая панель: запуск репрайсинга/парсинга, загрузка Excel
│   ├── cache.py                    # Кэширование Streamlit (TTL 3600с) + фабрики объектов
│   └── pages/                      # Страницы дашборда
│       ├── summary.py              # Сводка (KPI, графики за 7 дней, топ-3/худшие-3)
│       ├── statistics.py           # Статистика (распределение маржи, стратегии, ROI)
│       ├── analytics.py            # Аналитика (динамика, прогноз, отклонения индексов)
│       ├── analysis.py             # Анализ (комиссии FBS, индексы, ABC-анализ)
│       ├── tables.py               # Просмотр сырых таблиц БД
│       ├── requests.py             # Управление товарами (история, удаление)
│       └── service.py              # Сервис (heatmap, работа с БД, диагностика, смена пароля)
│
├── static/                         # Статические ресурсы
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
│   ├── test_api_client.py
│   ├── test_database.py
│   ├── test_entities.py
│   ├── test_integration.py
│   ├── test_loader.py
│   ├── test_ozon_parser.py
│   ├── test_services.py
│   ├── test_update_competitor_prices.py
│   └── test_use_cases.py
│
└── .streamlit/
    └── config.toml                 # Конфигурация Streamlit-сервера
```
