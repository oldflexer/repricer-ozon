# WBS (Work Breakdown Structure) - repricer-ozon

Актуальная структура работ проекта на 2026-08-19.

## 1.0 Конфигурация
- 1.1 Определить переменные окружения (.env.example)
- 1.2 Реализовать settings.py (загрузка из .env, геттеры)
- 1.3 Реализовать api.py (batch size, retries, timeout)
- 1.4 Реализовать ui.py (web user/pass для Streamlit)
- 1.5 Реализовать instance.py (пути data и logs)
- 1.6 Поддерживать pyproject.toml (зависимости, инструменты)

## 2.0 Доменный слой (core)
- 2.1 Определить сущности (ProductInfo, PricingData, StrategyInterval, PriceCalculationResult)
- 2.2 Определить DTO (ProductDTO, PriceUpdateRequestDTO, ProductViewModel)
- 2.3 Реализовать мапперы (entity <-> DTO)
- 2.4 Определить контракты репозиториев (IProductRepository, ILoader)
- 2.5 Реализовать бизнес-сервисы:
  - 2.5.1 PriceCalculationService (алгоритм цены)
  - 2.5.2 MarginCalculator (маржинальность)
  - 2.5.3 ActionService (акции Ozon)
  - 2.5.4 calculate_old_price
  - 2.5.5 HistoryService
  - 2.5.6 MigrationService
  - 2.5.7 RealPriceSyncService
- 2.6 Реализовать оркестраторы:
  - 2.6.1 PriceUpdateCoordinator
  - 2.6.2 PricingOrchestrator (делегирующий)
- 2.7 DI-контейнер (container.py)
- 2.8 Enums (StrategyType)
- 2.9 Реализовать Use Cases:
  - 2.9.1 RepricingUseCase
  - 2.9.2 DisableAutoAddUseCase
  - 2.9.3 ParseCompetitorPricesUseCase
  - 2.9.4 BaseParserUseCase
- 2.10 Domain Model (domain/):
  - 2.10.1 Product, PricingStrategy
  - 2.10.2 Value Objects (SKU, Money, Percentage, DiscountCoefficient, TimeInterval)
  - 2.10.3 OzonPricingRules
- 2.11 Pipeline Pattern (pipeline/):
  - 2.11.1 PipelineOrchestrator
  - 2.11.2 9 Pipeline Steps
- 2.12 Protocol Interfaces (protocols/):
  - 2.12.1 IApiClient, ILoader, INotifier
  - 2.12.2 5 Repository Protocols

## 3.0 Инфраструктура
- 3.1 SQLiteRepository с миксинами:
  - 3.1.1 DBConnectionMixin
  - 3.1.2 CRUDMixin
  - 3.1.3 StrategyMixin
  - 3.1.4 HistoryMixin
  - 3.1.5 MarginalityMixin
  - 3.1.6 AnalyticsMixin
  - 3.1.7 MaintenanceMixin
- 3.2 ExcelLoader (чтение/запись Excel)
- 3.3 OzonApiClient (HTTP клиент)
- 3.4 OzonSellerClient (Selenium для шаблона)
- 3.5 OzonPriceParser (undetected-chromedriver)
- 3.6 MailNotifier (email + CSV)
- 3.7 Logger (structlog)
- 3.8 FileUtils (pathlib locking)
- 3.9 ChromeDriverManager
- 3.10 CircuitBreaker
- 3.11 TemplateParser (zip XML + openpyxl)
- 3.12 XDisplay (Linux headless)
- 3.13 Migration runner (run_migrations_once)

## 4.0 CLI Scripts
- 4.1 repricer.py (основной workflow)
- 4.2 competitors_parser.py
- 4.3 actions_disable_auto_add.py
- 4.4 actions_update_price_timer.py
- 4.5 health_check.py
- 4.6 upgrade_db.py
- 4.7 common.py (сигналы, логирование)

## 5.0 Web Dashboard (Streamlit)
- 5.1 app.py (entry point, routing)
- 5.2 Auth (login/password)
- 5.3 Sidebar (run triggers, file upload/download)
- 5.4 Cache (TTL caching)
- 5.5 Pages (7):
  - 5.5.1 Summary (KPI, 7-day dynamics, top/bottom 3)
  - 5.5.2 Statistics (margin distribution, strategy analysis, ROI)
  - 5.5.3 Analytics (price dynamics, forecasting, index deviations)
  - 5.5.4 Analysis (FBS fees, Ozon indices, ABC, Pareto)
  - 5.5.5 Tables (raw DB tables)
  - 5.5.6 Requests (product management, price history, deletion)
  - 5.5.7 Service (heatmap, DB cleanup, diagnostics, password change)
- 5.6 Static assets (styles.css, favicon)

## 6.0 Database (SQLite + Alembic)
- 6.1 product table
- 6.2 strategy table
- 6.3 product_strategy table
- 6.4 product_price_history table
- 6.5 product_marginality_history table
- 6.6 product_price_daily table
- 6.7 price_calculation_logs table
- 6.8 maintenance table
- 6.9 migration 001 (initial schema)
- 6.10 migration 002 (daily aggregates and logs)

## 7.0 External Integrations
- 7.1 Ozon Seller API client (product info, prices, import, actions)
- 7.2 Ozon web scraping (competitor pages)
- 7.3 SMTP email sender (Yandex, Gmail)
- 7.4 Excel file handling (read product data, write results)

## 8.0 Testing
- 8.1 Unit tests for OzonApiClient
- 8.2 Unit tests for SQLiteRepository
- 8.3 Unit tests for domain entities
- 8.4 Integration tests (end-to-end)
- 8.5 Unit tests for ExcelLoader
- 8.6 Unit tests for OzonPriceParser
- 8.7 Unit tests for PriceCalculationService
- 8.8 Unit tests for competitor price update use case
- 8.9 Unit tests for use cases (repricing, disable auto-add, etc.)

## 9.0 Documentation
- 9.1 README.md (overview, features, architecture, setup)
- 9.2 PBS.md (Product Breakdown Structure)
- 9.3 WBS.md (this document)
- 9.4 FILE_STRUCTURE.md (project structure overview)
- 9.5 ARCHITECTURE.md (detailed architecture)
- 9.6 DEPLOYMENT.md (deployment guide)
- 9.7 CONTRIBUTING.md (development guide)
- 9.8 API_REFERENCE.md (Ozon API reference)

## 10.0 DevOps and Deployment
- 10.1 systemd service template for repricer
- 10.2 cron job templates for periodic tasks
- 10.3 Dockerfile and docker-compose.yml (optional)
- 10.4 Logging rotation and retention
- 10.5 Backup strategy for SQLite database
- 10.6 Monitoring and health check endpoints
