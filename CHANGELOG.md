# Changelog

Все заметные изменения в этом проекте.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/),
проект следует [Semantic Versioning](https://semver.org/lang/ru/).

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
