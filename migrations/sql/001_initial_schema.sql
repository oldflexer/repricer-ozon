-- Initial schema for Repricer-Ozon
-- This file is the single source of truth for DDL.
-- Alembic migration 001_initial_schema.py should be kept in sync with this file.

-- Таблица товаров
CREATE TABLE IF NOT EXISTS product (
    product_id INTEGER PRIMARY KEY,
    offer_id TEXT,
    sku TEXT UNIQUE,
    product_name TEXT,
    rip REAL,
    net_price REAL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    real_customer_price REAL
);

-- Таблица стратегий (справочник)
CREATE TABLE IF NOT EXISTS strategy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_name TEXT UNIQUE
);

-- Начальные данные стратегий
INSERT OR IGNORE INTO strategy(id, strategy_name) VALUES (1, 'Ниже');
INSERT OR IGNORE INTO strategy(id, strategy_name) VALUES (2, 'Выше');
INSERT OR IGNORE INTO strategy(id, strategy_name) VALUES (3, 'Равная');

-- Связь товаров со стратегиями (интервалы)
CREATE TABLE IF NOT EXISTS product_strategy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    interval_start TEXT,
    interval_stop TEXT,
    strategy_id INTEGER,
    strategy_percent REAL,
    FOREIGN KEY(product_id) REFERENCES product(product_id),
    FOREIGN KEY(strategy_id) REFERENCES strategy(id)
);

-- История цен
CREATE TABLE IF NOT EXISTS product_price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    min_price REAL,
    price REAL,
    old_price REAL,
    marketing_seller_price REAL,
    external_index_data_price REAL,
    external_index_data_index REAL,
    ozon_index_data_price REAL,
    ozon_index_data_index REAL,
    self_marketplaces_index_data_price REAL,
    self_marketplaces_index_data_index REAL,
    result_target_price REAL,
    discount_coef REAL,
    marginality REAL,
    sales_percent_fbs REAL,
    acquiring REAL,
    fbs_first_mile_min_amount REAL,
    fbs_first_mile_max_amount REAL,
    fbs_direct_flow_trans_min_amount REAL,
    fbs_direct_flow_trans_max_amount REAL,
    fbs_deliv_to_customer_amount REAL,
    log_details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    real_price REAL,
    fbo_deliv_to_customer_amount REAL,
    fbo_direct_flow_trans_min_amount REAL,
    fbo_direct_flow_trans_max_amount REAL,
    fbo_return_flow_amount REAL,
    fbs_return_flow_amount REAL,
    FOREIGN KEY(product_id) REFERENCES product(product_id)
);

-- История маржинальности
CREATE TABLE IF NOT EXISTS product_marginality_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    marginality REAL,
    marginality_week REAL,
    marginality_month REAL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(product_id) REFERENCES product(product_id)
);

-- Служебная таблица
CREATE TABLE IF NOT EXISTS maintenance (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
INSERT OR IGNORE INTO maintenance (key, value) VALUES ('last_cleanup', '1970-01-01 00:00:00');

-- Индексы
CREATE INDEX IF NOT EXISTS idx_product_sku ON product(sku);
CREATE INDEX IF NOT EXISTS idx_history_product_timestamp ON product_price_history(product_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_marginality_product_timestamp ON product_marginality_history(product_id, timestamp);
