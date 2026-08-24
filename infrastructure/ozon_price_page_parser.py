"""
Парсер страницы управления ценами Ozon Seller (Selenium/UC).

Извлекает реальные цены покупателя (FBS/FBO) со страницы
https://seller.ozon.ru/app/prices/control
"""

import time
from dataclasses import dataclass

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from infrastructure.chrome_driver import ChromeDriverManager
from infrastructure.logger import logger


@dataclass
class PriceData:
    """Данные о цене товара со страницы управления ценами."""
    product_id: int
    real_price: int  # Реальная цена покупателя (показанная / 0.9)
    raw_price: int   # Цена как показана на странице (со скидкой 10%)


class OzonPricePageParser:
    """Парсер страницы управления ценами Ozon Seller (Selenium/UC)."""

    def __init__(self, driver_manager: ChromeDriverManager):
        self.driver_manager = driver_manager
        # Ensure driver is initialized (same pattern as OzonSellerClient)
        if not self.driver_manager.ensure_initialized():
            raise RuntimeError("Failed to initialize Chrome driver")
        self.driver = self.driver_manager.driver
        self.wait = self.driver_manager.wait
        assert self.driver is not None, "Driver must be initialized"
        assert self.wait is not None, "Wait must be initialized"

    def parse_all_prices(self) -> list[PriceData]:
        """
        Парсит цены со всех страниц пагинации.

        Returns:
            Список PriceData для всех товаров.
        """
        all_prices = []
        page_num = 1

        while True:
            logger.info(f"Парсинг страницы {page_num}...")
            prices = self._parse_current_page()
            all_prices.extend(prices)
            logger.info(f"Найдено цен на странице: {len(prices)}")

            if not self._go_to_next_page():
                logger.info("Следующая страница не найдена, завершаем парсинг")
                break

            page_num += 1
            time.sleep(2)  # Пауза для загрузки данных

        logger.info(f"Всего спарсено цен: {len(all_prices)}")
        return all_prices

    def _parse_current_page(self) -> list[PriceData]:
        """
        Парсит цены с текущей страницы.

        Returns:
            Список PriceData для товаров на текущей странице.
        """
        # Type narrowing for Pylance - driver and wait are guaranteed non-None after __init__
        assert self.driver is not None
        assert self.wait is not None
        # Ждём загрузку ячеек цен
        self.wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'td[id$="-pdpPrice"]'))
        )

        price_cells = self.driver.find_elements(
            By.CSS_SELECTOR, 'td[id$="-pdpPrice"]'
        )

        results = []
        for cell in price_cells:
            try:
                cell_id = cell.get_attribute('id')
                if not cell_id:
                    continue

                product_id = cell_id.replace('-pdpPrice', '')
                if not product_id.isdigit():
                    continue

                # Ищем спан с ценой
                price_span = cell.find_element(
                    By.CSS_SELECTOR, 'span.nd-ml8l.nd-at1'
                )
                price_text = price_span.text

                price_with_bank_discount = self._parse_price_text(price_text)
                if price_with_bank_discount <= 0:
                    continue

                # Реальная цена покупателя = показанная / 0.9 (скидка 10% за оплату через банки-партнёры)
                real_price = round(price_with_bank_discount / 0.9)

                results.append(PriceData(
                    product_id=int(product_id),
                    real_price=real_price,
                    raw_price=price_with_bank_discount
                ))

            except NoSuchElementException:
                continue
            except Exception as e:
                logger.warning(f"Ошибка парсинга ячейки цены: {e}")
                continue

        return results

    def _go_to_next_page(self) -> bool:
        """
        Переходит на следующую страницу пагинации.

        Returns:
            True если переход успешен, False если следующей страницы нет.
        """
        # Type narrowing for Pylance - driver and wait are guaranteed non-None after __init__
        assert self.driver is not None
        assert self.wait is not None
        try:
            # Ищем кнопку следующей страницы (не disabled, не selected)
            next_button = self.driver.find_element(
                By.CSS_SELECTOR,
                'ul.t0c137-a li button:not([disabled])[data-selected="false"]'
            )

            # Проверяем, что это не текущая страница
            if next_button.get_attribute("data-selected") == "true":
                return False

            next_button.click()

            # Ждём загрузки новой страницы
            self.wait.until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            time.sleep(2)  # Дополнительная пауза для загрузки данных
            return True

        except NoSuchElementException:
            return False
        except TimeoutException:
            logger.warning("Таймаут при ожидании загрузки следующей страницы")
            return False
        except Exception as e:
            logger.warning(f"Ошибка при переходе на следующую страницу: {e}")
            return False

    def _parse_price_text(self, text: str) -> int:
        """
        Парсит текст цены в число.

        Args:
            text: Текст цены (например, "1 436 ₽" или "1\u00a0436\u00a0₽")

        Returns:
            Цена в рублях как целое число.
        """
        # Удаляем неразрывные пробелы, обычные пробелы и символ рубля
        cleaned = text.replace('\u00a0', '').replace(' ', '').replace('₽', '').strip()
        try:
            return int(cleaned)
        except ValueError:
            logger.warning(f"Не удалось распарсить цену: '{text}'")
            return 0
