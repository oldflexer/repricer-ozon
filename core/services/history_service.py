"""
Сервис для сохранения истории цен и дневных агрегатов.
"""

import asyncio
from typing import List, Dict, Any, Optional

from core.entities import ProductInfo, PricingData, PriceCalculationResult
from core.repository import IProductRepository
from infrastructure.logger import logger


class HistoryService:
    """Сервис для сохранения истории цен и дневных агрегатов."""

    def __init__(self, repository: IProductRepository, api_client):
        self.repo = repository
        self.api = api_client

    async def save_history(
        self,
        results_data: List[tuple],
        updates: List[Dict[str, Any]],
        valid_ids: List[int],
        dry_run: bool,
        update_results: Dict[int, Dict],
        wait_seconds: int = 10,
    ) -> None:
        """
        Сохраняет историю цен и дневные агрегаты.

        В случае реального запуска (не dry-run) запрашивает свежие цены
        для получения real_price и обновляет соответствующие записи.
        """
        if dry_run:
            for product, pricing, result in results_data:
                self.repo.save_price_history(product.sku, pricing, result, real_price=None)
            return

        if not update_results:
            for product, pricing, result in results_data:
                self.repo.save_price_history(product.sku, pricing, result, real_price=None)
                self.repo.save_daily_aggregates(product.sku, pricing, result, real_price=None)
            return

        logger.info("Запрашиваем актуальные цены для получения real_price...")
        await asyncio.sleep(wait_seconds)
        fresh_prices = await self.api.get_product_prices(valid_ids)
        fresh_dict = {p.product_id: p for p in fresh_prices}

        for product, pricing, result in results_data:
            fresh = fresh_dict.get(product.product_id)
            real_price_value = None

            if fresh:
                index_prices, index_data = [], []
                if (
                    fresh.external_index_data_price
                    and fresh.external_index_data_index
                    and fresh.external_index_data_index != 0
                ):
                    index_prices.append(fresh.external_index_data_price)
                    index_data.append(fresh.external_index_data_index)
                if (
                    fresh.ozon_index_data_price
                    and fresh.ozon_index_data_index
                    and fresh.ozon_index_data_index != 0
                ):
                    index_prices.append(fresh.ozon_index_data_price)
                    index_data.append(fresh.ozon_index_data_index)
                if (
                    fresh.self_marketplaces_index_data_price
                    and fresh.self_marketplaces_index_data_index
                    and fresh.self_marketplaces_index_data_index != 0
                ):
                    index_prices.append(fresh.self_marketplaces_index_data_price)
                    index_data.append(fresh.self_marketplaces_index_data_index)

                if index_prices and index_data:
                    approx_index_price = sum(index_prices) / len(index_prices)
                    approx_index_data = sum(index_data) / len(index_data)
                    real_price_value = round(approx_index_price * approx_index_data)
                    logger.info(f"Товар {product.sku}: real_price={real_price_value}")

            if real_price_value is not None:
                self.repo.update_real_customer_price(product.sku, real_price_value)
                self.repo.save_price_history(product.sku, pricing, result, real_price=real_price_value)
                self.repo.save_daily_aggregates(product.sku, pricing, result, real_price=real_price_value)
                for u in updates:
                    if u["sku"] == product.sku:
                        u["new_price"] = real_price_value
                        break
            else:
                self.repo.save_price_history(product.sku, pricing, result, real_price=None)
                if fresh is None:
                    logger.warning(f"Товар {product.sku}: свежие цены не получены")