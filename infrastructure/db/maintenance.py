"""
Миксин для методов обслуживания БД (очистка, удаление записей).
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from config.settings import settings
from infrastructure.logger import logger
from .base import DBConnectionMixin
from .queries import (
    SQL_SELECT_PRODUCT_ID_BY_SKU,
    SQL_DELETE_PRODUCT_STRATEGIES_BY_PID,
    SQL_DELETE_PRICE_HISTORY_BY_PID,
    SQL_DELETE_MARGINALITY_HISTORY_BY_PID,
    SQL_DELETE_PRODUCT,
    SQL_DELETE_PRICE_HISTORY_BEFORE,
    SQL_DELETE_MARGINALITY_HISTORY_BEFORE,
    SQL_DELETE_PRICE_CALC_LOGS_BY_HISTORY,
    SQL_SELECT_LAST_CLEANUP,
    SQL_UPDATE_LAST_CLEANUP,
)


def _utc_now_naive() -> datetime:
    """Returns current UTC time as naive datetime (for SQLite storage)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _subtract_months(dt: datetime, months: int) -> datetime:
    """Subtract months from datetime, handling month boundaries correctly."""
    year = dt.year
    month = dt.month - months
    while month <= 0:
        month += 12
        year -= 1
    # Keep same day, but handle month-end (e.g., Jan 31 -> Feb 28)
    day = min(dt.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return datetime(year, month, day, dt.hour, dt.minute, dt.second, dt.microsecond)


class MaintenanceMixin(DBConnectionMixin):
    """Миксин, добавляющий методы обслуживания БД."""

    def delete_product(self, sku: str) -> Dict[str, int]:
        """Удаляет товар и все связанные записи."""
        with self._get_connection() as conn:
            product_id_row = conn.execute(
                SQL_SELECT_PRODUCT_ID_BY_SKU, (sku,)
            ).fetchone()
            if not product_id_row:
                return {"product": 0, "strategies": 0, "price_history": 0, "margin_history": 0}
            pid = product_id_row["product_id"]
            deleted_strategies = conn.execute(
                SQL_DELETE_PRODUCT_STRATEGIES_BY_PID, (pid,)
            ).rowcount
            deleted_price_history = conn.execute(
                SQL_DELETE_PRICE_HISTORY_BY_PID, (pid,)
            ).rowcount
            deleted_margin_history = conn.execute(
                SQL_DELETE_MARGINALITY_HISTORY_BY_PID, (pid,)
            ).rowcount
            deleted_product = conn.execute(
                SQL_DELETE_PRODUCT, (pid,)
            ).rowcount
            conn.commit()
            return {
                "product": deleted_product,
                "strategies": deleted_strategies,
                "price_history": deleted_price_history,
                "margin_history": deleted_margin_history,
            }

    def delete_old_records(self, days: int) -> int:
        """Удаляет записи истории старше указанного количества дней."""
        with self._get_connection() as conn:
            cutoff = _utc_now_naive() - timedelta(days=days)
            cutoff_str = cutoff.isoformat()
            deleted_price = conn.execute(
                SQL_DELETE_PRICE_HISTORY_BEFORE, (cutoff_str,)
            ).rowcount
            deleted_margin = conn.execute(
                SQL_DELETE_MARGINALITY_HISTORY_BEFORE, (cutoff_str,)
            ).rowcount
            conn.execute(
                SQL_DELETE_PRICE_CALC_LOGS_BY_HISTORY,
                (cutoff_str,),
            )
            conn.commit()
            return deleted_price + deleted_margin

    def delete_records_older_than(self, months: int = settings.CLEANUP_MONTHS) -> int:
        """Удаляет записи истории старше указанного количества месяцев."""
        with self._get_connection() as conn:
            cutoff = _subtract_months(_utc_now_naive(), months)
            cutoff_str = cutoff.isoformat()
            deleted_price = conn.execute(
                SQL_DELETE_PRICE_HISTORY_BEFORE, (cutoff_str,)
            ).rowcount
            deleted_margin = conn.execute(
                SQL_DELETE_MARGINALITY_HISTORY_BEFORE, (cutoff_str,)
            ).rowcount
            conn.execute(
                SQL_DELETE_PRICE_CALC_LOGS_BY_HISTORY,
                (cutoff_str,),
            )
            conn.commit()
            logger.info(
                f"Очистка БД: удалено {deleted_price} записей истории цен и {deleted_margin} "
                f"записей маржинальности старше {months} месяцев"
            )
            return deleted_price + deleted_margin

    def get_last_cleanup_date(self) -> Optional[datetime]:
        """Возвращает дату последней автоматической очистки БД."""
        with self._get_connection() as conn:
            row = conn.execute(
                SQL_SELECT_LAST_CLEANUP
            ).fetchone()
            if row and row["value"]:
                try:
                    dt = datetime.fromisoformat(row["value"])
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except Exception:
                    return None
            return None

    def set_last_cleanup_date(self, dt: datetime) -> None:
        """Устанавливает дату последней автоматической очистки БД."""
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        dt_str = dt.isoformat()
        with self._get_connection() as conn:
            conn.execute(
                SQL_UPDATE_LAST_CLEANUP,
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
            self.set_last_cleanup_date(datetime.now(timezone.utc))
            return deleted

        last_naive = last.astimezone(timezone.utc).replace(tzinfo=None)
        if (now_utc_naive - last_naive).days >= days_threshold:
            deleted = self.delete_records_older_than(months)
            self.set_last_cleanup_date(datetime.now(timezone.utc))
            return deleted
        return 0