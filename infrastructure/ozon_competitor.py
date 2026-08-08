"""
Парсер цен конкурентов с Ozon с использованием Selenium.
Использует ChromeDriverManager для управления браузером.
"""

import random
import re
import time
from typing import Optional

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from config.settings import settings
from infrastructure.chrome_driver import ChromeDriverManager
from infrastructure.logger import logger


class OzonPriceParser:
    """
    Парсер цен конкурентов на Ozon.

    Использует ChromeDriverManager с профилем Chrome для
    авторизации и обхода блокировок.
    """

    def __init__(self, headless: bool = False) -> None:
        """
        Args:
            headless: Запускать браузер в headless-режиме (по умолчанию False).
        """
        self.driver_manager = ChromeDriverManager(headless=headless, use_profile=True)
        self.driver: Optional[WebDriver] = None
        self.wait: Optional[WebDriverWait] = None

    def _ensure_driver(self) -> bool:
        """Гарантирует, что драйвер инициализирован."""
        if self.driver is None:
            if not self.driver_manager.init_driver():
                logger.error("Не удалось инициализировать драйвер")
                return False
            self.driver = self.driver_manager.driver
            self.wait = self.driver_manager.wait
        return True

    def restart(self) -> None:
        """Перезапускает драйвер с нуля."""
        logger.info("Перезапуск драйвера...")
        self.driver_manager.restart()
        self.driver = self.driver_manager.driver
        self.wait = self.driver_manager.wait

    def get_price(self, product_url: str) -> Optional[float]:
        """
        Получает цену товара по его URL.

        Args:
            product_url: Полный URL страницы товара на Ozon.

        Returns:
            Цена в виде float, -1.0 если товар закончился,
            или None при ошибке.
        """
        if not self._ensure_driver():
            return None

        assert self.driver is not None and self.wait is not None

        try:
            logger.info(f"Загрузка страницы: {product_url}")
            self.driver.get(product_url)
            time.sleep(random.uniform(5, 10))

            # Проверка, что товар не закончился
            try:
                out_of_stock = self.driver.find_element(
                    By.XPATH, "//h2[contains(text(), 'Этот товар закончился')]"
                )
                logger.info(f"Товар закончился: {product_url}")
                return -1.0
            except NoSuchElementException:
                pass

            # Поиск элемента с ценой по нескольким селекторам
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
                    for el in elements:
                        text = el.text.strip()
                        if "₽" in text:
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
            # Очистка от всего, кроме цифр, точки и запятой
            cleaned = re.sub(r"[^\d.,]", "", raw_price)
            cleaned = cleaned.replace(",", ".")  # запятая → точка
            # Удаляем точки-разделители тысяч (оставляем только последнюю точку)
            parts = cleaned.split(".")
            if len(parts) > 1:
                cleaned = "".join(parts[:-1]) + "." + parts[-1]

            price = float(cleaned)
            logger.info(f"Цена для {product_url}: {price}")
            return price

        except Exception as e:
            logger.error(f"Ошибка при парсинге {product_url}: {e}")
            return None

    def close(self) -> None:
        """Закрывает драйвер и освобождает ресурсы."""
        self.driver_manager.close()
        self.driver = None
        self.wait = None