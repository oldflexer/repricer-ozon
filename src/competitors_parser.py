import asyncio
import logging
from typing import List, Dict, Set

from src.parser import OzonParser
from src.database import Database

logger = logging.getLogger(__name__)


class CompetitorsParser:
    """Парсинг конкурентов и сохранение в БД."""

    def __init__(self, db: Database):
        self.db = db
        self._saved_prices: Set[int] = set()

    async def run(self, products: List[Dict]) -> Dict:
        stats = {'competitor_prices_parsed': 0}
        self._saved_prices.clear()

        async with OzonParser() as parser:
            for product in products:
                offer_id = product['offer_id']
                urls = product.get('competitor_urls', [])
                if not urls:
                    continue

                results = await parser.get_prices(urls)
                valid_prices = 0
                for idx, (price, prod_name, shop_name) in enumerate(results):
                    comp_id = self.db.get_or_create_competitor(urls[idx], prod_name, shop_name)
                    self.db.link_product_competitor(offer_id, comp_id, idx + 1)
                    if price is not None and comp_id not in self._saved_prices:
                        self.db.save_competitor_price(comp_id, price)
                        self._saved_prices.add(comp_id)
                        valid_prices += 1

                stats['competitor_prices_parsed'] += valid_prices
                logger.info(f"Товар {offer_id}: сохранено {valid_prices} цен конкурентов")

        return stats