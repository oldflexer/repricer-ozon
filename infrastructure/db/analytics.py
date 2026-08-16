"""
Миксин для аналитических методов (KPI, ROI, heatmap, ABC и т.д.).
"""

from typing import Any

import pandas as pd

from .base import DBConnectionMixin


class AnalyticsMixin(DBConnectionMixin):
    """Миксин, добавляющий методы для аналитики и отчётности."""

    def get_strategy_roi(self) -> pd.DataFrame:
        """Возвращает аналитику эффективности стратегий (ROI) за последние 30 дней."""
        with self._get_connection() as conn:
            query = """
                SELECT
                    s.strategy_name,
                    AVG( ph.result_target_price - (
                        p.net_price +
                        (ph.result_target_price * ph.sales_percent_fbs / 100) +
                        (ph.fbs_first_mile_min_amount + ph.fbs_first_mile_max_amount)/2 +
                        (ph.fbs_direct_flow_trans_min_amount + ph.fbs_direct_flow_trans_max_amount)/2 +
                        ph.fbs_deliv_to_customer_amount
                    ) ) as avg_abs_profit,
                    AVG(ph.marginality) as avg_marginality,
                    COUNT(*) as updates_count
                FROM product_price_history ph
                JOIN product p ON ph.product_id = p.product_id
                JOIN product_strategy ps ON ph.product_id = ps.product_id
                JOIN strategy s ON ps.strategy_id = s.id
                WHERE ph.timestamp >= datetime('now', '-30 days')
                GROUP BY s.id
            """
            return pd.read_sql_query(query, conn)

    def get_ozon_index_vs_price(self) -> pd.DataFrame:
        """Возвращает сравнение реальной цены и индекса Ozon для последней записи каждого товара."""
        with self._get_connection() as conn:
            query = """
                SELECT
                    p.sku,
                    p.product_name,
                    ph.ozon_index_data_price,
                    (ph.result_target_price * ph.discount_coef) as real_price,
                    ph.marginality,
                    ph.ozon_index_data_index
                FROM product_price_history ph
                JOIN product p ON p.product_id = ph.product_id
                WHERE ph.timestamp = (
                    SELECT MAX(timestamp) FROM product_price_history WHERE product_id = ph.product_id
                )
                AND ph.ozon_index_data_price > 0
                ORDER BY ph.ozon_index_data_price
            """
            return pd.read_sql_query(query, conn)

    def get_kpi_metrics(self) -> dict[str, Any]:
        """Возвращает ключевые метрики для дашборда."""
        with self._get_connection() as conn:
            today_margin = conn.execute(
                "SELECT AVG(marginality) FROM product_price_history "
                "WHERE timestamp >= datetime('now', '-1 day')"
            ).fetchone()[0]
            yesterday_margin = conn.execute(
                "SELECT AVG(marginality) FROM product_price_history "
                "WHERE timestamp >= datetime('now', '-2 days') "
                "AND timestamp < datetime('now', '-1 day')"
            ).fetchone()[0]
            updates_week = conn.execute(
                "SELECT COUNT(*) FROM product_price_history "
                "WHERE timestamp >= datetime('now', '-7 days')"
            ).fetchone()[0]
            unprofitable = conn.execute(
                """
                WITH last_prices AS (
                    SELECT ph.product_id, ph.marginality,
                        ROW_NUMBER() OVER (PARTITION BY ph.product_id ORDER BY ph.timestamp DESC) as rn
                    FROM product_price_history ph
                )
                SELECT COUNT(*) FROM last_prices
                WHERE rn = 1 AND marginality < 0
                """
            ).fetchone()[0]
            no_index = conn.execute(
                """
                SELECT COUNT(DISTINCT p.product_id)
                FROM product p
                JOIN product_price_history ph ON p.product_id = ph.product_id
                WHERE ph.timestamp = (
                    SELECT MAX(timestamp) FROM product_price_history WHERE product_id = p.product_id
                )
                AND (ph.ozon_index_data_price = 0 OR ph.ozon_index_data_price IS NULL)
                """
            ).fetchone()[0]
            return {
                "avg_margin_today": today_margin * 100 if today_margin else 0,
                "avg_margin_yesterday": yesterday_margin * 100 if yesterday_margin else 0,
                "updates_last_week": updates_week,
                "unprofitable_count": unprofitable,
                "no_index_count": no_index,
            }

    def get_recent_history(self, limit: int = 100) -> pd.DataFrame:
        """Возвращает последние записи истории цен для дашборда."""
        with self._get_connection() as conn:
            return pd.read_sql_query(
                """
                SELECT
                    p.sku as "SKU",
                    ph.timestamp,
                    ROUND(ph.result_target_price * ph.discount_coef, 0) as "Цена",
                    ph.marginality as "Маржинальность"
                FROM product_price_history ph
                JOIN product p ON p.product_id = ph.product_id
                ORDER BY ph.timestamp DESC
                LIMIT ?
                """,
                conn,
                params=(limit,),
            )

    def get_strategy_performance(self, days: int = 30) -> pd.DataFrame:
        """Возвращает эффективность стратегий за указанный период."""
        with self._get_connection() as conn:
            return pd.read_sql_query(
                """
                SELECT
                    s.strategy_name as "Стратегия",
                    AVG(ph.marginality) * 100 as "Средняя маржинальность (%)",
                    COUNT(*) as "Количество обновлений (30 дней)"
                FROM product_price_history ph
                JOIN product_strategy ps ON ph.product_id = ps.product_id
                JOIN strategy s ON ps.strategy_id = s.id
                WHERE ph.timestamp >= datetime('now', ? || ' days')
                GROUP BY s.id
                """,
                conn,
                params=(-days,),
            )

    def get_stale_products(self, days: int = 7) -> pd.DataFrame:
        """Возвращает товары, у которых давно не было обновлений цен."""
        with self._get_connection() as conn:
            return pd.read_sql_query(
                """
                SELECT
                    p.sku, p.product_name,
                    MAX(ph.timestamp) as last_update,
                    JULIANDAY('now') - JULIANDAY(MAX(ph.timestamp)) as days_stale
                FROM product_price_history ph
                JOIN product p ON p.product_id = ph.product_id
                GROUP BY p.sku
                HAVING days_stale > ?
                ORDER BY days_stale DESC
                """,
                conn,
                params=(days,),
            )

    def get_update_heatmap(self, days: int = 90) -> pd.DataFrame:
        """Возвращает данные для тепловой карты обновлений."""
        with self._get_connection() as conn:
            return pd.read_sql_query(
                """
                SELECT
                    strftime('%w', timestamp) as weekday,
                    strftime('%H', timestamp) as hour,
                    COUNT(*) as updates
                FROM product_price_history
                WHERE timestamp >= datetime('now', ? || ' days')
                GROUP BY weekday, hour
                """,
                conn,
                params=(-days,),
            )

    def get_top_bottom_marginality(self, limit: int = 5) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Возвращает топ-N и худшие N товаров по маржинальности."""
        with self._get_connection() as conn:
            df = pd.read_sql_query(
                """
                SELECT
                    p.sku, p.product_name,
                    ph.marginality * 100 as marginality_pct
                FROM product_price_history ph
                JOIN product p ON p.product_id = ph.product_id
                WHERE ph.timestamp = (
                    SELECT MAX(timestamp) FROM product_price_history WHERE product_id = ph.product_id
                )
                ORDER BY ph.marginality DESC
                """,
                conn,
            )
            return df.head(limit), df.tail(limit)

    def get_recent_changes(self, limit: int = 10) -> pd.DataFrame:
        """Возвращает последние изменения цен (для ленты активности)."""
        with self._get_connection() as conn:
            return pd.read_sql_query(
                """
                SELECT
                    p.sku, p.product_name, ph.timestamp,
                    ROUND(ph.result_target_price * ph.discount_coef, 0) as price,
                    ROUND(ph.marginality * 100, 2) as margin_pct
                FROM product_price_history ph
                JOIN product p ON p.product_id = ph.product_id
                ORDER BY ph.timestamp DESC
                LIMIT ?
                """,
                conn,
                params=(limit,),
            )

    def export_full_history(self) -> pd.DataFrame:
        """Экспортирует всю историю цен для выгрузки."""
        with self._get_connection() as conn:
            return pd.read_sql_query(
                """
                SELECT
                    p.sku, p.product_name, ph.timestamp,
                    ROUND(ph.result_target_price * ph.discount_coef, 0) as price,
                    ROUND(ph.marginality * 100, 2) as margin_pct
                FROM product_price_history ph
                JOIN product p ON p.product_id = ph.product_id
                ORDER BY ph.timestamp DESC
                """,
                conn,
            )

    def get_commission_analysis(self) -> pd.DataFrame:
        """Возвращает детальный анализ комиссий для последних записей товаров."""
        with self._get_connection() as conn:
            return pd.read_sql_query(
                """
                SELECT
                    p.sku,
                    p.product_name,
                    ph.result_target_price,
                    ph.discount_coef,
                    ph.sales_percent_fbs,
                    ph.fbs_first_mile_min_amount,
                    ph.fbs_first_mile_max_amount,
                    ph.fbs_direct_flow_trans_min_amount,
                    ph.fbs_direct_flow_trans_max_amount,
                    ph.fbs_deliv_to_customer_amount,
                    ph.external_index_data_price,
                    ph.ozon_index_data_price,
                    ph.ozon_index_data_index,
                    ph.self_marketplaces_index_data_price,
                    (ph.result_target_price * ph.discount_coef) as real_price,
                    ph.marginality
                FROM product_price_history ph
                JOIN product p ON p.product_id = ph.product_id
                WHERE ph.timestamp = (
                    SELECT MAX(timestamp) FROM product_price_history WHERE product_id = ph.product_id
                )
                ORDER BY p.sku
                """,
                conn,
            )

    def get_all_last_prices(self) -> pd.DataFrame:
        """Возвращает последние цены и маржинальность для всех товаров."""
        with self._get_connection() as conn:
            query = """
                SELECT
                    p.sku,
                    p.product_name,
                    COALESCE(p.real_customer_price, ph.customer_price) as last_price,
                    ph.marginality as last_margin
                FROM (
                    SELECT product_id,
                        CASE WHEN real_price IS NOT NULL THEN real_price
                             ELSE result_target_price * discount_coef END as customer_price,
                        marginality,
                        ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY timestamp DESC) as rn
                    FROM product_price_history
                ) ph
                JOIN product p ON p.product_id = ph.product_id
                WHERE ph.rn = 1
            """
            return pd.read_sql_query(query, conn)
