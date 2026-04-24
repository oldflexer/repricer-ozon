import asyncio
import logging
from typing import List, Dict, Optional

from src.parser import OzonParser

logger = logging.getLogger(__name__)


class ProductsParser:
    """Парсинг информации о наших товарах (реальная цена с витрины Ozon)."""

    async def fetch_real_prices(self, products: List[Dict]) -> Dict[str, Optional[float]]:
        real_prices = {}
        async with OzonParser() as parser:
            for product in products:
                sku = product['sku']
                price = await parser.fetch_price_by_sku(sku)
                if price is not None:
                    logger.info(f"Товар {sku}: реальная цена = {price}")
                else:
                    logger.info(f"Товар {sku}: реальная цена не найдена")
                real_prices[sku] = price
        return real_prices