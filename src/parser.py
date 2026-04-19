import asyncio
import logging
from typing import List, Optional
import random

import nodriver as uc

from config.settings import PARSER_DELAY, PARSER_TIMEOUT, MAX_RETRIES

logger = logging.getLogger(__name__)


class OzonParser:
    """Асинхронный парсер цен Ozon на основе nodriver (преемник undetected_chromedriver)"""

    def __init__(self):
        self.browser: Optional[uc.Browser] = None

    async def __aenter__(self) -> 'OzonParser':
        # Запускаем браузер с маскировкой (headless можно включить при необходимости)
        # nodriver сам найдёт установленный Chrome
        self.browser = await uc.start(
            headless=False,  # Для отладки можно True
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            self.browser.stop()

    async def fetch_price(self, url: str) -> Optional[float]:
        """
        Асинхронно получает цену товара с указанной страницы Ozon.
        Возвращает float цену или None в случае ошибки.
        """
        if self.browser is None:
            raise RuntimeError("Браузер не инициализирован. Используйте 'async with OzonParser() as parser'")

        for attempt in range(MAX_RETRIES):
            try:
                # Задержка между попытками
                await asyncio.sleep(PARSER_DELAY + random.uniform(0, 1))

                # Открываем новую вкладку и переходим по URL
                tab = await self.browser.get(url)
                # Даём странице до конца отрисоваться
                await asyncio.sleep(1)
                price_element = await tab.select('.pdp_bj', timeout=PARSER_TIMEOUT)

                # Ждём появления элемента с ценой — по классу pdp_bj (специфичный класс Ozon для основной цены)
                # Метод select ждёт появления элемента с заданным CSS-селектором
                price_element = await tab.select('.pdp_bj', timeout=PARSER_TIMEOUT)

                if price_element:
                    price_text = price_element.text
                    # Очищаем от лишних символов
                    price_text = ''.join(c for c in price_text if c.isdigit() or c in '.,')
                    price_text = price_text.replace(',', '.')
                    if price_text:
                        return float(price_text)
                else:
                    logger.warning(f"Цена не найдена на странице {url}")

            except asyncio.TimeoutError:
                logger.warning(f"Таймаут при запросе {url} (попытка {attempt+1})")
            except Exception as e:
                logger.error(f"Ошибка парсинга {url}: {e}")

            # Пауза перед следующей попыткой
            await asyncio.sleep(1)

        logger.error(f"Не удалось получить цену после {MAX_RETRIES} попыток: {url}")
        return None

    async def get_prices(self, urls: List[str]) -> List[Optional[float]]:
        """
        Асинхронно получает цены для списка URL.
        Возвращает список в том же порядке.
        """
        results = []
        for url in urls:
            price = await self.fetch_price(url)
            results.append(price)
        return results


# Синхронная обёртка для использования в синхронном коде (если необходимо)
class SyncOzonParser:
    """Синхронная обёртка над OzonParser для простоты интеграции"""

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