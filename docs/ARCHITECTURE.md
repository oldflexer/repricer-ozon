# ARCHITECTURE.md - Детальная архитектура repricer-ozon

> Автоматически сгенерированная документация архитектуры проекта.
> Версия: 1.0.0
> Дата: 2026-08-19

---

## 1. Обзор архитектуры

Проект построен на **Clean Architecture** с четким разделением на слои:

```
+-------------------------------------------------------------+
|                    Presentation Layer (ui/)                   |
|  Streamlit Dashboard (7 страниц) + Sidebar + Auth + Cache   |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                      Application Layer (core/)                |
|  Use Cases + Pipeline + Domain Model + Protocols + Services |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                   Infrastructure Layer (infrastructure/)      |
|  SQLiteRepository + ExcelLoader + OzonApiClient + Parsers   |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                    Configuration Layer (config/)              |
|  Pydantic Settings (7 модулей) + .env + pyproject.toml      |
+-------------------------------------------------------------+
```

### Ключевые принципы

1. **Dependency Inversion** — доменный слой не зависит от инфраструктуры
2. **Protocol-based DI** — интерфейсы в core/protocols/, реализации в infrastructure/
3. **Pipeline Pattern** — репрайсинг как последовательность изолированных шагов
4. **Rich Domain Model** — бизнес-логика инкапсулирована в core/domain/
5. **Single Responsibility** — каждый класс/модуль имеет одну причину для изменения

---

## 2. Pipeline Pattern (core/pipeline/)

Основной поток репрайсинга реализован как pipeline из 9 шагов.

### 9 шагов Pipeline

| Шаг | Класс | Ответственность | Входные данные | Выходные данные |
|-----|-------|-----------------|----------------|-----------------|
| 1 | LoadProductsStep | Загрузка товаров из Excel | ILoader | context.products (List[Product]) |
| 2 | EnrichProductIdsStep | Обогащение product_id, offer_id, name | IApiClient | product.product_id, product.offer_id |
| 3 | FetchPricingDataStep | Получение цен, индексов, комиссий | IApiClient | context.pricing_data (Dict[product_id, PricingData]) |
| 4 | CalculatePricesStep | Расчёт целевых цен | PriceCalculationService + Domain | context.calculation_results (Dict[SKU, PriceCalculationResult]) |
| 5 | PersistToExcelStep | Запись результатов в Excel | ILoader | Excel обновлён |
| 6 | SubmitPricesToOzonStep | Отправка цен в Ozon API | IApiClient | context.api_results (Dict[product_id, result]) |
| 7 | SaveHistoryStep | Сохранение в БД | Repository protocols | БД обновлена |
| 8 | SendReportStep | Email-отчёт | INotifier | Email отправлен |
| 9 | CleanupDatabaseStep | Автоочистка старых записей | IMaintenanceRepository | Старые записи удалены |

### PipelineContext

Неизменяемый контекст, передаваемый между шагами:

- products: List[Product]
- pricing_data: Dict[int, PricingData]
- calculation_results: Dict[SKU, PriceCalculationResult]
- price_updates: List[dict]
- api_results: Dict[int, dict]
- updates_for_excel: List[dict]
- errors: List[str]
- warnings: List[str]
- dry_run: bool
- current_time: time | None
- should_stop: bool

### Обработка ошибок

- Каждый шаг обёрнут в try/except
- При ошибке: context.add_error(), context.should_stop = True
- Pipeline останавливается перед следующим шагом
- Результат содержит список ошибок и предупреждений

---

## 3. Domain Model (core/domain/)

### Product (Aggregate Root)

Поля: sku, product_id, offer_id, product_name, cost_price, min_price (RIP), current_price, old_price, competitor_min_price, real_customer_price, strategies[], _discount_coef

Методы: calculate_target_price(), discount_coefficient (property)

### PricingStrategy (Value Object)

Поля: interval (TimeInterval), strategy_type (StrategyType), percent (Percentage)

Методы: is_active_at(), calculate_price()

### Value Objects

| Value Object | Описание | Ключевые операции |
|--------------|----------|-------------------|
| SKU | Артикул продавца | валидация, str() |
| Money | Денежная сумма в копейках | +, -, *, /, rubles_float |
| Percentage | Процент (0-100) | ratio (0.0-1.0), percent_float |
| DiscountCoefficient | Коэффициент дисконта | value (float) |
| TimeInterval | Временной интервал | contains(hour, minute), поддержка полуночи |

### OzonPricingRules (Domain Rules)

Все бизнес-правила Ozon в одном месте:

- min_price_ratio: 0.5 (min_price >= price * 0.5)
- old_price_multiplier: 1.5 (old_price = price * 1.5)
- old_price_round_step: 100 (округление old_price)
- default_discount_coef: 0.5
- manage_elastic_boosting: false
- wait_after_update_seconds: 10
- schedule_intervals_count: 4
- max_competitors: 5

Методы: validate_min_price(), calculate_old_price(), apply_strategy_below/above/equal(), calculate_target_min_price()

---

## 4. Protocol-based DI (core/protocols/)

Интерфейсы для инверсии зависимостей:

**IApiClient** — get_product_info_list, get_product_prices, import_prices, get_actions, delete_auto_add_products, update_price_timer, close

**ILoader** — load(), save_price(), save_competitor_price()

**INotifier** — send_detailed_report(), notify_cycle_complete()

**Repository Protocols (5 шт.)**:
- IProductRepository — get_all_products, upsert_product, delete_product
- IPriceHistoryRepository — save_price_history, get_price_history
- IAnalyticsRepository — get_daily_aggregates, get_strategy_roi
- IMarginalityRepository — save_marginality, get_marginality_history
- IMaintenanceRepository — auto_cleanup_if_needed, get_last_cleanup, set_last_cleanup

---

## 5. DI Container (core/container.py)

Использует dependency-injector для декларативного DI.

### Scoping

| Тип | Scope | Примеры |
|-----|-------|---------|
| Singleton | Application lifetime | Repository, ApiClient, Loader, Notifier, PriceCalculationService |
| Factory | New instance per call | Parser, Use Cases, Pipeline |
| Resource | Async lifecycle | ApiClient (auto-close) |

Repository протоколы извлекаются из основного repository через cast().

Lifecycle management для ApiClient через @providers.Resource.

---

## 6. Data Flow (последовательность)

User -> Script -> Sync(ДО) -> UC -> Pipeline -> 9 Steps -> Excel/API/DB/Email -> Sync(ПОСЛЕ) -> Close

1. Синхронизация реальных цен ДО (RealPriceSyncService)
2. RepricingUseCase.execute() -> создаёт Pipeline
3. PipelineOrchestrator выполняет 9 шагов последовательно
4. Синхронизация реальных цен ПОСЛЕ (если не dry-run)
5. Закрытие HTTP-клиента

---

## 7. Extensibility Guide

### Добавление шага в Pipeline

1. Создать класс MyCustomStep(PipelineStep) в core/pipeline/steps.py
2. Добавить в create_repricing_pipeline() в core/pipeline/orchestrator.py
3. Зарегистрировать зависимость в PipelineDependencies и Container

### Расширение Domain Model

1. Новый Value Object в core/domain/value_objects.py
2. Расширить Product в core/domain/product.py
3. Обновить OzonPricingRules при необходимости
4. Обновить PriceCalculationService

### Новый Use Case

1. Класс в core/use_cases/
2. Зависимости в Container
3. CLI скрипт в scripts/ (при необходимости)
4. Кнопка в Sidebar UI (при необходимости)

---

## 8. Testing Strategy

### Unit Tests

- Domain Model (test_entities.py, test_services.py): Product, PricingStrategy, Money, Percentage, PriceCalculationService, OzonPricingRules
- Pipeline Steps (test_use_cases.py): каждый шаг изолированно с моками
- Use Cases (test_use_cases.py): RepricingUseCase (мок pipeline), ParseCompetitorPricesUseCase (мок парсер)

### Integration Tests

- Database (test_database.py): SQLite in-memory, CRUD, миграции, агрегаты
- API Client (test_api_client.py): pytest-httpx, retry logic, batching, error handling
- Excel Loader (test_excel_loader.py, test_loader.py): временные файлы, чтение/запись, стили

### E2E Tests

- Full Pipeline (test_integration.py): полный pipeline с моками внешних систем

### Coverage Targets

source = ["core", "infrastructure", "scripts", "config", "ui"]
omit = ["tests/*", "migrations/*", "scripts/health_check.py"]

---

## 9. Deployment Architecture

### Systemd Service

Type=oneshot, User=repricer, WorkingDirectory=/opt/repricer-ozon, EnvironmentFile=.env, ExecStart=python scripts/repricer.py

### Cron Jobs

- Репрайсинг: */30 * * * *
- Парсер конкурентов: 0 3 * * *
- Отключение автодобавления: 0 4 * * *
- Обновление таймера: 0 5 * * *
- Health check: 0 * * * *

### Docker (опционально)

FROM python:3.12-slim, WORKDIR /app, COPY pyproject.toml requirements.txt, RUN pip install, COPY ., CMD ["python", "scripts/repricer.py"]

---

## 10. Monitoring & Observability

### Logging

- Structlog с JSON output для production
- TimedRotatingFileHandler — ротация по дням, 7 бэкапов
- Изолированные логгеры: repricer, parser, selenium, uc, wdm
- Файлы: logs/repricer-{INSTANCE}.log, logs/parser-{INSTANCE}.log

### Health Checks

scripts/health_check.py проверяет: дисковое пространство, доступность БД (SQLite), доступность Excel файла, подключение к Ozon API

### Metrics (Dashboard)

Streamlit дашборд: KPI (товары, обновления, ошибки, маржинальность), Heatmap обновлений за 90 дней, последний запуск и статистика, диагностика БД

---

## 11. Security Considerations

- Secrets — только в .env (не в git)
- API Keys — передаются через headers, не логируются
- SMTP Password — в .env
- Web UI — Basic Auth (WEB_USER/WEB_PASSWORD)
- Chrome Profile — изолированный профиль для парсера
- File Locks — предотвращение параллельного запуска парсера

---

## 12. Performance Considerations

- Batching — API запросы батчами по 100 (настраиваемо)
- Connection Pooling — httpx client с keep-alive
- SQLite WAL Mode — конкурентное чтение/запись
- Streamlit Caching — TTL 3600с для тяжелых запросов
- Circuit Breaker — защита от каскадных сбоев API/парсера
- Async/Await — неблокирующие HTTP запросы

---

*Документ обновляется при изменении архитектуры. Последнее обновление: 2026-08-19*