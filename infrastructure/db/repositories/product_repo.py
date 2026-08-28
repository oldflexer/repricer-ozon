"""
Product repository implementation.
"""

import sqlite3
from pathlib import Path
from typing import Any, Optional

from config.settings import settings
from core.entities import ProductInfo, StrategyInterval
from core.protocols.repository import IProductRepository

from .base import BaseRepository
from ..queries import (
    SQL_INSERT_PRODUCT,
    SQL_INSERT_PRODUCT_STRATEGY,
    SQL_SELECT_PRODUCT_BY_SKU,
    SQL_SELECT_PRODUCT_ID_BY_SKU,
    SQL_SELECT_PRODUCT_STRATEGIES,
    SQL_SELECT_STRATEGY_COUNTS,
    SQL_UPDATE_PRODUCT_REAL_PRICE,
    SQL_UPDATE_PRODUCT_STRATEGIES,
)


class ProductRepository(BaseRepository, IProductRepository):
    """Repository for product CRUD operations and strategies."""
    
    def __init__(self, db_path: Optional[Path] = None) -> None:
        super().__init__(db_path)
        self._initialize_schema()
    
    def get_all_products(self) -> list[ProductInfo]:
        """Возвращает список всех товаров из таблицы product."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT product_id, offer_id, sku, product_name, rip, net_price,
                       real_customer_price
                FROM product
            """).fetchall()
            return [
                ProductInfo(
                    sku=r["sku"],
                    product_name=r["product_name"],
                    product_id=r["product_id"],
                    offer_id=r["offer_id"],
                    min_price=r["rip"] or 0.0,
                    cost_price=r["net_price"] or 0.0,
                    real_customer_price=r["real_customer_price"],
                )
                for r in rows
            ]
    
    def upsert_product(self, product: ProductInfo) -> bool:
        """Создаёт или обновляет запись о товаре."""
        with self._get_connection() as conn:
            conn.execute(
                SQL_INSERT_PRODUCT,
                (
                    product.sku,
                    product.product_name,
                    product.product_id,
                    product.offer_id,
                    product.min_price,
                    product.cost_price,
                    product.real_customer_price,
                ),
            )
            conn.commit()
            return True
    
    def update_real_customer_price(self, sku: str, real_price: float) -> bool:
        """Обновляет реальную цену покупателя для товара."""
        with self._get_connection() as conn:
            conn.execute(
                SQL_UPDATE_PRODUCT_REAL_PRICE,
                (real_price, sku),
            )
            conn.commit()
            return True
    
    def get_strategies(self, sku: str) -> list[StrategyInterval]:
        """Возвращает интервалы стратегий для товара."""
        with self._get_connection() as conn:
            rows = conn.execute(
                SQL_SELECT_PRODUCT_STRATEGIES,
                (sku,),
            ).fetchall()
            return [
                StrategyInterval(
                    start=r["interval_start"],
                    end=r["interval_stop"],
                    strategy_type=r["strategy_id"],
                    percent=r["strategy_percent"],
                )
                for r in rows
            ]
    
    def set_strategies(self, sku: str, intervals: list[StrategyInterval]) -> bool:
        """Сохраняет интервалы стратегий для товара (заменяет существующие)."""
        with self._get_connection() as conn:
            product_id = conn.execute(
                SQL_SELECT_PRODUCT_ID_BY_SKU, (sku,)
            ).fetchone()
            if not product_id:
                return False
            pid = product_id["product_id"]
            
            conn.execute("DELETE FROM product_strategy WHERE product_id = ?", (pid,))
            for inv in intervals:
                conn.execute(
                    SQL_INSERT_PRODUCT_STRATEGY,
                    (pid, inv.start, inv.end, inv.strategy_type, inv.percent),
                )
            conn.commit()
            return True
    
    def get_strategy_counts(self) -> dict[str, int]:
        """Возвращает количество интервалов стратегий по типам."""
        with self._get_connection() as conn:
            rows = conn.execute(SQL_SELECT_STRATEGY_COUNTS).fetchall()
            return {r["strategy_name"]: r["count"] for r in rows}