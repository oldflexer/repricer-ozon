# Репрайсер для Ozon (API‑версия)

Автоматическое управление ценами на Ozon через Ozon Seller API, с расчётом на основе индексов цен и заданных временных стратегий, контролем маржинальности по реальным комиссиям FBS.

## 🚀 Возможности

- Работа **только через Ozon Seller API** (v3, v5, v1)
- Автоматическое получение product_id, offer_id, названия товара через /v3/product/info/list.
- Получение цен, индексов и комиссий FBS через /v5/product/info/prices.
- Расчёт целевой цены с использованием динамического discount_coef на основе индексов (external, ozon, self_marketplaces) или коэффициента из .env.
- Гибкие временные стратегии: ниже/выше/равна индексу Ozon с настраиваемым процентом.
- Расчёт **маржинальности с учётом всех комиссий Ozon FBS**:
    sales_commission = result_target_price * (sales_percent_fbs/100)
    first_mile_avg = (min + max)/2
    direct_flow_avg = (min + max)/2
    total_cost = sales_commission + first_mile_avg + direct_flow_avg + fbs_deliv_to_customer + net_price
    marginality = (result_target_price - total_cost) / result_target_price
- Отправка цен в Ozon через /v1/product/import/prices (с поправкой min_price = РИЦ / discount_coef).
- Автоматическое обновление Excel-файла (реальная цена покупателя, маржа) и запись истории в SQLite.
- Email-уведомления о завершении цикла с детализацией и CSV-вложением.
- **Парсинг цен конкурентов** через undetected-chromedriver (обход блокировок, поддержка профиля Chrome).
- **Отключение автодобавления в акции** Ozon (mass-delete через API).
- Веб-интерфейс на **Streamlit** (7 страниц: Сводка, Статистика, Аналитика, Анализ, Таблицы, Запросы, Сервис).
- Поддержка --dry-run (расчёт без отправки) для всех операций.
- **Alembic-миграции** БД (автозапуск 
un_migrations_once при старте).
- **SQLite WAL mode + busy_timeout=30s** для конкурентного доступа.
- Готов к развёртыванию на сервере через systemd и cron.

## 🧱 Архитектура

Проект чётко разделён на слои (Clean Architecture):

`
repricer-ozon/
├── config/
│   └── settings.py              # Pydantic-настройки, .env, пути, константы
├── core/                        # Доменный слой (бизнес-логика)
│   ├── entities.py              # ProductInfo, PricingData, StrategyInterval, PriceCalculationResult
│   ├── dto.py                   # Data Transfer Objects (API-контракты)
│   ├── mappers.py               # Мапперы entities ↔ DTO, build_price_update_request
│   ├── repository.py            # Абстракции: IProductRepository, ILoader
│   ├── orchestrator.py          # PricingOrchestrator (legacy, делегирует в Coordinator)
│   ├── price_coordinator.py     # PriceUpdateCoordinator — основной оркестратор репрайсинга
│   ├── services/
│   │   ├── price_calculation.py # PriceCalculationService, MarginCalculator, calculate_old_price
│   │   └── action_service.py    # ActionService — работа с акциями Ozon
│   └── use_cases/
│       ├── repricing.py         # RepricingUseCase — вход в цикл репрайсинга
│       └── disable_auto_add.py  # DisableAutoAddUseCase — отключение автодобавления
├── infrastructure/              # Инфраструктура (реализации)
│   ├── db.py                    # SQLiteRepository + run_migrations_once()
│   ├── excel_loader.py          # ExcelLoader (чтение/запись, валидация)
│   ├── ozon_api.py              # OzonApiClient (v3/v5/v1, retry, батчи)
│   ├── ozon_parser.py           # OzonPriceParser (undetected-chromedriver)
│   ├── mail_notifier.py         # MailNotifier (plain + CSV attachment)
│   ├── logger.py                # structlog + TimedRotatingFileHandler
│   ├── file_utils.py            # Блокировка Excel, безопасное сохранение
│   └── x_display.py             # Поиск X-сервера для headless (Linux)
├── scripts/                     # CLI-точки входа
│   ├── repricer.py              # Репрайсинг (--dry-run)
│   ├── parser.py                # Парсинг конкурентов (--dry-run, FileLock)
│   └── disable_auto_add.py      # Отключение автодобавления (--dry-run)
├── ui/                          # Streamlit UI
│   ├── app.py                   # Точка входа, роутинг
│   ├── auth.py                  # Аутентификация
│   ├── sidebar.py               # Управление запусками, Excel
│   ├── cache.py                 # @st.cache_resource / @st.cache_data (TTL 1h)
│   └── pages/
│       ├── summary.py           # KPI, динамика 7 дней, топ-3/худшие-3
│       ├── statistics.py        # Распределение маржи, стратегии, ROI
│       ├── analytics.py         # Динамика, прогноз (numpy.polyfit), отклонения индексов
│       ├── analysis.py          # Комиссии FBS, индексы, ABC-анализ, Парето
│       ├── tables.py            # Просмотр сырых таблиц БД
│       ├── requests.py          # История цен товара, удаление
│       └── service.py           # Heatmap, очистка БД, диагностика, смена пароля
├── static/
│   └── styles.css               # Кастомные стили
├── migrations/                  # Alembic
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 001_initial_schema.py           # 6 таблиц + seed
│       └── 002_add_daily_aggregates_and_logs.py  # daily aggregates + logs
├── data/                        # Runtime (создаётся автоматически)
│   ├── products_{{INSTANCE_NAME}}.xlsx            # Входной Excel
│   └── repricer_{{INSTANCE_NAME}}.db              # SQLite
├── logs/                        # Логи (ротация по дням, 7 бэкапов)
│   ├── repricer-{INSTANCE}.log
│   └── parser-{INSTANCE}.log
├── tests/                       # 9 тест-модулей (pytest + pytest-asyncio)
├── .env                         # Секреты (не в git)
├── .env.example                 # Пример переменных
├── alembic.ini                  # Конфигурация Alembic
├── requirements.txt
└── README.md

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
4. **`target_min_price = РИЦ / discount_coef`**.
5. **Выбор активной стратегии** по текущему времени (TIMEZONE Europe/Moscow, поддержка пересечения полночи).
6. **Применение стратегии**:
   - Тип 3 (Равная): `result = target_min_price`.
   - Тип 1 (Ниже): `strategy_price = base * (1 - %/100)`, `result = strategy_price / discount_coef`.
   - Тип 2 (Выше): `strategy_price = base * (1 + %/100)`, `result = strategy_price / discount_coef`.
   - База: `competitor_min_price` → `ozon_index_data_price`. Если нет базы → fallback на `target_min_price`.
7. **`result_target_price = round(max(strategy_result, target_min_price))`**.
8. **Реальная цена покупателя** = `result_target_price * discount_coef` (для Excel/дашборда).
9. **Маржинальность** (усреднение FBS + FBO):
   - `sales_commission = result * sales_percent_fbs / 100`
   - FBS: `first_mile_avg + direct_flow_avg + deliv_to_customer`
   - FBO: `direct_flow_avg + deliv_to_customer`
   - `total_costs = (FBS_total + FBO_total) / 2`
   - `marginality = (result - total_costs) / result`
10. **Отправка в Ozon** (`/v1/product/import/prices`):
    - `price = result_target_price`
    - `min_price = max(РИЦ / discount_coef, price * 0.5)` (правило Ozon 50%)
    - `net_price = себестоимость`
    - `old_price = max(result * OLD_PRICE_MULTIPLIER, округлён до PRICE_ROUND_UP_TO)`
11. **Сохранение**:
    - SQLite: `product_price_history` (все метрики), `product_marginality_history` (текущая/неделя/месяц), `product_price_daily` (агрегаты), `price_calculation_logs` (JSON).
    - Excel: `Ваша цена` (real_price), `Маржинальность` (текущая/неделя/месяц), `Цена до скидки`.
12. **Email-отчёт** (CSV-вложение если товаров > 20).
13. **Автоочистка БД** — удаление записей старше 3 месяцев (раз в день).

## 🕷 Парсер цен конкурентов

- Запуск: `python scripts/parser.py [--dry-run]`
- Использует `undetected-chromedriver` с monkey-patch (нет обращений к GitHub за версией драйвера).
- Профиль Chrome: `CHROME_PROFILE_PATH` (сохраняет куки/авторизацию).
- Парсит до 5 конкурентов на товар (`Конкурент N` / `Цена N`).
- Ретраи: 2 попытки с перезапуском драйвера.
- Запись в Excel — точечная (`openpyxl`), стили сохраняются.
- Блокировка `filelock` (один экземпляр парсера).
- Логи: `parser-{INSTANCE_NAME}.log` (изолированные логгеры selenium/UC/WDM).

## 🛑 Отключение автодобавления в акции

- Запуск: `python scripts/disable_auto_add.py [--dry-run]`
- Получает все акции (`/v1/actions`), даты автодобавления, товары (пагинация).
- Массовое удаление (`/v1/actions/auto-add/products/delete`) батчами по 1000.

## 🌐 Веб-дашборд (Streamlit)

Запуск: `streamlit run app.py`

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
- `product` — товары (product_id, sku, product_name, rip, net_price, real_customer_price)
- `strategy` — справочник стратегий (1: Ниже, 2: Выше, 3: Равная)
- `product_strategy` — временные интервалы стратегий товара
- `product_price_history` — полная история каждого цикла репрайсинга
- `product_marginality_history` — маржинальность (текущая/неделя/месяц)
- `maintenance` — служебные данные (last_cleanup)

**Таблицы (миграция 002):**
- `product_price_daily` — дневные агрегаты (avg/min/max цены и маржи)
- `price_calculation_logs` — JSON-логи расчётов (привязаны к history_id)

**Особенности:**
- WAL mode + busy_timeout=30000 для конкурентного доступа
- Индексы на product_id+timestamp, sku, marginality
- Автоочистка через `auto_cleanup_if_needed(months=3)`

## 📦 Установка и запуск

```bash
# 1. Клонирование
git clone <repo>
cd repricer-ozon

# 2. Виртуальное окружение
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Зависимости
pip install -r requirements.txt

# 4. Настройка .env (скопируйте .env.example)
cp .env.example .env
# отредактируйте .env — добавьте OZON_CLIENT_ID, OZON_API_KEY, SMTP и т.д.

# 5. Запуск репрайсинга (CLI)
python scripts/repricer.py [--dry-run]

# 6. Запуск парсера конкурентов
python scripts/parser.py [--dry-run]

# 7. Отключение автодобавления
python scripts/disable_auto_add.py [--dry-run]

# 8. Веб-дашборд
streamlit run app.py
```

## 🧪 Тесты

```bash
pytest -v
# или с покрытием
pytest --cov=core --cov=infrastructure --cov=scripts
```

## 📄 Лицензия

Внутренний проект. Использование только командой.