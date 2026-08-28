"""
Price history repository implementation.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

from config.settings import settings
from core.entities import PriceCalculationResult, PricingData
from core.protocols.repository import IPriceHistoryRepository

from .base import BaseRepository
from ..queries import (
    SQL_INSERT_PRICE_CALCULATION_LOG,
    SQL_INSERT_PRICE_HISTORY,
    SQL_SELECT_MAX_PRICE_HISTORY_TIMESTAMP,
    SQL_SELECT_PRICE_HISTORY_BY_SKU,
    SQL_SELECT_PRODUCT_ID_BY_SKU,
)


class PriceHistoryRepository(BaseRepository, IPriceHistoryRepository):
    """Repository for price history operations."""
    
    def __init__(self, db_path: Optional[Path] = None) -> None:
        super().__init__(db_path)
        self._initialize_schema()
    
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
    
    def get_last_run_time(self) -> datetime | None:
        """Возвращает время последнего успешного запуска репрайсинга."""
        with self._get_connection() as conn:
            row = conn.execute(SQL_SELECT_MAX_PRICE_HISTORY_TIMESTAMP).fetchone()
            if row and row[0]:
                return datetime.fromisoformat(row[0]).replace(tzinfo=UTC)
            return None