"""
Клиент для работы с панелью управления продавца Ozon.
Поддерживает навигацию и скачивание шаблона цен.
"""

import time
from pathlib import Path

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from infrastructure.chrome_driver import ChromeDriverManager
from infrastructure.logger import logger


class OzonSellerClient:
    def __init__(self, headless: bool = False, download_dir: str | None = None):
        self.download_dir = download_dir
        self.driver_manager = ChromeDriverManager(
            headless=headless, use_profile=True, download_dir=download_dir
        )
        self.driver: WebDriver | None = None
        self.wait: WebDriverWait | None = None

    def _ensure_driver(self) -> bool:
        if not self.driver_manager.ensure_initialized():
            return False
        self.driver = self.driver_manager.driver
        self.wait = self.driver_manager.wait
        return True

    def navigate_to_prices(
        self, target_url: str = "https://seller.ozon.ru/app/prices/control"
    ) -> bool:
        """
        Переходит на страницу управления ценами.
        Предполагается, что пользователь уже авторизован в профиле.
        """
        if not self._ensure_driver():
            logger.error("Не удалось инициализировать драйвер")
            return False

        assert self.driver is not None and self.wait is not None

        try:
            logger.info(f"Переход на {target_url}")
            self.driver.get(target_url)
            # Ждём загрузки страницы (появление любого элемента)
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(3)  # даём время на динамическую загрузку
            logger.info("✅ Страница управления ценами загружена")
            return True
        except Exception as e:
            logger.error(f"Ошибка при переходе на страницу: {e}")
            return False

    def download_price_template(self, timeout: int = 60) -> Path | None:
        """
        Нажимает кнопку 'Скачать шаблон xlsx' и ожидает завершения загрузки.
        Возвращает путь к скачанному файлу или None при ошибке.
        """
        if not self._ensure_driver():
            logger.error("Драйвер не инициализирован")
            return None

        assert self.driver is not None and self.wait is not None

        # Проверяем, что мы на правильной странице
        current_url = self.driver.current_url
        if "prices/control" not in current_url:
            logger.warning("Текущий URL не является страницей управления ценами, пробуем перейти")
            if not self.navigate_to_prices():
                return None

        # Ждём, пока кнопка станет кликабельной
        try:
            button = self.wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(., 'Скачать шаблон xlsx')]")
                )
            )
        except TimeoutException:
            logger.error("Кнопка 'Скачать шаблон xlsx' не найдена")
            return None

        if not self.download_dir:
            logger.error("Папка загрузки не указана")
            return None

        download_path = Path(self.download_dir)
        download_path.mkdir(parents=True, exist_ok=True)

        # Запоминаем файлы до клика
        before_files = set(download_path.glob("*.xlsx"))

        logger.info("Нажимаем кнопку 'Скачать шаблон xlsx'...")
        button.click()

        # Ожидаем появления нового файла
        start_time = time.time()
        while time.time() - start_time < timeout:
            current_files = set(download_path.glob("*.xlsx"))
            new_files = current_files - before_files
            if new_files:
                # Берём самый свежий
                downloaded = max(new_files, key=lambda f: f.stat().st_mtime)
                if downloaded.suffix == ".xlsx" and not downloaded.name.endswith(".crdownload"):
                    logger.info(f"Файл скачан: {downloaded}")
                    return downloaded
            time.sleep(1)

        logger.error("Время ожидания загрузки истекло")
        return None

    def close(self):
        self.driver_manager.close()
