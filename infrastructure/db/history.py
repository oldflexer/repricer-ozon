"""
Миксин для работы с историей цен и маржинальности.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

from core.entities import PriceCalculationResult, PricingData
from infrastructure.logger import logger
from .base import DBConnectionMixin


class HistoryMixin(DBConnectionMixin):
    """Миксин, добавляющий методы для работы с историей цен и маржинальности."""

    def save_price_history(
        self,
        sku: str,
        pricing: PricingData,
        result: PriceCalculationResult,
        real_price: Optional[float] = None,
    ) -> bool:
        """Сохраняет запись истории цен для товара."""
        with self._get_connection() as conn:
            product_id = conn.execute(
                "SELECT product_id FROM product WHERE sku = ?", (sku,)
            ).fetchone()
            if not product_id:
                return False
            pid = product_id["product_id"]
            log_details_json = json.dumps(result.log_details, ensure_ascii=False)

            cursor = conn.execute(
                """
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
                """,
                (
                    pid,
                    pricing.min_price,
                    pricing.price,
                    pricing.old_price,
                    pricing.marketing_seller_price,
                    pricing.external_index_data_price,
                    pricing.external_index_data_index,
                    pricing.ozon_index_data_price,
                    pricing.ozon_index_data_index,
                    pricing.self_marketplaces_index_data_price,
                    pricing.self_marketplaces_index_data_index,
                    result.result_target_price,
                    result.log_details.get("discount_coef", 0),
                    result.marginality,
                    pricing.sales_percent_fbs,
                    pricing.acquiring,
                    pricing.fbs_first_mile_min_amount,
                    pricing.fbs_first_mile_max_amount,
                    pricing.fbs_direct_flow_trans_min_amount,
                    pricing.fbs_direct_flow_trans_max_amount,
                    pricing.fbs_deliv_to_customer_amount,
                    pricing.fbo_deliv_to_customer_amount,
                    pricing.fbo_direct_flow_trans_min_amount,
                    pricing.fbo_direct_flow_trans_max_amount,
                    real_price,
                    log_details_json,
                ),
            )
            history_id = cursor.lastrowid

            if log_details_json:
                conn.execute(
                    "INSERT INTO price_calculation_logs (history_id, log_details) VALUES (?, ?)",
                    (history_id, log_details_json),
                )

            conn.commit()
            return True

    def save_daily_aggregates(
        self,
        sku: str,
        pricing: PricingData,
        result: PriceCalculationResult,
        real_price: Optional[float] = None,
    ) -> None:
        """Сохраняет агрегированные данные за текущий день (avg, min, max)."""
        today = datetime.now(timezone.utc).date()
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT avg_price, avg_marginality, min_price, max_price, updates_count
                FROM product_price_daily
                WHERE product_id = (SELECT product_id FROM product WHERE sku = ?) AND date = ?
                """,
                (sku, today.isoformat()),
            ).fetchone()

            price_val = (
                real_price
                if real_price is not None
                else result.result_target_price * result.log_details.get("discount_coef", 1.0)
            )
            margin_val = result.marginality

            if row:
                avg_price = (row["avg_price"] * row["updates_count"] + price_val) / (
                    row["updates_count"] + 1
                )
                avg_marginality = (
                    row["avg_marginality"] * row["updates_count"] + margin_val
                ) / (row["updates_count"] + 1)
                min_price = min(row["min_price"], price_val)
                max_price = max(row["max_price"], price_val)
                updates_count = row["updates_count"] + 1

                conn.execute(
                    """
                    UPDATE product_price_daily
                    SET avg_price = ?, avg_marginality = ?, min_price = ?, max_price = ?, updates_count = ?
                    WHERE product_id = (SELECT product_id FROM product WHERE sku = ?) AND date = ?
                    """,
                    (avg_price, avg_marginality, min_price, max_price, updates_count, sku, today.isoformat()),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO product_price_daily
                    (product_id, date, avg_price, avg_marginality, min_price, max_price, updates_count)
                    VALUES ((SELECT product_id FROM product WHERE sku = ?), ?, ?, ?, ?, ?, ?)
                    """,
                    (sku, today.isoformat(), price_val, margin_val, price_val, price_val, 1),
                )
            conn.commit()

    def get_daily_trends_aggregated(self, days: int = 7) -> pd.DataFrame:
        """Возвращает агрегированные дневные тренды."""
        with self._get_connection() as conn:
            query = """
                SELECT
                    date as day,
                    AVG(avg_price) as avg_price,
                    AVG(avg_marginality) as avg_margin
                FROM product_price_daily
                WHERE date >= date('now', ? || ' days')
                GROUP BY date
                ORDER BY date
            """
            return pd.read_sql_query(query, conn, params=(-days,))

    def get_daily_trends(self, days: int = 7) -> pd.DataFrame:
        """Получает дневные тренды."""
        df = self.get_daily_trends_aggregated(days)
        if df.empty:
            with self._get_connection() as conn:
                query = """
                    SELECT
                        DATE(ph.timestamp) as day,
                        AVG(ph.result_target_price * ph.discount_coef) as avg_price,
                        AVG(ph.marginality) as avg_margin
                    FROM product_price_history ph
                    WHERE ph.timestamp >= datetime('now', ? || ' days')
                    GROUP BY day
                    ORDER BY day
                """
                return pd.read_sql_query(query, conn, params=(-days,))
        return df

    def get_daily_deviation(self, days: int = 30) -> pd.DataFrame:
        """Возвращает среднее отношение цены к индексу Ozon по дням."""
        with self._get_connection() as conn:
            query = """
                SELECT
                    DATE(ph.timestamp) as day,
                    AVG( (ph.result_target_price * ph.discount_coef) / NULLIF(ph.ozon_index_data_price, 0) ) as avg_ratio
                FROM product_price_history ph
                WHERE ph.ozon_index_data_price > 0
                AND ph.timestamp >= datetime('now', ? || ' days')
                GROUP BY day
                ORDER BY day
            """
            return pd.read_sql_query(query, conn, params=(-days,))

    def get_price_history(self, sku: str) -> List[Dict[str, Any]]:
        """Возвращает историю цен для товара."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
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
                """,
                (sku,),
            ).fetchall()
            result = []
            for row in rows:
                if row["real_price"] is not None:
                    customer_price = row["real_price"]
                else:
                    customer_price = row["result_target_price"] * row["discount_coef"]
                result.append(
                    {
                        "timestamp": row["timestamp"],
                        "customer_price": customer_price,
                        "marginality": row["marginality"],
                    }
                )
            return result

    def save_marginality(
        self,
        sku: str,
        marginality: float,
        marginality_week: float,
        marginality_month: float,
    ) -> bool:
        """Сохраняет значения маржинальности."""
        with self._get_connection() as conn:
            product_id = conn.execute(
                "SELECT product_id FROM product WHERE sku = ?", (sku,)
            ).fetchone()
            if not product_id:
                return False
            pid = product_id["product_id"]
            conn.execute(
                """
                INSERT INTO product_marginality_history
                (product_id, marginality, marginality_week, marginality_month)
                VALUES (?, ?, ?, ?)
                """,
                (pid, marginality, marginality_week, marginality_month),
            )
            conn.commit()
            return True

    def get_average_marginality(self, sku: str, days: int) -> Optional[float]:
        """Возвращает среднюю маржинальность за указанное количество дней."""
        with self._get_connection() as conn:
            product_id = conn.execute(
                "SELECT product_id FROM product WHERE sku = ?", (sku,)
            ).fetchone()
            if not product_id:
                return None
            pid = product_id["product_id"]
            cutoff = datetime.now() - timedelta(days=days)
            row = conn.execute(
                """
                SELECT AVG(marginality) FROM product_marginality_history
                WHERE product_id = ? AND timestamp >= ?
                """,
                (pid, cutoff.isoformat()),
            ).fetchone()
            return row[0] if row and row[0] else None

    def get_last_run_time(self) -> Optional[datetime]:
        """Возвращает время последнего успешного запуска репрайсинга."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT MAX(timestamp) FROM product_price_history").fetchone()
            if row and row[0]:
                return datetime.fromisoformat(row[0]).replace(tzinfo=timezone.utc)
            return None