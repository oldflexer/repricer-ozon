-- Migration 002: Add daily aggregates and logs tables
-- This file is the single source of truth for DDL.
-- Alembic migration 002_add_daily_aggregates_and_logs.py should be kept in sync with this file.

-- Таблица дневных агрегатов
CREATE TABLE IF NOT EXISTS product_price_daily (
    product_id INTEGER NOT NULL,
    date DATE NOT NULL,
    avg_price REAL,
    avg_marginality REAL,
    min_price REAL,
    max_price REAL,
    updates_count INTEGER,
    PRIMARY KEY (product_id, date),
    FOREIGN KEY(product_id) REFERENCES product(product_id)
);

-- Таблица логов расчётов (детализация)
CREATE TABLE IF NOT EXISTS price_calculation_logs (
    history_id INTEGER PRIMARY KEY,
    log_details TEXT,
    FOREIGN KEY(history_id) REFERENCES product_price_history(id)
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_history_timestamp ON product_price_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_history_product_marginality ON product_price_history(product_id, marginality);
CREATE INDEX IF NOT EXISTS idx_daily_product_date ON product_price_daily(product_id, date);
