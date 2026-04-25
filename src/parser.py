import asyncio
import logging
from typing import List, Optional, Dict, Tuple
import random

import nodriver as uc

from config.settings import PARSER_DELAY, PARSER_TIMEOUT, MAX_RETRIES, HEADLESS, USER_AGENT

logger = logging.getLogger(__name__)


class OzonParser:
    """Асинхронный парсер цен Ozon с извлечением названия товара и продавца"""

    def __init__(self):
        self.browser: Optional[uc.Browser] = None
        self._cache: Dict[str, Tuple[Optional[float], Optional[str], Optional[str]]] = {}

    async def __aenter__(self) -> 'OzonParser':
        browser_args = [
            '--window-size=1920,1080',
            '--disable-blink-features=AutomationControlled',
            f'--user-agent={USER_AGENT}',
            '--lang=ru-RU',
        ]

        self.browser = await uc.start(
            headless=HEADLESS,
            browser_args=browser_args
        )

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            self.browser.stop()

    async def fetch_price_and_info(self, url: str) -> Tuple[Optional[float], Optional[str], Optional[str]]:
        """Возвращает (цена, название товара, магазин)."""
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

                # Проверка на заглушку "Такой страницы не существует"
                page_text = await tab.evaluate('document.body.innerText')
                if page_text and "Такой страницы не существует" in page_text:
                    logger.warning(f"Страница не существует (заглушка) для {url}")
                    self._cache[url] = (None, None, None)
                    return None, None, None

        		# Цена
                price_elem = await tab.select('.pdp_bj', timeout=timeout)
                price = None
                if price_elem:
                    price_text = price_elem.text
                    price_text = ''.join(c for c in price_text if c.isdigit() or c in '.,')
                    price_text = price_text.replace(',', '.')
                    if price_text:
                        price = float(price_text)

                # Название товара
                title_elem = await tab.select('h1', timeout=5)
                product_name = title_elem.text.strip() if title_elem else None

                # Магазин (продавец)
                shop_elem = await tab.select('span[class*="b35_3_30-b7"]', timeout=5)
                shop_name = shop_elem.text.strip() if shop_elem else None

                self._cache[url] = (price, product_name, shop_name)
                return price, product_name, shop_name

            except asyncio.TimeoutError:
                logger.warning(f"Таймаут при запросе {url} (попытка {attempt+1})")
            except Exception as e:
                if "Could not find node" in str(e) or "code: -32000" in str(e):
                    logger.warning(f"CDP-ошибка для {url}, повтор...")
                else:
                    logger.error(f"Ошибка парсинга {url}: {e}")

            await asyncio.sleep(1)

        logger.error(f"Не удалось получить данные после {MAX_RETRIES} попыток: {url}")
        self._cache[url] = (None, None, None)
        return None, None, None

    async def fetch_price_by_sku(self, sku: str) -> Optional[float]:
        """Получает цену товара по прямой ссылке https://www.ozon.ru/product/{sku}"""
        url = f"https://www.ozon.ru/product/{sku}"
        price, _, _ = await self.fetch_price_and_info(url)
        return price

    async def get_prices(self, urls: List[str]) -> List[Tuple[Optional[float], Optional[str], Optional[str]]]:
        results = []
        for url in urls:
            res = await self.fetch_price_and_info(url)
            results.append(res)
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
        price, _, _ = self.loop.run_until_complete(self.parser.fetch_price_and_info(url))
        return price

    def get_prices(self, urls: List[str]) -> List[Optional[float]]:
        results = self.loop.run_until_complete(self.parser.get_prices(urls))
        return [r[0] for r in results]
