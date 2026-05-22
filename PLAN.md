# PLAN.md — План рефакторинга и улучшения архитектуры репрайсера Ozon

## 🔥 Этап 1. Быстрые победы

### 1.1 Хелпер для обновления Excel

- В `infrastructure/loader.py` добавить метод:

      def _build_excel_updates(product, result, marginality_week, marginality_month, old_price_update) -> Dict

  чтобы централизовать формирование словаря обновлений.

### 1.2 Добавление индексов в БД (миграция)

- Написать миграцию (ручную или через Alembic) для создания индексов:

      CREATE INDEX IF NOT EXISTS idx_product_sku ON product(sku);
      CREATE INDEX IF NOT EXISTS idx_history_product_timestamp ON product_price_history(product_id, timestamp);
      CREATE INDEX IF NOT EXISTS idx_marginality_product_timestamp ON product_marginality_history(product_id, timestamp);

### 1.3 Docstring для публичных методов

- Добавить описания для:
  - `RepricingUseCase.execute`
  - `PriceCalculationService.calculate`
  - `OzonApiClient.get_product_prices`, `update_prices`
  - `SQLiteRepository.*` (ключевые методы)

---

## 🚀 Этап 2. Долгосрочные и опциональные улучшения

### 2.1 Компонентизация Streamlit UI

- Вынести CSS в отдельный файл `styles.css`.
- Создать функции:
  - `render_sidebar()` – боковая панель
  - `render_product_table(products)`
  - `render_history_table()`
  - `render_price_chart(selected)`
  - `render_statistics()`
- Добавить UI-тесты с `pytest-streamlit` или Playwright.

### 2.2 Структурированное логирование

- Установить `structlog`.
- Настроить вывод в JSON для логов (консоль + файл).
- Добавить поля `request_id`, `sku`, `product_id` в ключевые точки.

### 2.3 Абстракция для работы с Excel (ILoader)

- Создать интерфейс `ILoader` в `core/repository.py`.
- Реализовать `ExcelLoader` (текущий `DataLoader`).
- В будущем можно будет легко добавить загрузку из CSV, Google Sheets.

---

*Последнее обновление: 2026-05-22*