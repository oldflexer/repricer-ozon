#!/usr/bin/env python3
"""
Скрипт для ручного логина в Ozon и сохранения профиля Chrome.

Запускает браузер с профилем, открывает страницу Ozon Seller,
ждёт 5 минут (или до ручного закрытия), затем сохраняет профиль и закрывает браузер.
"""

import sys
from pathlib import Path

# Добавляем корень проекта в sys.path для импортов
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import time
import signal

from infrastructure.chrome_driver import ChromeDriverManager
from infrastructure.logger import logger
from config.settings import settings


def main() -> int:
    """Main entry point for manual Ozon login."""
    logger.info("=" * 60)
    logger.info("РУЧНОЙ ЛОГИН В OZON - СОХРАНЕНИЕ ПРОФИЛЯ CHROME")
    logger.info("=" * 60)
    
    # URL для входа в Ozon Seller
    ozon_url = "https://seller.ozon.ru/"
    
    # Таймаут в секундах (5 минут)
    TIMEOUT_SECONDS = 300
    
    # Создаём менеджер драйвера с профилем
    manager = ChromeDriverManager(
        headless=False,  # Обязательно False для ручного логина
        use_profile=True,
        download_dir=None,
    )
    
    # Флаг для отслеживания ручного закрытия
    manually_closed = False
    
    def signal_handler(signum: int, frame: object) -> None:
        nonlocal manually_closed
        logger.info("Получен сигнал завершения, закрываем браузер...")
        manually_closed = True
        manager.close()
        sys.exit(0)
    
    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Инициализируем драйвер
        logger.info("Инициализация Chrome драйвера...")
        if not manager.init_driver():
            logger.error("Не удалось инициализировать драйвер")
            return 1
        
        driver = manager.driver
        assert driver is not None
        
        # Открываем Ozon Seller
        logger.info(f"Открываем страницу: {ozon_url}")
        driver.get(ozon_url)
        
        logger.info("-" * 60)
        logger.info("⏳ ВРЕМЯ НА ЛОГИН: 5 МИНУТ (300 секунд)")
        logger.info("🌐 Войдите в аккаунт Ozon в открывшемся браузере")
        logger.info("🔒 После входа профиль сохранится автоматически")
        logger.info("❌ Можно закрыть браузер вручную — профиль тоже сохранится")
        logger.info("-" * 60)
        
        # Ждём 5 минут или пока пользователь не закроет браузер
        start_time = time.time()
        while time.time() - start_time < TIMEOUT_SECONDS:
            # Проверяем, жив ли драйвер (пользователь не закрыл окно)
            try:
                _ = driver.current_url  # Просто обращаемся к драйверу
            except Exception:
                logger.info("Браузер закрыт пользователем")
                manually_closed = True
                break
            
            # Показываем оставшееся время каждые 30 секунд
            elapsed = int(time.time() - start_time)
            remaining = TIMEOUT_SECONDS - elapsed
            if elapsed % 30 == 0 and elapsed > 0:
                logger.info(f"⏱ Осталось времени: {remaining // 60} мин {remaining % 60} сек")
            
            time.sleep(1)
        
        if not manually_closed:
            logger.info("⏰ Время вышло (5 минут), закрываем браузер...")
        
        # Профиль автоматически сохраняется при закрытии драйвера
        manager.close()
        logger.info("✅ Профиль Chrome сохранён, браузер закрыт")
        
        # Путь к профилю для информации
        profile_path = getattr(settings, "CHROME_PROFILE_PATH", "не задан")
        logger.info(f"📁 Путь к профилю: {profile_path}")
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("Прервано пользователем (Ctrl+C)")
        manager.close()
        return 0
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        manager.close()
        return 1


if __name__ == "__main__":
    sys.exit(main())
