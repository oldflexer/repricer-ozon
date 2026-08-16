"""
Сервис для сохранения истории цен и дневных агрегатов.
"""

from typing import Any

from core.repository import IRepository
from infrastructure.logger import logger


class HistoryService:
    """Сервис для сохранения истории цен и дневных агрегатов."""

    def __init__(self, repository: IRepository):
        self.repo = repository

    async def save_history(
        self,
        results_data: list[tuple],
        updates: list[dict[str, Any]],
        dry_run: bool,
        update_results: dict[int, dict],
    ) -> None:
        """
        Сохраняет историю цен и дневные агрегаты.
        Использует расчётные значения из result, без дополнительных API-запросов.
        """
        if dry_run:
            for product, pricing, result in results_data:
                self.repo.save_price_history(product.sku, pricing, result, real_price=None)
            return

        # Если не было обновлений (update_results пуст) – просто сохраняем без real_price
        if not update_results:
            for product, pricing, result in results_data:
                self.repo.save_price_history(product.sku, pricing, result, real_price=None)
                self.repo.save_daily_aggregates(product.sku, result, real_price=None)
            return

        # Для каждого товара вычисляем real_price из имеющихся данных
        for product, pricing, result in results_data:
            # Вычисляем real_price как result_target_price * discount_coef
            discount_coef = result.log_details.get("discount_coef", 1.0)
            real_price_value = round(result.result_target_price * discount_coef)

            logger.info(f"Товар {product.sku}: real_price (расчётное) = {real_price_value}")

            # Сохраняем историю и агрегаты с вычисленным real_price
            self.repo.save_price_history(product.sku, pricing, result, real_price=real_price_value)
            self.repo.save_daily_aggregates(product.sku, result, real_price=real_price_value)

            # Обновляем поле new_price в отчёте (для email)
            for u in updates:
                if u["sku"] == product.sku:
                    u["new_price"] = real_price_value
                    break
