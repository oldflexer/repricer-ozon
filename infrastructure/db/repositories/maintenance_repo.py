"""
Maintenance repository implementation - Part 2: Cleanup and run tracking methods.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Optional

from config.settings import settings
from core.protocols.repository import IMaintenanceRepository
from infrastructure.logger import logger

from .base import BaseRepository
from ..queries import (
    SQL_DELETE_MARGINALITY_HISTORY_BEFORE,
    SQL_DELETE_MARGINALITY_HISTORY_BY_PID,
    SQL_DELETE_PRICE_CALC_LOGS_BY_HISTORY,
    SQL_DELETE_PRICE_HISTORY_BEFORE,
    SQL_DELETE_PRICE_HISTORY_BY_PID,
    SQL_DELETE_PRODUCT,
    SQL_DELETE_PRODUCT_STRATEGIES_BY_PID,
    SQL_SELECT_LAST_CLEANUP,
    SQL_SELECT_LAST_RUN,
    SQL_SELECT_PRODUCT_ID_BY_SKU,
    SQL_UPDATE_LAST_CLEANUP,
    SQL_UPDATE_LAST_RUN,
)

from ..maintenance import _utc_now_naive, _subtract_months


class MaintenanceRepository(BaseRepository, IMaintenanceRepository):
    """Repository for database maintenance operations."""
    
    def get_last_cleanup_date(self) -> datetime | None:
        """Возвращает дату последней автоматической очистки БД."""
        with self._get_connection() as conn:
            row = conn.execute(SQL_SELECT_LAST_CLEANUP).fetchone()
            if row and row["value"]:
                try:
                    dt = datetime.fromisoformat(row["value"])
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=UTC)
                    return dt
                except Exception:
                    return None
            return None
    
    def set_last_cleanup_date(self, dt: datetime) -> None:
        """Устанавливает дату последней автоматической очистки БД."""
        if dt.tzinfo is not None:
            dt = dt.astimezone(UTC).replace(tzinfo=None)
        dt_str = dt.isoformat()
        with self._get_connection() as conn:
            conn.execute(
                SQL_UPDATE_LAST_CLEANUP,
                (dt_str,),
            )
            conn.commit()
    
    def get_last_repricing_run(self) -> datetime | None:
        """Возвращает дату последнего запуска репрайсинга."""
        with self._get_connection() as conn:
            row = conn.execute(SQL_SELECT_LAST_RUN).fetchone()
            if row and row["value"]:
                try:
                    dt = datetime.fromisoformat(row["value"])
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=UTC)
                    return dt
                except Exception:
                    return None
            return None
    
    def set_last_repricing_run(self, dt: datetime) -> None:
        """Устанавливает дату последнего запуска репрайсинга."""
        if dt.tzinfo is not None:
            dt = dt.astimezone(UTC).replace(tzinfo=None)
        dt_str = dt.isoformat()
        with self._get_connection() as conn:
            conn.execute(
                SQL_UPDATE_LAST_RUN,
                (dt_str,),
            )
            conn.commit()
    
    def auto_cleanup_if_needed(
        self,
        months: int = settings.CLEANUP_MONTHS,
        days_threshold: int = settings.CLEANUP_DAYS_THRESHOLD,
    ) -> int:
        """Запускает очистку БД, если с последней очистки прошло больше days_threshold дней."""
        last = self.get_last_cleanup_date()
        now_utc_naive = _utc_now_naive()
        
        if last is None:
            deleted = self.delete_records_older_than(months)
            self.set_last_cleanup_date(datetime.now(UTC))
            return deleted
        
        last_naive = last.astimezone(UTC).replace(tzinfo=None)
        if (now_utc_naive - last_naive).days >= days_threshold:
            deleted = self.delete_records_older_than(months)
            self.set_last_cleanup_date(datetime.now(UTC))
            return deleted
        return 0