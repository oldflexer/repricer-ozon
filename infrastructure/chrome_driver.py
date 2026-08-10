"""
Унифицированная инициализация Chrome-драйвера (обычный Selenium с профилем).
Поддерживает загрузку файлов в указанную папку.
"""

import os
import sys
from pathlib import Path
from types import ModuleType

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait

from config.settings import settings
from infrastructure.logger import logger


# --- Патчи для Python 3.12+ ---
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
        if name == "LooseVersion":
            return _LooseVersion
        raise AttributeError(name)


if "distutils.version" not in sys.modules:
    sys.modules["distutils.version"] = _DistutilsVersionModule("distutils.version")
if "distutils" not in sys.modules:
    sys.modules["distutils"] = ModuleType("distutils")


class ChromeDriverManager:
    def __init__(
        self, headless: bool = False, use_profile: bool = True, download_dir: str | None = None
    ):
        self.headless = headless
        self.use_profile = use_profile
        self.download_dir = download_dir
        self.driver: WebDriver | None = None
        self.wait: WebDriverWait | None = None

    def _get_profile_path(self) -> str | None:
        if not self.use_profile:
            return None
        raw_path = getattr(settings, "CHROME_PROFILE_PATH", None)
        if not raw_path:
            logger.warning("CHROME_PROFILE_PATH не задан")
            return None
        expanded = os.path.expandvars(raw_path)
        abs_path = Path(expanded).expanduser().resolve()
        normalized = str(abs_path).replace("\\", "/")
        logger.info(f"Нормализованный путь к профилю: {normalized}")
        if not abs_path.exists():
            logger.warning(f"Папка профиля не существует: {normalized} (будет создана)")
        return normalized

    def _clean_profile_locks(self, profile_path: str) -> None:
        if not profile_path:
            return
        for fname in ["SingletonLock", "SingletonSocket", "SingletonCookie", "DevToolsActivePort"]:
            fpath = Path(profile_path) / fname
            if fpath.exists():
                try:
                    fpath.unlink()
                    logger.debug(f"Удалён файл: {fpath}")
                except Exception:
                    pass

    def _build_options(self):
        from selenium.webdriver.chrome.options import Options as ChromeOptions

        options = ChromeOptions()
        if self.headless:
            options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--remote-debugging-port=0")
        options.add_argument("--no-first-run")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-sync")

        if self.download_dir:
            download_path = Path(self.download_dir).resolve()
            download_path.mkdir(parents=True, exist_ok=True)
            prefs = {
                "download.default_directory": str(download_path),
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
            }
            options.add_experimental_option("prefs", prefs)
            logger.info(f"Загрузка файлов будет в: {download_path}")

        profile_path = self._get_profile_path()
        if profile_path:
            if " " in profile_path:
                options.add_argument(f'--user-data-dir="{profile_path}"')
            else:
                options.add_argument(f"--user-data-dir={profile_path}")
            self._clean_profile_locks(profile_path)
        return options

    def _build_selenium_options(self):
        from selenium.webdriver.chrome.options import Options as ChromeOptions

        options = ChromeOptions()
        if self.headless:
            options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--remote-debugging-port=0")
        options.add_argument("--no-first-run")
        options.add_argument("--disable-default-apps")

        if self.download_dir:
            download_path = Path(self.download_dir).resolve()
            download_path.mkdir(parents=True, exist_ok=True)
            prefs = {
                "download.default_directory": str(download_path),
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
            }
            options.add_experimental_option("prefs", prefs)

        profile_path = self._get_profile_path()
        if profile_path:
            if " " in profile_path:
                options.add_argument(f'--user-data-dir="{profile_path}"')
            else:
                options.add_argument(f"--user-data-dir={profile_path}")
            self._clean_profile_locks(profile_path)
        return options

    def init_driver(self) -> bool:
        driver_path = None
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service

            try:
                from webdriver_manager.chrome import ChromeDriverManager

                driver_path = ChromeDriverManager().install()
            except Exception as e:
                logger.warning(f"webdriver-manager не смог получить драйвер: {e}")

            options = self._build_options()
            if driver_path:
                service = Service(executable_path=driver_path)
                self.driver = webdriver.Chrome(service=service, options=options)
            else:
                self.driver = webdriver.Chrome(options=options)

            self._configure_driver()
            logger.info("✅ Драйвер успешно инициализирован")
            return True
        except Exception as e:
            logger.error(f"Ошибка инициализации драйвера: {e}")
            try:
                from selenium import webdriver
                from selenium.webdriver.chrome.service import Service

                fallback_options = self._build_selenium_options()
                if driver_path:
                    service = Service(executable_path=driver_path)
                    self.driver = webdriver.Chrome(service=service, options=fallback_options)
                else:
                    self.driver = webdriver.Chrome(options=fallback_options)
                self._configure_driver()
                logger.info("Драйвер инициализирован через fallback")
                return True
            except Exception as e2:
                logger.error(f"Ошибка fallback-инициализации: {e2}")
                self.driver = None
                self.wait = None
                return False

    def _configure_driver(self):
        assert self.driver is not None
        self.driver.set_page_load_timeout(30)
        self.wait = WebDriverWait(self.driver, 30)

    def restart(self) -> bool:
        self.close()
        return self.init_driver()

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
        self.driver = None
        self.wait = None

    def ensure_initialized(self) -> bool:
        if self.driver is None:
            return self.init_driver()
        return True
