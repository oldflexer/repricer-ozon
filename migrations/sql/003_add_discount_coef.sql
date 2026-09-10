-- Migration 003: Add discount_coef columns to product table
-- This file is the single source of truth for DDL.

-- Добавляем колонки для кэша discount_coef
ALTER TABLE product ADD COLUMN discount_coef REAL DEFAULT NULL;
ALTER TABLE product ADD COLUMN discount_coef_updated_at TIMESTAMP DEFAULT NULL;
ALTER TABLE product ADD COLUMN discount_coef_source TEXT DEFAULT NULL; -- 'parsed' | 'historical' | 'default'

-- Индекс для быстрого поиска товаров с заполненным discount_coef
CREATE INDEX IF NOT EXISTS idx_product_discount_coef ON product(discount_coef) WHERE discount_coef IS NOT NULL;
