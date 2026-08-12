# WBS (Work Breakdown Structure) - repricer-ozon

## 1.0 Configuration
  1.1 Define environment variables template (.env.example)
  1.2 Implement settings.py (load from .env, provide getters)
  1.3 Implement api.py (Ozon API settings: batch size, retries, timeout)
  1.4 Implement ui.py (web user/pass for Streamlit)
  1.5 Implement instance.py (data and logs paths)
  1.6 Maintain pyproject.toml (dependencies, tool configurations)

## 2.0 Domain Layer (core)
  2.1 Define entities (ProductInfo, PricingData, StrategyInterval, PriceCalculationResult)
  2.2 Define DTOs (ProductDTO, PriceUpdateRequestDTO, ProductViewModel)
  2.3 Implement mappers (entity <-> DTO)
  2.4 Define repository contracts (IProductRepository, ILoader)
  2.5 Implement business services:
      2.5.1 PriceCalculationService (price algorithm)
      2.5.2 MarginCalculator
      2.5.3 ActionService (Ozon actions)
      2.5.4 calculate_old_price function
      2.5.5 HistoryService
      2.5.6 MigrationService
      2.5.7 RealPriceSyncService
  2.6 Implement orchestrators:
      2.6.1 PriceUpdateCoordinator
      2.6.2 PricingOrchestrator (delegating)
  2.7 Implement DI container (container.py)
  2.8 Define enums (StrategyType)
  2.9 Implement use cases:
      2.9.1 RepricingUseCase
      2.9.2 DisableAutoAddUseCase
      2.9.3 ParseCompetitorPricesUseCase
      2.9.4 BaseParserUseCase

## 3.0 Infrastructure
  3.1 Implement SQLiteRepository with mixins:
      3.1.1 DBConnectionMixin (connection.py)
      3.1.2 CRUDMixin (crud.py)
      3.1.3 StrategyMixin (strategies.py)
      3.1.4 HistoryMixin (history.py)
      3.1.5 MarginalityMixin (marginality.py)
      3.1.6 AnalyticsMixin (analytics.py)
      3.1.7 MaintenanceMixin (maintenance.py)
  3.2 Implement ExcelLoader (reading/writing Excel, updating cells)
  3.3 Implement OzonApiClient (HTTP client for Seller API)
  3.4 Implement OzonSellerClient (Selenium for template download)
  3.5 Implement OzonPriceParser (undetected-chromedriver for competitor prices)
  3.6 Implement MailNotifier (email reports with CSV attachments)
  3.7 Implement Logger (structlog with TimedRotatingFileHandler)
  3.8 Implement FileUtils (pathlib-based locking and safe save)
  3.9 Implement ChromeDriverManager (undetected-chromedriver with fallback)
  3.10 Implement CircuitBreaker (for API and parser)
  3.11 Implement TemplateParser (zip XML and openpyxl fallback)
  3.12 Implement XDisplay (find available X server for headless)
  3.13 Implement migration runner (run_migrations_once)

## 4.0 CLI Scripts
  4.1 Implement repricer.py (main repricing workflow)
  4.2 Implement competitors_parser.py (competitor price parsing)
  4.3 Implement actions_disable_auto_add.py (disable auto-add in actions)
  4.4 Implement health_check.py (disk, DB, Excel health checks)
  4.5 Implement actions_update_price_timer.py (price update timer)
  4.6 Implement common.py (signal handling, logging setup)

## 5.0 Web Dashboard (Streamlit)
  5.1 Implement app.py (entry point, routing)
  5.2 Implement Auth (login/password)
  5.3 Implement Sidebar (run triggers, file upload/download)
  5.4 Implement Cache (TTL caching)
  5.5 Implement pages (7 pages):
      5.5.1 Summary page (KPIs, 7-day dynamics, top/bottom 3)
      5.5.2 Statistics page (margin distribution, strategy analysis, ROI)
      5.5.3 Analytics page (price dynamics, forecasting, index deviations)
      5.5.4 Analysis page (FBS fees, Ozon indices, ABC, Pareto)
      5.5.5 Tables page (raw DB tables viewing)
      5.5.6 Requests page (product management, price history, deletion)
      5.5.7 Service page (heatmap, DB cleanup, diagnostics, password change)
  5.6 Implement static assets (styles.css, favicon)

## 6.0 Database (SQLite + Alembic)
  6.1 Design and create product table
  6.2 Design and create strategy table
  6.3 Design and create product_strategy table
  6.4 Design and create product_price_history table
  6.5 Design and create product_marginality_history table
  6.6 Design and create product_price_daily table
  6.7 Design and create price_calculation_logs table
  6.8 Design and create maintenance table
  6.9 Create migration 001 (initial schema)
  6.10 Create migration 002 (daily aggregates and logs)

## 7.0 External Integrations
  7.1 Implement Ozon Seller API client (endpoints: product info, prices, import, actions)
  7.2 Implement Ozon web scraping (competitor product pages)
  7.3 Implement SMTP email sender (Yandex, Gmail, etc.)
  7.4 Implement Excel file handling (read product data, write results)

## 8.0 Testing
  8.1 Write unit tests for OzonApiClient
  8.2 Write unit tests for SQLiteRepository
  8.3 Write unit tests for domain entities
  8.4 Write integration tests (end-to-end scenarios)
  8.5 Write unit tests for ExcelLoader
  8.6 Write unit tests for OzonPriceParser
  8.7 Write unit tests for PriceCalculationService
  8.8 Write unit tests for competitor price update use case
  8.9 Write unit tests for use cases (repricing, disable auto-add, etc.)

## 9.0 Documentation
  9.1 Write README.md (project overview, features, architecture, setup)
  9.2 Write PBS.md (Product Breakdown Structure)
  9.3 Write WBS.md (this document)
  9.4 Write FILE_STRUCTURE.md (project structure overview)

## 10.0 DevOps and Deployment
  10.1 Create systemd service template for repricer
  10.2 Create cron job template for periodic tasks
  10.3 Create Dockerfile and docker-compose.yml (optional)
  10.4 Configure logging rotation and retention
  10.5 Implement backup strategy for SQLite database
  10.6 Set up monitoring and health check endpoints