"""
Marginality repository implementation.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Optional

from config.settings import settings
from core.protocols.repository import IMarginalityRepository

from .base import BaseRepository
from ..queries import (
    SQL_INSERT_MARGINALITY_HISTORY,
    SQL_SELECT_AVG_MARGINALITY,
    SQL_SELECT_PRODUCT_ID_BY_SKU,
)

from ..maintenance import _utc_now_naive


class MarginalityRepository(BaseRepository, IMarginalityRepository):
    """Repository for marginality operations."""
    
    def __init__(self, db_path: Optional[Path] = None) -> None:
        super().__init__(db_path)
        self._initialize_schema()
    
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