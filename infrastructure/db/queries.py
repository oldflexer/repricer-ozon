"""
SQL query constants for database operations.

Centralizing SQL queries here improves maintainability, enables type checking,
and makes it easier to audit/modify queries.
"""

# =========================================================================
# Product table queries
# =========================================================================

SQL_SELECT_PRODUCT_ID_BY_SKU = """
    SELECT product_id FROM product WHERE sku = ?
"""

SQL_SELECT_PRODUCT_BY_SKU = """
    SELECT product_id, offer_id, sku, product_name, rip, net_price,
           real_customer_price
    FROM product
    WHERE sku = ?
"""

SQL_INSERT_PRODUCT = """
    INSERT INTO product (product_id, sku, product_name, rip, net_price, real_customer_price)
    VALUES (?, ?, ?, ?, ?, ?)
"""

SQL_UPDATE_PRODUCT = """
    UPDATE product SET product_name = ?, rip = ?, net_price = ?, real_customer_price = ?
    WHERE product_id = ?
"""

SQL_UPDATE_PRODUCT_REAL_PRICE = """
    UPDATE product
    SET real_customer_price = ?, last_updated = CURRENT_TIMESTAMP
    WHERE sku = ?
"""

SQL_SELECT_ALL_PRODUCTS = """
    SELECT product_id, sku, product_name, rip, net_price, real_customer_price
    FROM product
"""

SQL_DELETE_PRODUCT = """
    DELETE FROM product WHERE product_id = ?
"""

# =========================================================================
# Strategy table queries
# =========================================================================

SQL_SELECT_STRATEGY_BY_ID = """
    SELECT id, name FROM strategy WHERE id = ?
"""

SQL_SELECT_ALL_STRATEGIES = """
    SELECT id, name FROM strategy
"""

SQL_INSERT_PRODUCT_STRATEGY = """
    INSERT INTO product_strategy (product_id, strategy_id, time_start, time_end, percent)
    VALUES (?, ?, ?, ?, ?)
"""

SQL_SELECT_PRODUCT_STRATEGIES = """
    SELECT ps.strategy_id, ps.time_start, ps.time_end, ps.percent, s.name as strategy_name
    FROM product_strategy ps
    JOIN strategy s ON s.id = ps.strategy_id
    WHERE ps.product_id = ?
"""

SQL_SELECT_STRATEGY_COUNTS = """
    SELECT s.name as strategy_name, COUNT(*) as count
    FROM product_strategy ps
    JOIN strategy s ON ps.strategy_id = s.id
    GROUP BY s.name
"""

SQL_DELETE_PRODUCT_STRATEGIES = """
    DELETE FROM product_strategy WHERE product_id = ?
"""

SQL_UPDATE_PRODUCT_STRATEGIES = """
    UPDATE product_strategy SET strategy_id = ?, time_start = ?, time_end = ?, percent = ?
    WHERE product_id = ? AND strategy_id = ?
"""

# =========================================================================
# Price History table queries
# =========================================================================

SQL_INSERT_PRICE_HISTORY = """
    INSERT INTO product_price_history (
        product_id, min_price, price, old_price,
        marketing_seller_price,
        external_index_data_price, external_index_data_index,
        ozon_index_data_price, ozon_index_data_index,
        self_marketplaces_index_data_price, self_marketplaces_index_data_index,
        result_target_price, discount_coef, marginality,
        sales_percent_fbs, acquiring,
        fbs_first_mile_min_amount, fbs_first_mile_max_amount,
        fbs_direct_flow_trans_min_amount, fbs_direct_flow_trans_max_amount,
        fbs_deliv_to_customer_amount,
        fbo_deliv_to_customer_amount, fbo_direct_flow_trans_min_amount,
        fbo_direct_flow_trans_max_amount, real_price, log_details
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

SQL_INSERT_PRICE_CALCULATION_LOG = """
    INSERT INTO price_calculation_logs (history_id, log_details) VALUES (?, ?)
"""

SQL_SELECT_PRICE_HISTORY_BY_SKU = """
    SELECT
        ph.timestamp,
        ph.result_target_price,
        ph.discount_coef,
        ph.real_price,
        ph.marginality
    FROM product_price_history ph
    JOIN product p ON p.product_id = ph.product_id
    WHERE p.sku = ?
    ORDER BY ph.timestamp
"""

SQL_SELECT_MAX_PRICE_HISTORY_TIMESTAMP = """
    SELECT MAX(timestamp) FROM product_price_history
"""

# =========================================================================
# Marginality History table queries
# =========================================================================

SQL_INSERT_MARGINALITY_HISTORY = """
    INSERT INTO product_marginality_history
    (product_id, marginality, marginality_week, marginality_month)
    VALUES (?, ?, ?, ?)
"""

SQL_SELECT_AVG_MARGINALITY = """
    SELECT AVG(marginality) FROM product_marginality_history
    WHERE product_id = ? AND timestamp >= ?
"""

# =========================================================================
# Daily Aggregates table queries
# =========================================================================

SQL_SELECT_DAILY_AGGREGATE = """
    SELECT avg_price, avg_marginality, min_price, max_price, updates_count
    FROM product_price_daily
    WHERE product_id = (SELECT product_id FROM product WHERE sku = ?) AND date = ?
"""

SQL_UPDATE_DAILY_AGGREGATE = """
    UPDATE product_price_daily
    SET avg_price = ?, avg_marginality = ?, min_price = ?, max_price = ?, updates_count = ?
    WHERE product_id = (SELECT product_id FROM product WHERE sku = ?) AND date = ?
"""

SQL_INSERT_DAILY_AGGREGATE = """
    INSERT INTO product_price_daily
    (product_id, date, avg_price, avg_marginality, min_price, max_price, updates_count)
    VALUES ((SELECT product_id FROM product WHERE sku = ?), ?, ?, ?, ?, ?, ?)
"""

SQL_SELECT_DAILY_TRENDS_AGGREGATED = """
    SELECT
        date as day,
        AVG(avg_price) as avg_price,
        AVG(avg_marginality) as avg_margin
    FROM product_price_daily
    WHERE date >= date('now', ? || ' days')
    GROUP BY date
    ORDER BY date
"""

SQL_SELECT_DAILY_TRENDS_FALLBACK = """
    SELECT
        DATE(ph.timestamp) as day,
        AVG(ph.result_target_price * ph.discount_coef) as avg_price,
        AVG(ph.marginality) as avg_margin
    FROM product_price_history ph
    WHERE ph.timestamp >= datetime('now', ? || ' days')
    GROUP BY day
    ORDER BY day
"""

SQL_SELECT_DAILY_DEVIATION = """
    SELECT
        DATE(ph.timestamp) as day,
        AVG( (ph.result_target_price * ph.discount_coef) / NULLIF(ph.ozon_index_data_price, 0) ) as avg_ratio
    FROM product_price_history ph
    WHERE ph.ozon_index_data_price > 0
    AND ph.timestamp >= datetime('now', ? || ' days')
    GROUP BY day
    ORDER BY day
"""

# =========================================================================
# Maintenance/Cleanup queries
# =========================================================================

SQL_DELETE_PRICE_HISTORY_BEFORE = """
    DELETE FROM product_price_history WHERE timestamp < ?
"""

SQL_DELETE_MARGINALITY_HISTORY_BEFORE = """
    DELETE FROM product_marginality_history WHERE timestamp < ?
"""

SQL_DELETE_PRICE_CALC_LOGS_BY_HISTORY = """
    DELETE FROM price_calculation_logs
    WHERE history_id IN (SELECT id FROM product_price_history WHERE timestamp < ?)
"""

SQL_SELECT_LAST_CLEANUP = """
    SELECT value FROM maintenance WHERE key = 'last_cleanup'
"""

SQL_UPDATE_LAST_CLEANUP = """
    UPDATE maintenance SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE key = 'last_cleanup'
"""

# Repricing run tracking
SQL_SELECT_LAST_RUN = """
    SELECT value FROM maintenance WHERE key = 'last_repricing_run'
"""

SQL_UPDATE_LAST_RUN = """
    INSERT OR REPLACE INTO maintenance (key, value, updated_at)
    VALUES ('last_repricing_run', ?, CURRENT_TIMESTAMP)
"""

# =========================================================================
# Product deletion cascade queries
# =========================================================================

SQL_DELETE_PRODUCT_STRATEGIES_BY_PID = """
    DELETE FROM product_strategy WHERE product_id = ?
"""

SQL_DELETE_PRICE_HISTORY_BY_PID = """
    DELETE FROM product_price_history WHERE product_id = ?
"""

SQL_DELETE_MARGINALITY_HISTORY_BY_PID = """
    DELETE FROM product_marginality_history WHERE product_id = ?
"""

# =========================================================================
# Type-safe query parameter helpers
# =========================================================================


# These type aliases document the expected parameter tuple structure for each query
# They don't enforce at runtime but help IDEs and type checkers

ProductIdBySkuParams = tuple[str]
InsertProductParams = tuple[int, str, str, float, float, float]
UpdateProductParams = tuple[str, float, float, float, int]
InsertProductStrategyParams = tuple[int, int, str, str, float]
InsertPriceHistoryParams = tuple[
    int,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    str,
]
InsertPriceCalcLogParams = tuple[int, str]
PriceHistoryBySkuParams = tuple[str]
InsertMarginalityParams = tuple[int, float, float, float]
AvgMarginalityParams = tuple[int, str]
DailyAggregateSelectParams = tuple[str, str]
DailyAggregateUpdateParams = tuple[float, float, float, float, int, str, str]
DailyAggregateInsertParams = tuple[str, str, float, float, float, float, int]
DailyTrendsParams = tuple[int]
DailyDeviationParams = tuple[int]
CleanupParams = tuple[str]
LastCleanupParams = tuple[str]
ProductDeleteByPidParams = tuple[int]
