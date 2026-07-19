import re
import time
import random
import logging
from typing import Optional, Any
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import undetected_chromedriver as uc

logger = logging.getLogger(__name__)


class OzonPriceParser:
    """Парсер цен на Ozon с использованием undetected-chromedriver."""

    driver: Optional[WebDriver]
    wait: Optional[WebDriverWait]

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.driver = None
        self.wait = None

    def _init_driver(self):
        """Инициализация драйвера с настройками для обхода блокировок."""
        options = uc.ChromeOptions()
        if self.headless:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)

        self.driver = uc.Chrome(options=options)
        self.driver.set_page_load_timeout(30)
        self.wait = WebDriverWait(self.driver, 10)

    def get_price(self, product_url: str) -> Optional[float]:
        """
        Получить цену товара по его URL.

        :param product_url: полный URL страницы товара на Ozon
        :return: цена в виде float или None, если не удалось извлечь
        """
        if self.driver is None:
            self._init_driver()

        # После _init_driver() гарантированы непустые driver и wait
        assert self.driver is not None and self.wait is not None, "Driver not initialized"

        try:
            logger.info(f"Загрузка страницы: {product_url}")
            self.driver.get(product_url)
            # Случайная задержка для имитации человека
            time.sleep(random.uniform(3, 5))

            # Ожидаем появления хотя бы одного элемента с ценой
            # Используем несколько селекторов
            price_selectors = [
                'span[data-testid="price-price"]',
                'span.tsHeadline600Large',
                'span.pdp_b0h.tsHeadline600Large',
                'span.pdp_b0h.tsHeadline500Medium',
                'div[data-testid="price"] span',
                'span[class*="tsHeadline"]',
            ]

            price_element = None
            for selector in price_selectors:
                try:
                    elements = self.wait.until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                    )
                    # Ищем элемент, содержащий ₽ и имеющий числовое значение
                    for el in elements:
                        text = el.text.strip()
                        if '₽' in text:
                            price_element = el
                            break
                    if price_element:
                        break
                except TimeoutException:
                    continue

            if not price_element:
                logger.warning(f"Цена не найдена на странице {product_url}")
                return None

            raw_price = price_element.text.strip()
            # Очищаем от всего, кроме цифр, точки и запятой
            cleaned = re.sub(r'[^\d.,]', '', raw_price)
            # Заменяем запятую на точку (если она используется как разделитель)
            cleaned = cleaned.replace(',', '.')
            # Удаляем возможные лишние точки (разделители тысяч) – оставляем только последнюю точку
            parts = cleaned.split('.')
            if len(parts) > 1:
                # Если есть несколько точек, скорее всего это разделители тысяч (123.456.789)
                # Удаляем все точки, кроме последней
                cleaned = ''.join(parts[:-1]) + '.' + parts[-1]
            price = float(cleaned)
            logger.info(f"Цена для {product_url}: {price}")
            return price

        except Exception as e:
            logger.error(f"Ошибка при парсинге {product_url}: {e}")
            return None

    def close(self):
        """Закрыть драйвер."""
        if self.driver:
            self.driver.quit()
            self.driver = None