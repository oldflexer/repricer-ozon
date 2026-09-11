"""
Analytics repository implementation - Part 3: Export and heatmap methods.
"""

from pathlib import Path
from typing import Any, Optional

import pandas as pd

from config.settings import settings
from core.enums import StrategyType
from core.protocols.repository import IAnalyticsRepository

from .base import BaseRepository


class AnalyticsRepository(BaseRepository, IAnalyticsRepository):
    """Repository for analytical queries."""
    
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
    
    def get_top_bottom_marginality(self, limit: int = 3) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Возвращает топ и худшие товары по маржинальности."""
        with self._get_connection() as conn:
            top = pd.read_sql_query(
                """
                SELECT
                    p.sku, p.product_name, ph.timestamp,
                    ROUND(ph.result_target_price * ph.discount_coef, 0) as price,
                    ROUND(ph.marginality * 100, 2) as margin_pct
                FROM product_price_history ph
                JOIN product p ON p.product_id = ph.product_id
                WHERE ph.timestamp = (
                    SELECT MAX(timestamp) FROM product_price_history WHERE product_id = ph.product_id
                )
                ORDER BY ph.marginality DESC
                LIMIT ?
                """,
                conn,
                params=(limit,),
            )
            bottom = pd.read_sql_query(
                """
                SELECT
                    p.sku, p.product_name, ph.timestamp,
                    ROUND(ph.result_target_price * ph.discount_coef, 0) as price,
                    ROUND(ph.marginality * 100, 2) as margin_pct
                FROM product_price_history ph
                JOIN product p ON p.product_id = ph.product_id
                WHERE ph.timestamp = (
                    SELECT MAX(timestamp) FROM product_price_history WHERE product_id = ph.product_id
                )
                ORDER BY ph.marginality ASC
                LIMIT ?
                """,
                conn,
                params=(limit,),
            )
        return top, bottom
    
    def get_update_heatmap(self, days: int = 90) -> pd.DataFrame:
        """Возвращает данные для тепловой карты обновлений."""
        with self._get_connection() as conn:
            query = """
                SELECT
                    date(timestamp) as day,
                    COUNT(*) as updates
                FROM product_price_history
                WHERE timestamp >= datetime('now', ?)
                GROUP BY date(timestamp)
                ORDER BY day
            """
            return pd.read_sql_query(query, conn, params=(f'-{days} days',))
    
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