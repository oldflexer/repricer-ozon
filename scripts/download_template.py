#!/usr/bin/env python3
"""
Скачивание шаблона XLSX с ценами из панели управления Ozon.
Использует блокировку для предотвращения одновременных запусков.
Браузер остаётся открытым после скачивания для просмотра результата.
"""

import argparse
import os
import sys
import tempfile
from pathlib import Path

from filelock import FileLock, Timeout

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from infrastructure.ozon_seller import OzonSellerClient
from infrastructure.logger import setup_logging
from scripts.common import register_signal_handlers

logger = setup_logging("download_template.log", mode="a")

LOCK_FILE = os.path.join(tempfile.gettempdir(), "repricer_download_template.lock")


def main():
    register_signal_handlers()

    parser = argparse.ArgumentParser(description="Скачивание шаблона цен Ozon")
    parser.add_argument(
        "--output-dir",
        default="download",
        help="Папка для сохранения файла (по умолчанию: download)"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Запустить браузер в headless-режиме (без GUI)"
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    lock = FileLock(LOCK_FILE, timeout=settings.PARSER_LOCK_TIMEOUT)
    try:
        with lock.acquire(timeout=settings.PARSER_LOCK_TIMEOUT):
            logger.info("=== Запуск скачивания шаблона цен ===")
            client = OzonSellerClient(headless=args.headless, download_dir=str(output_dir))
            try:
                # Переходим на страницу управления ценами
                if not client.navigate_to_prices():
                    logger.error("Не удалось перейти на страницу управления ценами")
                    return

                # Скачиваем шаблон
                downloaded = client.download_price_template(timeout=120)
                if downloaded:
                    logger.info(f"✅ Шаблон скачан: {downloaded}")
                else:
                    logger.error("❌ Не удалось скачать шаблон")
            finally:
                client.close()
    except Timeout:
        logger.error(
            f"Не удалось получить блокировку за {settings.PARSER_LOCK_TIMEOUT} секунд. "
            "Скрипт уже выполняется."
        )
    except Exception as e:
        logger.exception(f"Критическая ошибка: {e}")


if __name__ == "__main__":
    main()