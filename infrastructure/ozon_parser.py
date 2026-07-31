import re
import time
import random
import logging
from typing import Optional
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import undetected_chromedriver as uc
from undetected_chromedriver.patcher import Patcher
from webdriver_manager.chrome import ChromeDriverManager

from config.settings import settings

logger = logging.getLogger(__name__)


def _patch_fetch_release_number() -> None:
    """
    Monkey-patch метода Patcher.fetch_release_number.

    Оригинальный метод UC обращается в интернет
    (https://googlechromelabs.github.io/chrome-for-testing) за JSON,
    даже если version_main указан явно. Это вызывало WinError 10054
    в закрытых средах.

    Патч заменяет сетевой запрос на чтение версии напрямую из
    локального бинарника chromedriver через parse_exe_version().
    """
    def _patched(self: Patcher):
        version = self.parse_exe_version()
        if version:
            logger.debug(f"Версия драйвера прочитана из бинарника: {version}")
            return version
        # Фоллбэк: передаём мажорную версию.
        # UC ожидает LooseVersion (импортируется самим UC из distutils.version
        # на верхнем уровне patcher.py). Переиспользуем его оттуда, чтобы не
        # тянуть distutils напрямую (устаревший модуль в Python 3.12+) и
        # не получать IDE-warnings о неразрешённом импорте.
        from undetected_chromedriver.patcher import LooseVersion  # type: ignore[attr-defined]
        return LooseVersion(str(self.version_main or settings.CHROME_VERSION_MAIN))

    Patcher.fetch_release_number = _patched


# Применяем патч один раз при импорте модуля
_patch_fetch_release_number()


class OzonPriceParser:
    """Парсер цен на Ozon с использованием undetected-chromedriver."""

    driver: Optional[WebDriver]
    wait: Optional[WebDriverWait]

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.driver = None
        self.wait = None

    def _build_options(self) -> uc.ChromeOptions:
        options = uc.ChromeOptions()
        if self.headless:
            options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-features=IsolateOrigins,site-per-process')
        options.add_argument('--disable-site-isolation-trials')
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-features=TranslateUI')
        options.add_argument('--disable-features=OptimizationGuideModelDownloading')
        options.add_argument('--disable-features=OptimizationHints')
        options.add_argument('--disable-features=OptimizationHintsFetching')
        options.add_argument('--disable-features=OptimizationHintsPush')
        # Профиль Chrome из настроек (ENV: CHROME_PROFILE_PATH)
        options.add_argument(f'--user-data-dir={settings.CHROME_PROFILE_PATH}')
        return options

    def _build_selenium_options(self):
        """Создаёт стандартные selenium ChromeOptions для fallback-режима."""
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        options = ChromeOptions()
        if self.headless:
            options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-blink-features=AutomationControlled')
        return options

    def _init_driver(self):
        """Инициализация драйвера с настройками для обхода блокировок.

        Стратегия:
        1. Находим драйвер через webdriver-manager (локальный кэш) —
           это предотвращает попытки UC лезть в github.io за апдейтом.
        2. Создаём свежий uc.ChromeOptions (UC не переиспользуует options).
        3. Запускаем uc.Chrome с service=... и options=...
        4. Fallback: если что-то упало, пересоздаём options (UC consumирует
           объект при попытке) и запускаем чистый UC без webdriver-manager.
        """
        driver_path = None
        try:
            driver_path = ChromeDriverManager().install()
        except Exception as e:
            logger.warning(f"webdriver-manager не смог получить драйвер ({e}), "
                           "будет использован дефолтный механизм UC")

        # Попытка 1: UC с driver_executable_path от webdriver-manager
        if driver_path:
            try:
                service = ChromeService(executable_path=driver_path)
                self.driver = uc.Chrome(
                    service=service,
                    options=self._build_options(),
                    version_main=settings.CHROME_VERSION_MAIN,
                    driver_executable_path=driver_path,
                )
                self._configure_driver()
                return
            except Exception as e:
                logger.warning(
                    f"UC не смог запуститься с webdriver-manager ({e}), "
                    "переключаемся на обычный Selenium"
                )
                self._safe_quit()

        # Попытка 2 (fallback): обычный Selenium Chrome без UC
        try:
            service = ChromeService(executable_path=driver_path) if driver_path else ChromeService()
            from selenium import webdriver
            self.driver = webdriver.Chrome(service=service, options=self._build_selenium_options())
            self._configure_driver()
        except Exception as e:
            logger.error(f"Не удалось инициализировать Chrome драйвер: {e}")
            raise

    def _configure_driver(self) -> None:
        """Общие настройки драйвера после успешного создания."""
        assert self.driver is not None, "Driver not initialized in _configure_driver"
        self.driver.set_page_load_timeout(30)
        self.wait = WebDriverWait(self.driver, 15)

    def _safe_quit(self) -> None:
        """Безопасное закрытие драйвера без выброса исключений."""
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:
                pass
        self.driver = None
        self.wait = None

    def restart(self) -> None:
        """Пересоздать драйвер с нуля (закрыть + инициализировать заново).

        Полезен, когда текущий драйвер завис или оказался в невалидном
        состоянии: обычный get_price уже не сможет загрузить страницу,
        нужно полностью перезапустить браузер.
        """
        logger.info("Перезапуск драйвера (restart)...")
        self._safe_quit()
        self._init_driver()

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
            time.sleep(random.uniform(5, 10))

            # Проверка, что товар не закончился
            try:
                out_of_stock = self.driver.find_element(By.XPATH, "//h2[contains(text(), 'Этот товар закончился')]")
                logger.info(f"Товар закончился: {product_url}")
                return -1.0
            except NoSuchElementException:
                pass

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
        self._safe_quit()
