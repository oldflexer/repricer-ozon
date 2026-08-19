# Репрайсер для Ozon (API‑версия)

Автоматическое управление ценами на Ozon через Ozon Seller API, с расчётом на основе индексов цен и заданных временных стратегий, контролем маржинальности по реальным комиссиям FBS.

## 🚀 Возможности

- Работа **только через Ozon Seller API** (v3, v5, v1)
- Автоматическое получение product_id, offer_id, названия товара через `/v3/product/info/list`.
- Получение цен, индексов и комиссий FBS через `/v5/product/info/prices`.
- Расчёт целевой цены с использованием динамического `discount_coef` на основе индексов (external, ozon, self_marketplaces) или коэффициента из `.env`.
- Гибкие временные стратегии: ниже/выше/равна индексу Ozon с настраиваемым процентом.
- Расчёт **маржинальности с учётом всех комиссий Ozon FBS**:
    sales_commission = result_target_price * (sales_percent_fbs/100)
    first_mile_avg = (min + max)/2
    direct_flow_avg = (min + max)/2
    total_cost = sales_commission + first_mile_avg + direct_flow_avg + fbs_deliv_to_customer + net_price
    marginality = (result_target_price - total_cost) / result_target_price
- Отправка цен в Ozon через `/v1/product/import/prices` (с поправкой min_price = РИЦ / discount_coef).
- Автоматическое обновление Excel-файла (реальная цена покупателя, маржа) и запись истории в SQLite.
- Email-уведомления о завершении цикла с детализацией и CSV-вложением.
- **Парсинг цен конкурентов** через undetected-chromedriver (обход блокировок, поддержка профиля Chrome).
- **Отключение автодобавления в акции** Ozon (mass-delete через API).
- **Обновление таймера актуальности минимальной цены** через API.
- **Синхронизация реальных цен из шаблона Ozon** (ДО и ПОСЛЕ репрайсинга).
- Веб-интерфейс на **Streamlit** (7 страниц: Сводка, Статистика, Аналитика, Анализ, Таблицы, Запросы, Сервис).
- Поддержка `--dry-run` (расчёт без отправки) для всех операций.
- **Alembic-миграции** БД (автозапуск `run_migrations_once` при старте).
- **SQLite WAL mode + busy_timeout=30s** для конкурентного доступа.
- Готов к развёртыванию на сервере через systemd и cron.
- **Контейнер зависимостей** (`core/container.py`) на базе `dependency-injector` с lifecycle management.
- **Pipeline Pattern** для репрайсинга (9 изолированных шагов, легко тестируемые и заменяемые).
- **Rich Domain Model** (`core/domain/`): Product, PricingStrategy, Value Objects (Money, SKU, Percentage), PricingRules.
- **Protocol-based DI** (`core/protocols/`): IApiClient, ILoader, INotifier, 5 репозиториев.
- **Линтинг и типизация**: ruff 0.16+, mypy 2.3+, современные type hints (list[dict], float | None).

## 🧱 Архитектура

Проект построен на **Clean Architecture** с разделением на слои:

```
repricer-ozon/
├── config/                         # Слой конфигурации (Pydantic Settings)
│   ├── settings.py                 # Композиция всех настроек, .env, пути
│   ├── api.py                      # API-настройки (batch size, retries, timeout)
│   ├── db.py                       # DB-настройки (путь, WAL mode)
│   ├── email.py                    # SMTP-настройки
│   ├── instance.py                 # Instance-специфичные пути (data, logs)
│   ├── parser.py                   # Парсер-настройки (lock timeout, retries)
│   ├── pricing.py                  # Ценообразование (коэффициенты, стратегии)
│   └── ui.py                       # UI-настройки (web user/pass)
├── core/                           # Доменный слой (бизнес-логика)
│   ├── container.py                # DI-контейнер (dependency-injector, singletons/factories)
│   ├── entities.py                 # Dataclass-модели: ProductInfo, PricingData, StrategyInterval, PriceCalculationResult
│   ├── dto.py                      # Data Transfer Objects (API-контракты)
│   ├── mappers.py                  # Мапперы entities ↔ DTO, build_price_update_request
│   ├── enums.py                    # StrategyType (IntEnum), parse_strategy_value
│   ├── repository.py               # Legacy абстракции: IProductRepository, ILoader
│   ├── price_coordinator.py        # Legacy оркестратор (оставлен для совместимости)
│   ├── orchestrator.py             # Legacy оркестратор (оставлен для совместимости)
│   ├── domain/                     # 🆕 Rich Domain Model
│   │   ├── product.py              # Product, PricingStrategy — инкапсуляция бизнес-логики
│   │   ├── pricing_rules.py        # OzonPricingRules — все правила Ozon в одном месте
│   │   └── value_objects.py        # SKU, Money, Percentage, DiscountCoefficient, TimeInterval
│   ├── pipeline/                   # 🆕 Pipeline Pattern (основной поток репрайсинга)
│   │   ├── orchestrator.py         # PipelineOrchestrator — выполнение последовательности шагов
│   │   └── steps.py                # 9 шагов: LoadProducts → EnrichProductIds → FetchPricingData → CalculatePrices → PersistToExcel → SubmitPricesToOzon → SaveHistory → SendReport → CleanupDatabase
│   ├── protocols/                  # 🆕 Protocol Interfaces (для DI и тестирования)
│   │   ├── api.py                  # IApiClient
│   │   ├── loader.py               # ILoader
│   │   ├── notifier.py             # INotifier
│   │   └── repository.py           # IProductRepository, IPriceHistoryRepository, IAnalyticsRepository, IMarginalityRepository, IMaintenanceRepository
│   ├── services/                   # Бизнес-сервисы
│   │   ├── price_calculation.py    # PriceCalculationService — алгоритм расчёта цены и маржи
│   │   ├── action_service.py       # ActionService — работа с акциями Ozon
│   │   ├── history_service.py      # HistoryService — сохранение истории и агрегатов
│   │   ├── migration_service.py    # MigrationService — запуск Alembic
│   │   └── real_price_sync.py      # RealPriceSyncService — синхронизация реальных цен из шаблона Ozon
│   └── use_cases/                  # Use Cases (точки входа в бизнес-логику)
│       ├── repricing.py            # RepricingUseCase — обёртка над Pipeline
│       ├── disable_auto_add.py     # DisableAutoAddUseCase — отключение автодобавления в акции
│       ├── parse_competitor_prices.py # ParseCompetitorPricesUseCase — парсинг конкурентов
│       ├── base_parser.py          # BaseParserUseCase — базовый класс для парсеров
│       └── update_price_timer.py   # UpdatePriceTimerUseCase — обновление таймера актуальности цены
├── infrastructure/                 # Слой инфраструктуры (реализация протоколов)
│   ├── db/                         # SQLiteRepository (разбит на миксины)
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
├── scripts/                        # CLI-точки входа (исполняемые скрипты)
│   ├── common.py                   # Общие утилиты (сигналы, логирование)
│   ├── repricer.py                 # Запуск репрайсинга → синхронизация → Pipeline → синхронизация
│   ├── competitors_parser.py       # Запуск парсера цен конкурентов
│   ├── actions_disable_auto_add.py # Запуск отключения автодобавления (CLI, --dry-run)
│   ├── actions_update_price_timer.py # Запуск обновления таймера актуальности цены
│   ├── health_check.py             # Проверка здоровья (диск, БД, Excel)
│   └── upgrade_db.py               # Ручной запуск миграций
├── ui/                             # Слой представления (Streamlit UI)
│   ├── app.py                      # Точка входа Streamlit, роутинг по страницам
│   ├── auth.py                     # Аутентификация в дашборде
│   ├── sidebar.py                  # Боковая панель: запуск репрайсинга/парсинга, загрузка/скачивание Excel
│   ├── cache.py                    # Кэширование Streamlit (TTL 3600с) + фабрики объектов
│   └── pages/                      # Страницы дашборда
│       ├── summary.py              # Сводка (KPI, графики за 7 дней, топ-3/худшие-3)
│       ├── statistics.py           # Статистика (распределение маржи, анализ стратегий, ROI)
│       ├── analytics.py            # Аналитика (динамика, прогноз полиномиальной регрессией, отклонения индексов)
│       ├── analysis.py             # Анализ (комиссии FBS, индексы Ozon, ABC-анализ, диаграмма Парето)
│       ├── tables.py               # Просмотр всех таблиц БД в интерактивном dataframe
│       ├── requests.py             # Управление товарами (история цен, удаление)
│       └── service.py              # Сервис (heatmap, работа с БД, диагностика, смена пароля)
├── static/                         # Статические ресурсы
│   ├── favicon.ico
│   └── styles.css                  # CSS-стили для Streamlit
├── migrations/                     # Миграции Alembic
│   ├── env.py                      # Конфигурация окружения Alembic
│   ├── script.py.mako              # Шаблон файла миграции
│   └── versions/
│       ├── 001_initial_schema.py   # Схема БД: product, strategy, product_strategy, *_history, maintenance
│       └── 002_add_daily_aggregates_and_logs.py  # Таблицы product_price_daily, price_calculation_logs
├── data/                           # runtime-данные (создаётся автоматически)
│   ├── products_{{INSTANCE_NAME}}.xlsx               # Входной Excel-файл с товарами
│   └── repricer_{{INSTANCE_NAME}}.db                 # SQLite база данных
├── logs/                           # Лог-файлы (создаётся автоматически)
│   ├── repricer-{INSTANCE}.log     # Логи репрайсера (ротация по дням, 7 бэкапов)
│   └── parser-{INSTANCE}.log       # Логи парсера (ротация по дням, 7 бэкапов)
├── tests/                          # Unit- и интеграционные тесты
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
└── .streamlit/
    └── config.toml                 # Конфигурация Streamlit-сервер
```

### Pipeline репрайсинга (9 шагов)

```
LoadProductsStep       → Загрузка товаров из Excel (ExcelLoader)
EnrichProductIdsStep   → Обогащение product_id, offer_id, name через /v3/product/info/list
FetchPricingDataStep   → Получение цен, индексов, комиссий через /v5/product/info/prices
CalculatePricesStep    → Расчёт целевых цен через PriceCalculationService + Domain Model
PersistToExcelStep     → Запись результатов в Excel (реальная цена, маржа)
SubmitPricesToOzonStep → Отправка цен в Ozon через /v1/product/import/prices
SaveHistoryStep        → Сохранение в БД: история цен, дневные агрегаты, маржинальность, логи расчётов
SendReportStep         → Email-отчёт с детализацией и CSV-вложением
CleanupDatabaseStep    → Автоочистка старых записей (>3 месяцев)
```

Каждый шаг — изолированный класс с интерфейсом `PipelineStep`, легко тестируется и заменяется.

### Domain Model (core/domain/)

- **Product** — агрегат: SKU, product_id, offer_id, cost_price, min_price (RIP), current_price, strategies[], competitor_min_price, real_customer_price
- **PricingStrategy** — Value Object: interval (TimeInterval), strategy_type (StrategyType), percent (Percentage)
- **Value Objects** — Money (копейки, точность), SKU, Percentage, DiscountCoefficient, TimeInterval
- **OzonPricingRules** — все бизнес-правила Ozon: min_price_ratio (0.5), old_price_multiplier (1.5), default_discount_coef, manage_elastic_boosting, etc.

## ⚙️ Переменные окружения (`.env`)

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `INSTANCE_NAME` | Имя экземпляра (в логах, путях) | `Ozon` |
| `OZON_CLIENT_ID` | Client ID Ozon Seller API | — |
| `OZON_API_KEY` | API Key Ozon Seller API | — |
| `OZON_API_URL` | Базовый URL API | `https://api-seller.ozon.ru` |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` | Настройки почты | — |
| `SENDER_EMAIL` / `RECIPIENT_EMAIL` | Email отправителя/получателя | — |
| `COEFFICIENT_OZON` | Коэффициент дисконта (fallback) | `0.5` |
| `OLD_PRICE_MULTIPLIER` | Множитель для old_price | `1.5` |
| `PRICE_ROUND_UP_TO` | Округление old_price | `100` |
| `MANAGE_ELASTIC_BOOSTING` | Управление эластичным бустингом | `false` |
| `DATA_FILE` | Путь к Excel (поддерживает `{{INSTANCE_NAME}}`) | `./data/products_{{INSTANCE_NAME}}.xlsx` |
| `DATABASE_PATH` | Путь к SQLite (поддерживает `{{INSTANCE_NAME}}`) | `./data/repricer_{{INSTANCE_NAME}}.db` |
| `NOTIFICATION_MAX_DETAILS` | Лимит детализации в email | `20` |
| `WEB_USER` / `WEB_PASS` | Логин/пароль дашборда | `admin` / `changeme` |
| `CHROME_PROFILE_PATH` | Путь к профилю Chrome для парсера | автоопределение по ОС |
| `API_BATCH_SIZE` | Размер батча для API запросов | `100` |
| `API_MAX_RETRIES` | Макс. попыток повторных запросов | `3` |
| `API_BATCH_DELAY` | Задержка между батчами (сек) | `0.2` |
| `API_HTTP_TIMEOUT` | HTTP таймаут (сек) | `30.0` |
| `PARSER_RETRIES` | Попытки парсинга цены конкурента | `2` |
| `PARSER_REQUEST_DELAY_MIN` / `MAX` | Задержка между запросами парсера | `2.0` / `4.0` |
| `PARSER_LOCK_TIMEOUT` | Таймаут файловой блокировки парсера | `300` |
| `CLEANUP_MONTHS` | Месяцы для автоочистки БД | `3` |
| `CLEANUP_DAYS_THRESHOLD` | Дни для автоочистки | `30` |

## 📥 Входные данные (Excel)

Файл `products_{{INSTANCE_NAME}}.xlsx` (колонки **обязательны**):

| Колонка | Описание |
|---------|----------|
| `SKU` | Артикул продавца (offer_id) |
| `Себестоимость` | Закупочная цена (net_price) |
| `Цена РИЦ` | Минимальная допустимая цена |
| `Интервал 1`…`4` | Временной интервал `ЧЧ:ММ-ЧЧ:ММ` |
| `Стратегия 1`…`4` | 1 — ниже, 2 — выше, 3 — равна |
| `Процент 1`…`4` | % отклонения (для 1 и 2) |
| `Конкурент 1`…`5` | URL конкурента (для парсера) |
| `Цена 1`…`5` | Текущая цена конкурента (обновляется парсером) |

**Автоматически заполняются после расчёта:** `Ваша цена`, `Название`, `Маржинальность`, `Маржинальность за неделю`, `Маржинальность за месяц`, `Цена до скидки`, `Минимальная цена`.

## 🔄 Алгоритм репрайсинга

1. **Загрузка Excel** — SKU, себестоимость, РИЦ, стратегии, цены конкурентов.
2. **Получение `product_id`, `offer_id`, названия** через `/v3/product/info/list` (батчи по 100).
3. **Получение цен, индексов, комиссий FBS** через `/v5/product/info/prices` (батчи по 100).
4. **Расчёт `discount_coef`**:
   - Берутся индексы: external, ozon, self_marketplaces (где `index ≠ 0`).
   - `approx_real_price = avg(index_price) * avg(index_value)`.
   - `discount_coef = approx_real_price / marketing_seller_price`.
   - Если индексов нет → `discount_coef = COEFFICIENT_OZON` (0.5).
5. **`target_min_price = РИЦ / discount_coef`**.
6. **Выбор активной стратегии** по текущему времени (TIMEZONE Europe/Moscow, поддержка пересечения полночи).
7. **Применение стратегии**:
   - Тип 3 (Равная): `result = target_min_price`.
   - Тип 1 (Ниже): `strategy_price = base * (1 - %/100)`, `result = strategy_price / discount_coef`.
   - Тип 2 (Выше): `strategy_price = base * (1 + %/100)`, `result = strategy_price / discount_coef`.
   - База: `competitor_min_price` → `ozon_index_data_price`. Если нет базы → fallback на `target_min_price`.
8. **`result_target_price = round(max(strategy_result, target_min_price))`**.
9. **Реальная цена покупателя** = `result_target_price * discount_coef` (для Excel/дашборда).
10. **Маржинальность** (усреднение FBS + FBO):
    - `sales_commission = result * sales_percent_fbs / 100`
    - FBS: `first_mile_avg + direct_flow_avg + deliv_to_customer`
    - FBO: `direct_flow_avg + deliv_to_customer`
    - `total_costs = (FBS_total + FBO_total) / 2`
    - `marginality = (result - total_costs) / result`
11. **Отправка в Ozon** (`/v1/product/import/prices`):
    - `price = result_target_price`
    - `min_price = max(РИЦ / discount_coef, price * 0.5)` (правило Ozon 50%)
    - `net_price = себестоимость`
    - `old_price = max(result * OLD_PRICE_MULTIPLIER, округлён до PRICE_ROUND_UP_TO)`
12. **Сохранение**:
    - SQLite: `product_price_history` (все метрики), `product_marginality_history` (текущая/неделя/месяц), `product_price_daily` (агрегаты), `price_calculation_logs` (JSON).
    - Excel: `

12. **Сохранение**:
    - SQLite: product_price_history (все метрики), product_marginality_history (текущая/неделя/месяц), product_price_daily (агрегаты), price_calculation_logs (JSON).
    - Excel: Ваша цена (real_price), Маржинальность (текущая/неделя/месяц), Цена до скидки.
13. **Email-отчёт** (CSV-вложение если товаров > 20).
14. **Автоочистка БД** — удаление записей старше 3 месяцев (раз в день).

## 🕷 Парсер цен конкурентов (scripts/competitors_parser.py)

- Запуск: python scripts/competitors_parser.py [--dry-run]
- Использует undetected-chromedriver с monkey-patch (нет обращений к GitHub за версией драйвера).
- Профиль Chrome: CHROME_PROFILE_PATH (сохраняет куки/авторизацию).
- Парсит до 5 конкурентов на товар (Конкурент N / Цена N).
- Ретраи: 2 попытки с перезапуском драйвера.
- Запись в Excel — точечная (openpyxl), стили сохраняются.
- Блокировка ilelock (один экземпляр парсера).
- Логи: parser-{INSTANCE_NAME}.log (изолированные логгеры selenium/UC/WDM).

## 🛑 Отключение автодобавления в акции (scripts/actions_disable_auto_add.py)

- Запуск: python scripts/actions_disable_auto_add.py [--dry-run]
- Получает все акции (/v1/actions), даты автодобавления, товары (пагинация).
- Массовое удаление (/v1/actions/auto-add/products/delete) батчами по 1000.

## 🌐 Веб-дашборд (Streamlit)

Запуск: streamlit run app.py

**Страницы:**
1. **Сводка** — 5 KPI, графики цены/маржи за 7 дней, топ-3 и худшие-3 по марже.
2. **Статистика** — распределение маржинальности (pie), стратегии (pie), ROI по стратегиям (bar + таблица).
3. **Аналитика** — 3 вкладки:
   - *Динамика*: мультиселект товаров, графики цены и маржи за N дней.
   - *Прогнозирование*: полиномиальная регрессия (numpy.polyfit) средней цены и маржи.
   - *Отклонения индексов*: отношение реальной цены к индексу Ozon.
4. **Анализ** — 2 вкладки:
   - *Комиссии и индексы*: таблица комиссий FBS, scatter-графики (цена vs индекс, маржа vs индекс).
   - *ABC-анализ*: Парето-диаграмма, категории A (80% прибыли), B (15%), C (5%).
5. **Таблицы** — просмотр всех таблиц БД в интерактивном dataframe.
6. **Запросы** — выбор товара, история цен, график динамики, удаление товара (каскадно).
7. **Сервис** — heatmap обновлений (90 дней), последний запуск, очистка БД (>30 дней), скачивание БД, смена пароля, диагностика.

## 🗄️ База данных (SQLite + Alembic)

**Таблицы (миграция 001):**
- product — товары (product_id, sku, product_name, rip, net_price, real_customer_price)
- strategy — справочник стратегий (1: Ниже, 2: Выше, 3: Равная)
- product_strategy — временные интервалы стратегий товара
- product_price_history — полная история каждого цикла репрайсинга
- product_marginality_history — маржинальность (текущая/неделя/месяц)
- maintenance — служебные данные (last_cleanup)

**Таблицы (миграция 002):**
- product_price_daily — дневные агрегаты (avg/min/max цены и маржи)
- price_calculation_logs — JSON-логи расчётов (привязаны к history_id)

**Особенности:**
- WAL mode + busy_timeout=30000 для конкурентного доступа
- Индексы на product_id+timestamp, sku, marginality
- Автоочистка через auto_cleanup_if_needed(months=3)

## 📦 Установка и запуск

`ash
# 1. Клонирование
git clone <repo>
cd repricer-ozon

# 2. Виртуальное окружение
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scriptsctivate

# 3. Зависимости
pip install -r requirements.txt

# 4. Настройка .env (скопируйте .env.example)
cp .env.example .env
# отредактируйте .env — добавьте OZON_CLIENT_ID, OZON_API_KEY, SMTP и т.д.

# 5. Запуск репрайсинга (CLI)
python scripts/repricer.py [--dry-run]

# 6. Запуск парсера конкурентов
python scripts/competitors_parser.py [--dry-run]

# 7. Отключение автодобавления
python scripts/actions_disable_auto_add.py [--dry-run]

# 8. Обновление таймера актуальности цены
python scripts/actions_update_price_timer.py [--dry-run]

# 9. Веб-дашборд
streamlit run app.py
`

## 🧪 Тесты

`ash
pytest -v
# или с покрытием
pytest --cov=core --cov=infrastructure --cov=scripts --cov=config --cov=ui
`

## 📄 Лицензия

Внутренний проект. Использование только командой.
