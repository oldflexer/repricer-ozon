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
                offer_id = product['offer_id']
                price = await parser.fetch_price_by_sku(offer_id)
                if price is not None:
                    logger.info(f"Товар {offer_id}: реальная цена = {price}")
                else:
                    logger.info(f"Товар {offer_id}: реальная цена не найдена")
                real_prices[offer_id] = price
        return real_prices