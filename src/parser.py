import asyncio
import logging
from typing import List, Optional, Dict, Tuple
import random

import nodriver as uc

from config.settings import PARSER_DELAY, PARSER_TIMEOUT, MAX_RETRIES, HEADLESS, USER_AGENT

logger = logging.getLogger(__name__)


class OzonParser:
    """Асинхронный парсер цен Ozon (браузер запускается отдельно для каждого запроса)"""

    def __init__(self):
        self._cache: Dict[str, Tuple[Optional[float], Optional[str], Optional[str]]] = {}
        self._shared_browser_args = [
            '--window-size=1920,1080',
            '--disable-blink-features=AutomationControlled',
        ]

    async def __aenter__(self) -> 'OzonParser':
        # Браузер больше не создаётся при входе в контекст
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Нечего останавливать
        pass

    async def _create_browser(self) -> uc.Browser:
        """Создаёт новый браузер с нужными параметрами."""
        return await uc.start(
            headless=HEADLESS,
            browser_args=self._shared_browser_args
        )

    async def fetch_price_and_info(self, url: str) -> Tuple[Optional[float], Optional[str], Optional[str]]:
        """Возвращает (цена, название товара, магазин)."""
        if url in self._cache:
            logger.debug(f"Использовано кэшированное значение для {url}")
            return self._cache[url]

        base_timeout = PARSER_TIMEOUT
        for attempt in range(MAX_RETRIES):
            browser = None
            tab = None
            try:
                await asyncio.sleep(PARSER_DELAY + random.uniform(0, 1))
                timeout = base_timeout * (attempt + 1)

                # Запускаем свежий браузер
                browser = await self._create_browser()
                tab = await browser.get(url)
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
            finally:
                # Закрываем браузер в любом случае
                if browser:
                    try:
                        browser.stop()
                    except Exception as stop_e:
                        logger.debug(f"Ошибка при остановке браузера: {stop_e}")

            await asyncio.sleep(1)

        logger.error(f"Не удалось получить данные после {MAX_RETRIES} попыток: {url}")
        self._cache[url] = (None, None, None)
        return None, None, None

    async def fetch_price_by_sku(self, sku: str) -> Optional[float]:
        url = f"https://www.ozon.ru/product/{sku}"
        price, _, _ = await self.fetch_price_and_info(url)
        return price

    async def get_prices(self, urls: List[str]) -> List[Tuple[Optional[float], Optional[str], Optional[str]]]:
        results = []
        for url in urls:
            res = await self.fetch_price_and_info(url)
            results.append(res)
        return results