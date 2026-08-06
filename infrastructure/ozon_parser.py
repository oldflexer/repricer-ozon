import sys
from types import ModuleType

# --- HACK: эмуляция distutils.version для Python 3.12+ ---
# undetected-chromedriver импортирует distutils.version.LooseVersion,
# но distutils удалён в Python 3.12. Подменяем модуль до импорта uc.

class _LooseVersion:
    def __init__(self, vstring):
        self.vstring = str(vstring)
    def __repr__(self):
        return f"LooseVersion('{self.vstring}')"
    def __eq__(self, other):
        return self.vstring == str(other)
    def __lt__(self, other):
        return self.vstring < str(other)
    def __le__(self, other):
        return self.vstring <= str(other)
    def __gt__(self, other):
        return self.vstring > str(other)
    def __ge__(self, other):
        return self.vstring >= str(other)

class _DistutilsVersionModule(ModuleType):
    def __getattr__(self, name):
        if name == 'LooseVersion':
            return _LooseVersion
        raise AttributeError(name)

# Создаём и регистрируем модуль distutils.version
if 'distutils.version' not in sys.modules:
    sys.modules['distutils.version'] = _DistutilsVersionModule('distutils.version')
# Также создаём родительский модуль distutils, если его нет
if 'distutils' not in sys.modules:
    sys.modules['distutils'] = ModuleType('distutils')

# --- Остальные импорты ---
"""
Парсер цен конкурентов с Ozon с использованием Selenium.

Использует undetected-chromedriver для обхода блокировок,
с fallback на обычный Selenium при ошибках.
"""

import logging
import random
import re
import time
from typing import Optional

import undetected_chromedriver as uc
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from undetected_chromedriver.patcher import Patcher
from webdriver_manager.chrome import ChromeDriverManager

from config.settings import settings

logger = logging.getLogger(__name__)

# Мажорная версия Chrome, установленного на машине.
CHROME_VERSION_MAIN = 150

def _patch_fetch_release_number() -> None:
    """
    Monkey-patch для метода Patcher.fetch_release_number.

    Оригинальный метод UC обращается в интернет за JSON-версией,
    что может вызывать ошибки в закрытых средах. Данный патч
    заменяет сетевой запрос на чтение версии из локального
    бинарника chromedriver или использует settings.CHROME_VERSION_MAIN.
    """

    def _patched(self: Patcher):
        version = self.parse_exe_version()
        if version:
            logger.debug(f"Версия драйвера прочитана из бинарника: {version}")
            return version
        # Фоллбэк: мажорная версия из настроек
        from undetected_chromedriver.patcher import LooseVersion  # type: ignore[attr-defined]
        return LooseVersion(str(self.version_main or settings.CHROME_VERSION_MAIN))

    Patcher.fetch_release_number = _patched


# Применяем патч один раз при импорте
_patch_fetch_release_number()


class OzonPriceParser:
    """
    Парсер цен конкурентов на Ozon.

    Использует undetected-chromedriver с профилем Chrome для
    авторизации и обхода блокировок.
    """

    driver: Optional[WebDriver]
    wait: Optional[WebDriverWait]

    def __init__(self, headless: bool = False) -> None:
        """
        Инициализирует парсер.

        Args:
            headless: Запускать ли браузер в headless-режиме (по умолчанию False).
        """
        self.headless = headless
        self.driver = None
        self.wait = None

    # ------------------------------------------------------------------
    # Настройка драйвера
    # ------------------------------------------------------------------

    def _build_options(self) -> uc.ChromeOptions:
        """Создаёт опции для undetected-chromedriver."""
        options = uc.ChromeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-features=IsolateOrigins,site-per-process")
        options.add_argument("--disable-site-isolation-trials")
        options.add_argument("--disable-web-security")
        options.add_argument("--disable-features=TranslateUI")
        options.add_argument("--disable-features=OptimizationGuideModelDownloading")
        options.add_argument("--disable-features=OptimizationHints")
        options.add_argument("--disable-features=OptimizationHintsFetching")
        options.add_argument("--disable-features=OptimizationHintsPush")
        options.add_argument(f"--user-data-dir={settings.CHROME_PROFILE_PATH}")
        return options

    def _build_selenium_options(self):
        """Создаёт стандартные опции Selenium для fallback-режима."""
        from selenium.webdriver.chrome.options import Options as ChromeOptions

        options = ChromeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-blink-features=AutomationControlled")
        return options

    def _init_driver(self) -> None:
        """
        Инициализирует драйвер.

        Стратегия:
            1. Попытка через undetected-chromedriver с webdriver-manager.
            2. Fallback на обычный Selenium.
        """
        driver_path = None
        try:
            driver_path = ChromeDriverManager().install()
        except Exception as e:
            logger.warning(
                f"webdriver-manager не смог получить драйвер ({e}), "
                "будет использован дефолтный механизм UC"
            )

        # Попытка 1: UC с драйвером от webdriver-manager
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

        # Попытка 2: обычный Selenium
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
        """Безопасно закрывает драйвер без выброса исключений."""
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:
                pass
        self.driver = None
        self.wait = None

    def restart(self) -> None:
        """
        Пересоздаёт драйвер с нуля.

        Полезен при зависании или невалидном состоянии.
        """
        logger.info("Перезапуск драйвера (restart)...")
        self._safe_quit()
        self._init_driver()

    # ------------------------------------------------------------------
    # Основной метод парсинга
    # ------------------------------------------------------------------

    def get_price(self, product_url: str) -> Optional[float]:
        """
        Получает цену товара по его URL.

        Args:
            product_url: Полный URL страницы товара на Ozon.

        Returns:
            Цена в виде float, -1.0 если товар закончился,
            или None при ошибке.
        """
        if self.driver is None:
            self._init_driver()

        assert self.driver is not None and self.wait is not None, "Driver not initialized"

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
        """Закрывает драйвер."""
        self._safe_quit()