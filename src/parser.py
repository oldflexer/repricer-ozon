import asyncio
import logging
from typing import List, Optional, Dict
import random

import nodriver as uc

from config.settings import PARSER_DELAY, PARSER_TIMEOUT, MAX_RETRIES

logger = logging.getLogger(__name__)


class OzonParser:
    """Асинхронный парсер цен Ozon на основе nodriver"""

    def __init__(self):
        self.browser: Optional[uc.Browser] = None
        self._cache: Dict[str, Optional[float]] = {}

    async def __aenter__(self) -> 'OzonParser':
        self.browser = await uc.start(headless=False)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            self.browser.stop()

    async def fetch_price(self, url: str) -> Optional[float]:
        if self.browser is None:
            raise RuntimeError("Браузер не инициализирован")

        if url in self._cache:
            logger.debug(f"Использовано кэшированное значение для {url}")
            return self._cache[url]

        base_timeout = PARSER_TIMEOUT
        for attempt in range(MAX_RETRIES):
            try:
                await asyncio.sleep(PARSER_DELAY + random.uniform(0, 1))
                timeout = base_timeout * (attempt + 1)
                tab = await self.browser.get(url)
                await asyncio.sleep(1)
                price_element = await tab.select('.pdp_bj', timeout=timeout)

                if price_element:
                    price_text = price_element.text
                    price_text = ''.join(c for c in price_text if c.isdigit() or c in '.,')
                    price_text = price_text.replace(',', '.')
                    if price_text:
                        price = float(price_text)
                        self._cache[url] = price
                        return price
                else:
                    logger.warning(f"Цена не найдена на странице {url}")

            except asyncio.TimeoutError:
                logger.warning(f"Таймаут при запросе {url} (попытка {attempt+1})")
            except Exception as e:
                if "Could not find node" in str(e) or "code: -32000" in str(e):
                    logger.warning(f"CDP-ошибка для {url}, повтор...")
                else:
                    logger.error(f"Ошибка парсинга {url}: {e}")

            await asyncio.sleep(1)

        logger.error(f"Не удалось получить цену после {MAX_RETRIES} попыток: {url}")
        self._cache[url] = None
        return None

    async def get_prices(self, urls: List[str]) -> List[Optional[float]]:
        results = []
        for url in urls:
            price = await self.fetch_price(url)
            results.append(price)
        return results


class SyncOzonParser:
    """Синхронная обёртка"""
    def __enter__(self):
        self.parser = OzonParser()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.parser.__aenter__())
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.loop.run_until_complete(self.parser.__aexit__(exc_type, exc_val, exc_tb))
        self.loop.close()

    def fetch_price(self, url: str) -> Optional[float]:
        return self.loop.run_until_complete(self.parser.fetch_price(url))

    def get_prices(self, urls: List[str]) -> List[Optional[float]]:
        return self.loop.run_until_complete(self.parser.get_prices(urls))