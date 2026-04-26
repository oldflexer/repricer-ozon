import asyncio
import logging
import random
from typing import List, Optional, Dict, Tuple

import zendriver as zd

from config.settings import PARSER_DELAY, PARSER_TIMEOUT, MAX_RETRIES, HEADLESS, USER_AGENT

logger = logging.getLogger(__name__)


class OzonParser:
    """Асинхронный парсер цен Ozon на базе zendriver (форк nodriver)"""

    PRICE_SELECTORS = [
        '.pdp_bj',
        '[data-widget="webPrice"] span',
        'span[class*="l5_"]',
    ]

    def __init__(self):
        self.browser: Optional[zd.Browser] = None
        self.main_tab: Optional[zd.Tab] = None
        self._cache: Dict[str, Tuple[Optional[float], Optional[str], Optional[str]]] = {}
        self._shared_browser_args = [
            '--window-size=1920,1080',
            '--disable-blink-features=AutomationControlled',
            '--disable-gpu',
        ]
        if USER_AGENT:
            self._shared_browser_args.append(f'--user-agent={USER_AGENT}')

    async def __aenter__(self) -> 'OzonParser':

        # Собираем конфигурацию
        config = zd.Config(
            headless=HEADLESS,
            browser_args=self._shared_browser_args,
            user_agent=USER_AGENT if USER_AGENT else None,
        )

        self.browser = await zd.start(config=config)

        try:
            logger.debug("Разогрев сессии: открываем ya.ru")
            self.main_tab = await self.browser.get('https://ya.ru')
            await asyncio.sleep(3)

            logger.debug("Разогрев сессии: переходим на ozon.ru")
            self.main_tab = await self.browser.get('https://www.ozon.ru')
            await asyncio.sleep(3)
            
            logger.debug("Сессия разогрета, вкладка Ozon оставлена открытой")
        except Exception as e:
            logger.warning(f"Не удалось разогреть сессию: {e}")
            self.main_tab = await self.browser.get('about:blank')
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            await self.browser.stop()

    def _ensure_browser(self) -> zd.Browser:
        if self.browser is None:
            raise RuntimeError(
                "Браузер не инициализирован. Используйте 'async with OzonParser() as parser'"
            )
        return self.browser

    async def _safe_select(self, tab: zd.Tab, selector: str, timeout: float = 5) -> Optional[zd.Element]:
        try:
            elem = await tab.select(selector, timeout=timeout)
            return elem
        except asyncio.TimeoutError:
            logger.debug(f"Элемент '{selector}' не найден (timeout)")
            return None
        except Exception as e:
            if "Could not find node" in str(e) or "code: -32000" in str(e):
                logger.debug(f"CDP-ошибка при поиске '{selector}': {e}")
            else:
                logger.warning(f"Неизвестная ошибка при поиске '{selector}': {e}")
            return None

    async def fetch_price_and_info(self, url: str) -> Tuple[Optional[float], Optional[str], Optional[str]]:
        # Гарантируем, что browser не None, присваивая локальной переменной
        browser = self._ensure_browser()

        if url in self._cache:
            logger.debug(f"Использовано кэшированное значение для {url}")
            return self._cache[url]

        # Если вкладка ещё не создана, создаём её
        if self.main_tab is None:
            self.main_tab = await browser.get('about:blank')

        base_timeout = PARSER_TIMEOUT
        for attempt in range(MAX_RETRIES):
            try:
                await asyncio.sleep(PARSER_DELAY + random.uniform(0, 1))
                timeout = base_timeout * (attempt + 1)

                # В zendriver навигация идёт через browser.get()
                self.main_tab = await browser.get(url)
                await asyncio.sleep(1)

                # Эмуляция человеческого поведения: плавный скролл
                await self.main_tab.evaluate("""
                    window.scrollTo({ top: document.body.scrollHeight * 0.3, behavior: 'smooth' });
                """)
                await asyncio.sleep(0.8)
                await self.main_tab.evaluate("""
                    window.scrollTo({ top: document.body.scrollHeight * 0.6, behavior: 'smooth' });
                """)
                await asyncio.sleep(0.8)
                # Небольшое случайное движение мыши
                await self.main_tab.evaluate("""
                    document.dispatchEvent(new MouseEvent('mousemove', {
                        clientX: Math.random() * window.innerWidth,
                        clientY: Math.random() * window.innerHeight,
                        bubbles: true
                    }));
                """)
                await asyncio.sleep(0.5)

                # Проверка на несуществующую страницу
                page_text = await self.main_tab.evaluate('document.body.innerText')
                if page_text and "Такой страницы не существует" in page_text:
                    logger.warning(f"Страница не существует (заглушка) для {url}")
                    self._cache[url] = (None, None, None)
                    return None, None, None

                # Проверка на капчу
                captcha = await self._safe_select(
                    self.main_tab, 'form[action*="checkcaptcha"]', timeout=2
                )
                if captcha:
                    logger.warning("Обнаружена капча, нужна ручная разгадка")
                    self._cache[url] = (None, None, None)
                    return None, None, None

                # Поиск цены по нескольким селекторам
                price = None
                for selector in self.PRICE_SELECTORS:
                    price_elem = await self._safe_select(self.main_tab, selector, timeout=timeout)
                    if price_elem:
                        price_text = price_elem.text
                        price_text = ''.join(c for c in price_text if c.isdigit() or c in '.,')
                        price_text = price_text.replace(',', '.')
                        if price_text:
                            try:
                                price = float(price_text)
                                logger.debug(f"Цена найдена по селектору '{selector}': {price}")
                                break
                            except ValueError:
                                logger.debug(f"Не удалось преобразовать цену: '{price_text}'")
                if price is None:
                    logger.debug("Цена не найдена ни по одному селектору")

                # Название товара
                title_elem = await self._safe_select(self.main_tab, 'h1', timeout=5)
                product_name = title_elem.text.strip() if title_elem else None

                # Магазин (подбираем по частому классу)
                shop_elem = await self._safe_select(
                    self.main_tab, 'span[class*="b35_3_30-b7"]', timeout=5
                )
                shop_name = shop_elem.text.strip() if shop_elem else None

                self._cache[url] = (price, product_name, shop_name)
                return price, product_name, shop_name

            except asyncio.TimeoutError:
                logger.warning(f"Таймаут при запросе {url} (попытка {attempt+1})")
            except Exception as e:
                if "coroutine raised StopIteration" in str(e):
                    logger.warning(f"StopIteration в корутине для {url}, попытка {attempt+1}")
                elif "Could not find node" in str(e) or "code: -32000" in str(e):
                    logger.warning(f"CDP-ошибка для {url}, повтор...")
                else:
                    logger.error(f"Ошибка парсинга {url}: {e}")

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