# products_parser.py
import asyncio
import logging
from typing import List, Dict, Optional

from src.parser import OzonParser

logger = logging.getLogger(__name__)


class ProductsParser:
    """Парсинг информации о наших товарах (реальная цена с витрины Ozon)."""

    async def fetch_real_prices(
        self,
        products: List[Dict],
        parser: Optional[OzonParser] = None
    ) -> Dict[str, Optional[float]]:
        real_prices = {}

        if parser is not None:
            # Используем переданный парсер
            for product in products:
                sku = product['sku']
                price = await parser.fetch_price_by_sku(sku)
                if price is not None:
                    logger.info(f"Товар {sku}: реальная цена = {price}")
                else:
                    logger.info(f"Товар {sku}: реальная цена не найдена")
                real_prices[sku] = price
        else:
            # Создаём собственный (старое поведение, для тестов и Streamlit-кнопок)
            async with OzonParser() as p:
                return await self.fetch_real_prices(products, parser=p)

        return real_prices