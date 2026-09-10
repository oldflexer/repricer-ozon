"""
Миксин для работы с историей цен и маржинальности.
"""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd

from core.entities import PriceCalculationResult, PricingData

from .base import DBConnectionMixin
from .maintenance import _utc_now_naive
from .queries import (
    SQL_INSERT_DAILY_AGGREGATE,
    SQL_INSERT_MARGINALITY_HISTORY,
    SQL_INSERT_PRICE_CALCULATION_LOG,
    SQL_INSERT_PRICE_HISTORY,
    SQL_SELECT_AVG_MARGINALITY,
    SQL_SELECT_DAILY_AGGREGATE,
    SQL_SELECT_DAILY_DEVIATION,
    SQL_SELECT_DAILY_TRENDS_AGGREGATED,
    SQL_SELECT_DAILY_TRENDS_FALLBACK,
    SQL_SELECT_MAX_PRICE_HISTORY_TIMESTAMP,
    SQL_SELECT_PRICE_HISTORY_BY_SKU,
    SQL_SELECT_PRODUCT_ID_BY_SKU,
    SQL_UPDATE_DAILY_AGGREGATE,
)


class HistoryMixin(DBConnectionMixin):
    """Миксин, добавляющий методы для работы с историей цен и маржинальности."""

    def save_price_history(
        self,
        sku: str,
        pricing: PricingData,
        result: PriceCalculationResult,
        real_price: float | None = None,
    ) -> bool:
        """Сохраняет запись истории цен для товара."""
        with self._get_connection() as conn:
            product_id = conn.execute(SQL_SELECT_PRODUCT_ID_BY_SKU, (sku,)).fetchone()
            if not product_id:
                return False
            pid = product_id["product_id"]
            log_details_json = json.dumps(result.log_details, ensure_ascii=False)

            cursor = conn.execute(
                SQL_INSERT_PRICE_HISTORY,
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
                    SQL_INSERT_PRICE_CALCULATION_LOG,
                    (history_id, log_details_json),
                )

            conn.commit()
            return True

    def save_daily_aggregates(
        self,
        sku: str,
        result: PriceCalculationResult,
        real_price: float | None = None,
    ) -> None:
        """Сохраняет агрегированные данные за текущий день (avg, min, max)."""
        today = _utc_now_naive().date()
        today_str = today.isoformat()
        with self._get_connection() as conn:
            row = conn.execute(
                SQL_SELECT_DAILY_AGGREGATE,
                (sku, today_str),
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
                avg_marginality = (row["avg_marginality"] * row["updates_count"] + margin_val) / (
                    row["updates_count"] + 1
                )
                min_price = min(row["min_price"], price_val)
                max_price = max(row["max_price"], price_val)
                updates_count = row["updates_count"] + 1

                conn.execute(
                    SQL_UPDATE_DAILY_AGGREGATE,
                    (
                        avg_price,
                        avg_marginality,
                        min_price,
                        max_price,
                        updates_count,
                        sku,
                        today_str,
                    ),
                )
            else:
                conn.execute(
                    SQL_INSERT_DAILY_AGGREGATE,
                    (sku, today_str, price_val, margin_val, price_val, price_val, 1),
                )
            conn.commit()

    def get_daily_trends_aggregated(self, days: int = 7) -> pd.DataFrame:
        """Возвращает агрегированные дневные тренды."""
        with self._get_connection() as conn:
            return pd.read_sql_query(SQL_SELECT_DAILY_TRENDS_AGGREGATED, conn, params=(-days,))

    def get_daily_trends(self, days: int = 7) -> pd.DataFrame:
        """Получает дневные тренды."""
        df = self.get_daily_trends_aggregated(days)
        if df.empty:
            with self._get_connection() as conn:
                return pd.read_sql_query(SQL_SELECT_DAILY_TRENDS_FALLBACK, conn, params=(-days,))
        return df

    def get_daily_deviation(self, days: int = 30) -> pd.DataFrame:
        """Возвращает среднее отношение цены к индексу Ozon по дням."""
        with self._get_connection() as conn:
            return pd.read_sql_query(SQL_SELECT_DAILY_DEVIATION, conn, params=(-days,))

    def get_price_history(self, sku: str) -> list[dict[str, Any]]:
        """Возвращает историю цен для товара."""
        with self._get_connection() as conn:
            rows = conn.execute(
                SQL_SELECT_PRICE_HISTORY_BY_SKU,
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
            product_id = conn.execute(SQL_SELECT_PRODUCT_ID_BY_SKU, (sku,)).fetchone()
            if not product_id:
                return False
            pid = product_id["product_id"]
            conn.execute(
                SQL_INSERT_MARGINALITY_HISTORY,
                (pid, marginality, marginality_week, marginality_month),
            )
            conn.commit()
            return True

    def get_average_marginality(self, sku: str, days: int) -> float | None:
        """Возвращает среднюю маржинальность за указанное количество дней."""
        with self._get_connection() as conn:
            product_id = conn.execute(SQL_SELECT_PRODUCT_ID_BY_SKU, (sku,)).fetchone()
            if not product_id:
                return None
            pid = product_id["product_id"]
            cutoff = _utc_now_naive() - timedelta(days=days)
            row = conn.execute(
                SQL_SELECT_AVG_MARGINALITY,
                (pid, cutoff.isoformat()),
            ).fetchone()
            return row[0] if row and row[0] else None

    def get_last_run_time(self) -> datetime | None:
        """Возвращает время последнего успешного запуска репрайсинга."""
        with self._get_connection() as conn:
            row = conn.execute(SQL_SELECT_MAX_PRICE_HISTORY_TIMESTAMP).fetchone()
            if row and row[0]:
                return datetime.fromisoformat(row[0]).replace(tzinfo=UTC)
            return None
