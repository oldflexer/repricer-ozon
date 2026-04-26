# competitors_parser.py
import asyncio
import logging
from typing import List, Dict, Set, Optional

from src.parser import OzonParser
from src.database import Database

logger = logging.getLogger(__name__)


class CompetitorsParser:
    """Парсинг конкурентов и сохранение в БД."""

    def __init__(self, db: Database):
        self.db = db
        self._saved_prices: Set[int] = set()

    async def run(
        self,
        products: List[Dict],
        parser: Optional[OzonParser] = None
    ) -> Dict:
        stats = {'competitor_prices_parsed': 0}
        self._saved_prices.clear()

        if parser is not None:
            return await self._parse_with_parser(products, parser)
        else:
            async with OzonParser() as p:
                return await self._parse_with_parser(products, p)

    async def _parse_with_parser(self, products: List[Dict], parser: OzonParser) -> Dict:
        stats = {'competitor_prices_parsed': 0}
        self._saved_prices.clear()

        for product in products:
            sku = product['sku']
            urls = product.get('competitor_urls', [])
            if not urls:
                continue

            results = await parser.get_prices(urls)
            valid_prices = 0
            for idx, (price, prod_name, shop_name) in enumerate(results):
                comp_id = self.db.get_or_create_competitor(urls[idx], prod_name, shop_name)
                self.db.link_product_competitor(sku, comp_id, idx + 1)
                if price is not None and comp_id not in self._saved_prices:
                    self.db.save_competitor_price(comp_id, price)
                    self._saved_prices.add(comp_id)
                    valid_prices += 1

            stats['competitor_prices_parsed'] += valid_prices
            logger.info(f"Товар {sku}: сохранено {valid_prices} цен конкурентов")

        return stats