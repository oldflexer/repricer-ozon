"""
Миксин для методов обслуживания БД (очистка, удаление записей).
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from config.settings import settings
from infrastructure.logger import logger
from .base import DBConnectionMixin


class MaintenanceMixin(DBConnectionMixin):
    """Миксин, добавляющий методы обслуживания БД."""

    def delete_product(self, sku: str) -> Dict[str, int]:
        """Удаляет товар и все связанные записи."""
        with self._get_connection() as conn:
            product_id_row = conn.execute(
                "SELECT product_id FROM product WHERE sku = ?", (sku,)
            ).fetchone()
            if not product_id_row:
                return {"product": 0, "strategies": 0, "price_history": 0, "margin_history": 0}
            pid = product_id_row["product_id"]
            deleted_strategies = conn.execute(
                "DELETE FROM product_strategy WHERE product_id = ?", (pid,)
            ).rowcount
            deleted_price_history = conn.execute(
                "DELETE FROM product_price_history WHERE product_id = ?", (pid,)
            ).rowcount
            deleted_margin_history = conn.execute(
                "DELETE FROM product_marginality_history WHERE product_id = ?", (pid,)
            ).rowcount
            deleted_product = conn.execute(
                "DELETE FROM product WHERE product_id = ?", (pid,)
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
            cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
            deleted_price = conn.execute(
                "DELETE FROM product_price_history WHERE timestamp < ?", (cutoff,)
            ).rowcount
            deleted_margin = conn.execute(
                "DELETE FROM product_marginality_history WHERE timestamp < ?", (cutoff,)
            ).rowcount
            conn.execute(
                """
                DELETE FROM price_calculation_logs
                WHERE history_id IN (SELECT id FROM product_price_history WHERE timestamp < ?)
                """,
                (cutoff,),
            )
            conn.commit()
            return deleted_price + deleted_margin

    def delete_records_older_than(self, months: int = settings.CLEANUP_MONTHS) -> int:
        """Удаляет записи истории старше указанного количества месяцев."""
        with self._get_connection() as conn:
            cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=months * 30)
            deleted_price = conn.execute(
                "DELETE FROM product_price_history WHERE timestamp < ?", (cutoff,)
            ).rowcount
            deleted_margin = conn.execute(
                "DELETE FROM product_marginality_history WHERE timestamp < ?", (cutoff,)
            ).rowcount
            conn.execute(
                """
                DELETE FROM price_calculation_logs
                WHERE history_id IN (SELECT id FROM product_price_history WHERE timestamp < ?)
                """,
                (cutoff,),
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
                "SELECT value FROM maintenance WHERE key = 'last_cleanup'"
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
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE maintenance SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE key = 'last_cleanup'",
                (dt.isoformat(),),
            )
            conn.commit()

    def auto_cleanup_if_needed(
        self,
        months: int = settings.CLEANUP_MONTHS,
        days_threshold: int = settings.CLEANUP_DAYS_THRESHOLD,
    ) -> int:
        """Запускает очистку БД, если с последней очистки прошло больше days_threshold дней."""
        last = self.get_last_cleanup_date()
        now_utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)

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