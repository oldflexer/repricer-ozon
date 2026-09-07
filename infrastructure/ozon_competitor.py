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
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

from core.metrics import (
    record_parser_captcha_detected,
    record_parser_block_detected,
    record_parser_graceful_degradation,
    record_parser_price_fetch,
    record_parser_price_fetch_error,
    record_parser_price_fetch_result,
    record_parser_retry,
)
from core.protocols.parser import OzonPriceParserProtocol
from infrastructure.chrome_driver import ChromeDriverManager
from infrastructure.logger import logger


class OzonPriceParser(OzonPriceParserProtocol):
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
        self.driver: WebDriver | None = None
        self.wait: WebDriverWait | None = None

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

    def _detect_captcha_or_block(self) -> Optional[str]:
        """
        Проверяет страницу на наличие CAPTCHA или блокировки.
        
        Returns:
            'captcha' если обнаружена CAPTCHA,
            'block' если обнаружен блок/бан,
            None если ничего не найдено.
        """
        if not self.driver:
            return None
            
        # Селекторы для CAPTCHA
        captcha_selectors = [
            "//div[contains(@class, 'captcha')]",
            "//iframe[contains(@src, 'captcha')]",
            "//div[contains(text(), 'CAPTCHA')]",
            "//div[contains(text(), 'капча')]",
            "//div[contains(text(), 'проверка')]",
            "//img[contains(@src, 'captcha')]",
        ]
        
        # Селекторы для блокировки
        block_selectors = [
            "//div[contains(text(), 'Доступ ограничен')]",
            "//div[contains(text(), 'доступ запрещен')]",
            "//div[contains(text(), 'Too Many Requests')]",
            "//div[contains(text(), '429')]",
            "//div[contains(text(), 'IP заблокирован')]",
            "//div[contains(text(), 'доступ временно ограничен')]",
        ]
        
        for selector in captcha_selectors:
            try:
                if self.driver.find_elements(By.XPATH, selector):
                    return "captcha"
            except Exception:
                pass
                
        for selector in block_selectors:
            try:
                if self.driver.find_elements(By.XPATH, selector):
                    return "block"
            except Exception:
                pass
                
        return None

    def get_price(self, product_url: str) -> float | None:
        """
        Получает цену товара по его URL.

        Args:
            product_url: Полный URL страницы товара на Ozon.

        Returns:
            Цена в виде float, -1.0 если товар закончился,
            или None при ошибке.
        """
        start_time = time.time()
        
        if not self._ensure_driver():
            record_parser_price_fetch_result("error")
            record_parser_price_fetch_error("driver_init_failed")
            return None

        assert self.driver is not None and self.wait is not None

        try:
            logger.info(f"Загрузка страницы: {product_url}")
            self.driver.get(product_url)
            time.sleep(random.uniform(5, 10))

            # Проверка на CAPTCHA или блок
            block_type = self._detect_captcha_or_block()
            if block_type == "captcha":
                logger.warning(f"CAPTCHA обнаружена на странице: {product_url}")
                record_parser_captcha_detected()
                record_parser_price_fetch_result("captcha")
                record_parser_price_fetch_error("captcha")
                record_parser_graceful_degradation("captcha")
                return None
            elif block_type == "block":
                logger.warning(f"Блокировка обнаружена на странице: {product_url}")
                record_parser_block_detected()
                record_parser_price_fetch_result("block")
                record_parser_price_fetch_error("block")
                record_parser_graceful_degradation("block")
                return None

            # Проверка, что товар не закончился
            try:
                self.driver.find_element(
                    By.XPATH, "//h2[contains(text(), 'Этот товар закончился')]"
                )
                logger.info(f"Товар закончился: {product_url}")
                record_parser_price_fetch_result("out_of_stock")
                return -1.0
            except NoSuchElementException:
                pass

            # Поиск элемента с ценой по нескольким селекторам
            price_selectors = [
                'span[data-testid="price-price"]',
                "span.tsHeadline600Large",
                "span.pdp_b0h.tsHeadline600Large",
                "span.pdp_b0h.tsHeadline500Medium",
                'div[data-testid="price"] span',
                'span[class*="tsHeadline"]',
            ]

            price_element = None
            for selector in price_selectors:
                try:
                    elements = self.wait.until(
                        ec.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
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
                record_parser_price_fetch_result("error")
                record_parser_price_fetch_error("price_not_found")
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
            record_parser_price_fetch_result("success")
            return price

        except Exception as e:
            logger.error(f"Ошибка при парсинге {product_url}: {e}")
            record_parser_price_fetch_result("error")
            record_parser_price_fetch_error(type(e).__name__)
            return None
        finally:
            duration = time.time() - start_time
            record_parser_price_fetch(duration)

    def close(self) -> None:
        """Закрывает драйвер и освобождает ресурсы."""
        self.driver_manager.close()
        self.driver = None
        self.wait = None
