# PBS (Product Breakdown Structure) - repricer-ozon

PBS описывает иерархию продукта (подсистемы и модули), без привязки к задачам разработки.

## Иерархия

```
📊 Репрайсер для Ozon (продукт)
│
├── 1. Конфигурация
│   └── 1.1. Параметры окружения (config/settings.py) — API-ключи, SMTP, пути, коэффициенты
│   └── 1.2. API-настройки (config/api.py) — batch size, retries, timeout
│   └── 1.3. UI-настройки (config/ui.py) — web user/pass
│   └── 1.4. Instance-пути (config/instance.py) — data/logs пути
│   └── 1.5. .env-файлы — секреты и переменные окружения
│   └── 1.6. pyproject.toml — конфигурация проекта (ruff, mypy, pytest, deps)
│
├── 2. Доменный слой (core)
│   ├── 2.1. Сущности (entities.py) — ProductInfo, PricingData, StrategyInterval, PriceCalculationResult
│   ├── 2.2. DTO (dto.py) — ProductDTO, PriceUpdateRequestDTO, ProductViewModel
│   ├── 2.3. Мапперы (mappers.py) — преобразование entities <-> DTO
│   ├── 2.4. Контракты (repository.py) — IProductRepository, ILoader
│   ├── 2.5. Бизнес-сервисы
│   │   ├── 2.5.1. PriceCalculationService — алгоритм расчёта цены (индексы, FBS-комиссии, стратегии)
│   │   ├── 2.5.2. MarginCalculator — расчёт маржинальности с учётом всех комиссий
│   │   ├── 2.5.3. ActionService — работа с акциями Ozon (получение/удаление автодобавления)
│   │   ├── 2.5.4. calculate_old_price — расчёт old_price для Ozon
│   │   ├── 2.5.5. HistoryService — сохранение истории цен и дневных агрегатов
│   │   ├── 2.5.6. MigrationService — запуск Alembic миграций
│   │   └── 2.5.7. RealPriceSyncService — синхронизация реальных цен из шаблона Ozon
│   ├── 2.6. Оркестраторы
│   │   ├── 2.6.1. PriceUpdateCoordinator — оркестрация полного цикла репрайсинга
│   │   └── 2.6.2. PricingOrchestrator — устаревший, делегирует в PriceUpdateCoordinator
│   ├── 2.7. DI-контейнер (container.py) — singletons для инфраструктуры
│   ├── 2.8. Enums (enums.py) — StrategyType (IntEnum), parse_strategy_value
│   ├── 2.9. Use Cases
│   │   ├── 2.9.1. RepricingUseCase — вход в цикл репрайсинга
│   │   ├── 2.9.2. DisableAutoAddUseCase — вход в операцию отключения автодобавления
│   │   ├── 2.9.3. ParseCompetitorPricesUseCase — парсинг цен конкурентов
│   │   └── 2.9.4. BaseParserUseCase — базовый класс для парсеров
│
├── 3. Инфраструктура (infrastructure)
│   ├── 3.1. SQLiteRepository (db/) — БД: товары, стратегии, история цен, маржи, агрегаты, очистка
│   │   ├── 3.1.1. connection.py — DBConnectionMixin (PRAGMA, WAL)
│   │   ├── 3.1.2. crud.py — CRUDMixin
│   │   ├── 3.1.3. strategies.py — StrategyMixin
│   │   ├── 3.1.4. history.py — HistoryMixin
│   │   ├── 3.1.5. marginality.py — MarginalityMixin
│   │   ├── 3.1.6. analytics.py — AnalyticsMixin
│   │   └── 3.1.7. maintenance.py — MaintenanceMixin
│   ├── 3.2. ExcelLoader — чтение/запись Excel (товары, стратегии, обновление ячеек)
│   ├── 3.3. OzonApiClient — HTTP-клиент Ozon Seller API (product info, prices, actions)
│   ├── 3.4. OzonSellerClient — Selenium для скачивания шаблона цен
│   ├── 3.5. OzonPriceParser — парсер цен конкурентов через undetected-chromedriver
│   ├── 3.6. MailNotifier — email-отчёты (plain + CSV-вложения)
│   ├── 3.7. Logger — structlog + TimedRotatingFileHandler
│   ├── 3.8. FileUtils — блокировка/безопасное сохранение Excel (pathlib)
│   ├── 3.9. ChromeDriverManager — undetected-chromedriver + fallback
│   ├── 3.10. CircuitBreaker — для API/парсера
│   ├── 3.11. TemplateParser — парсинг шаблона цен (zip XML + openpyxl fallback)
│   ├── 3.12. XDisplay — поиск доступного X-сервера для headless-браузера (Linux, pathlib)
│   └── 3.13. Миграции (run_migrations_once) — запуск Alembic upgrade at startup
│
├── 4. CLI-скрипты (scripts)
│   ├── 4.1. repricer.py — запуск репрайсинга -> Ozon API -> расчёт -> отправка цен -> сохранение
│   ├── 4.2. competitors_parser.py — запуск парсера цен конкурентов -> Chrome -> запись в Excel
│   ├── 4.3. actions_disable_auto_add.py — отключение автодобавления в акции через Ozon API
│   ├── 4.4. health_check.py — проверка здоровья (диск, БД, Excel)
│   ├── 4.5. actions_update_price_timer.py — таймер обновления цен
│   └── 4.6. common.py — общие утилиты (сигналы, логирование)
│
├── 5. Веб-дашборд (ui / app.py)
│   ├── 5.1. app.py — точка входа Streamlit, роутинг по страницам
│   ├── 5.2. Auth — аутентификация пользователя
│   ├── 5.3. Sidebar — управление запусками, загрузка/скачивание Excel
│   ├── 5.4. Cache — кэширование данных в Streamlit (TTL 3600с)
│   ├── 5.5. Страницы
│   │   ├── 5.5.1. Сводка — KPI, динамика за 7 дней, топ-3/худшие-3
│   │   ├── 5.5.2. Статистика — распределение маржи, анализ стратегий, ROI
│   │   ├── 5.5.3. Аналитика — динамика цен, прогнозирование (полиномиальная регрессия), отклонения индексов
│   │   ├── 5.5.4. Анализ — комиссии FBS, индексы Ozon, ABC-анализ, диаграмма Парето
│   │   ├── 5.5.5. Таблицы — просмотр сырых таблиц БД
│   │   ├── 5.5.6. Запросы — управление товарами (история цен, удаление)
│   │   └── 5.5.7. Сервис — heatmap обновлений, очистка БД, диагностика, смена пароля
│   └── 5.6. Статика — styles.css, favicon
│
├── 6. База данных (SQLite + Alembic)
│   ├── 6.1. product — товары (product_id, sku, product_name, costs, strategies)
│   ├── 6.2. strategy — реальные стратегии
│   ├── 6.3. product_strategy — временные интервалы стратегий
│   ├── 6.4. product_price_history — история цен (все метрики каждого цикла)
│   ├── 6.5. product_marginality_history — история маржинальности (текущая/неделя/месяц)
│   ├── 6.6. product_price_daily — дневные агрегаты (avg/min/max)
│   ├── 6.7. price_calculation_logs — детальные JSON-логи расчётов
│   ├── 6.8. maintenance — служебные данные (last_cleanup)
│   ├── 6.9. migration 001 — initial schema
│   └── 6.10. migration 002 — daily aggregates + logs
│
├── 7. Внешние интеграции
│   ├── 7.1. Ozon Seller API — /v3/product/info/list, /v5/product/info/prices, /v1/product/import/prices, /v1/actions/*
│   ├── 7.2. Ozon Web (scraping) — парсинг страниц товаров конкурентов
│   ├── 7.3. SMTP — отправка email (Yandex, Gmail и т.д.)
│   └── 7.4. Excel (.xlsx) — источник данных и приёмник результатов
│
└── 8. Тесты
    ├── 8.1. test_api_client.py — тесты Ozon API
    ├── 8.2. test_database.py — тесты SQLiteRepository
    ├── 8.3. test_entities.py — тесты доменных сущностей
    ├── 8.4. test_integration.py — интеграционные тесты
    ├── 8.5. test_loader.py — тесты ExcelLoader
    ├── 8.6. test_ozon_parser.py — тесты парсера
    ├── 8.7. test_services.py — тесты PriceCalculationService
    ├── 8.8. test_update_competitor_prices.py — тесты обновления цен конкурентов
    └── 8.9. test_use_cases.py — тесты Use Cases
```

## Визуальная схема (Mermaid)

```mermaid
graph TD
    ROOT["📊 Репрайсер для Ozon"]

    subgraph C1["1. Конфигурация"]
        C1a["1.1 settings.py"]
        C1b["1.2 api.py"]
        C1c["1.3 ui.py"]
        C1d["1.4 instance.py"]
        C1e["1.5 .env"]
        C1f["1.6 pyproject.toml"]
    end

    subgraph C2["2. Доменный слой (core)"]
        C2a["2.1 Entities and Enums"]
        C2b["2.2 DTO"]
        C2c["2.3 Mappers"]
        C2d["2.4 Repository Contracts"]
        C2e["2.5 Services (PriceCalc, Action, History, Migration, RealPriceSync)"]
        C2f["2.6 Orchestrators"]
        C2g["2.7 Container"]
        C2h["2.8 Use Cases"]
    end

    subgraph C3["3. Инфраструктура"]
        C3a["3.1 SQLiteRepository (db/)"]
        C3b["3.2 ExcelLoader"]
        C3c["3.3 OzonApiClient"]
        C3d["3.4 OzonSellerClient"]
        C3e["3.5 OzonPriceParser"]
        C3f["3.6 MailNotifier"]
        C3g["3.7 Logger"]
        C3h["3.8 FileUtils"]
        C3i["3.9 ChromeDriverManager"]
        C3j["3.10 CircuitBreaker"]
        C3k["3.11 TemplateParser"]
        C3l["3.12 XDisplay"]
        C3m["3.13 Migrations (Alembic)"]
    end

    subgraph C4["4. CLI-скрипты"]
        C4a["4.1 repricer.py"]
        C4b["4.2 competitors_parser.py"]
        C4c["4.3 actions_disable_auto_add.py"]
        C4d["4.4 health_check.py"]
        C4e["4.5 actions_update_price_timer.py"]
        C4f["4.6 common.py"]
    end

    subgraph C5["5. Веб-дашборд"]
        C5a["5.1 app.py"]
        C5b["5.2 Auth"]
        C5c["5.3 Sidebar"]
        C5d["5.4 Cache"]
        C5e["5.5 Pages (7)"]
        C5f["5.6 Static"]
    end

    subgraph C6["6. База данных"]
        C6a["6.1-6.8 Tables (8)"]
        C6b["6.9-6.10 Migrations (2)"]
    end

    subgraph C7["7. Внешние интеграции"]
        C7a["7.1 Ozon API"]
        C7b["7.2 Ozon Web (scraping)"]
        C7c["7.3 SMTP"]
        C7d["7.4 Excel files"]
    end

    subgraph C8["8. Тесты"]
        C8a["8.1-8.9 Test suites (9)"]
    end

    subgraph C9["9. Документация"]
        C9a["9.1 README.md"]
        C9b["9.2 docs (PBS, WBS, file structure)"]
    end

    ROOT --> C1
    ROOT --> C2
    ROOT --> C3
    ROOT --> C4
    ROOT --> C5
    ROOT --> C6
    ROOT --> C7
    ROOT --> C8
    ROOT --> C9
```