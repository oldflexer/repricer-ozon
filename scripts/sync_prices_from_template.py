#!/usr/bin/env python3
"""
Полный цикл синхронизации реальных цен из шаблона Ozon:
1. Скачивание шаблона XLSX.
2. Парсинг и расчёт реальных цен.
3. Обновление БД.
4. Удаление файла (опционально).
"""

import argparse
import asyncio
import gc
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

from filelock import FileLock, Timeout

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from infrastructure.db import SQLiteRepository
from infrastructure.ozon_seller import OzonSellerClient
from infrastructure.template_parser import TemplateParser
from infrastructure.logger import setup_logging
from scripts.common import register_signal_handlers

logger = setup_logging("sync_prices_from_template.log", mode="a")

# Блокировка на весь процесс (скачивание + обработка)
LOCK_FILE = os.path.join(tempfile.gettempdir(), "repricer_sync_template.lock")


def find_latest_template(download_dir: str = "download") -> Optional[Path]:
    """Находит последний скачанный файл шаблона в указанной папке."""
    download_path = Path(download_dir)
    if not download_path.exists():
        return None
    files = list(download_path.glob("*.xlsx"))
    if not files:
        return None
    files.sort(key=lambda f: f.stat().st_mtime)
    return files[-1]


def delete_file_with_retry(file_path: Path, max_attempts: int = 5, delay: float = 1.0) -> bool:
    """Удаляет файл с повторными попытками, если он занят."""
    for attempt in range(1, max_attempts + 1):
        try:
            file_path.unlink()
            logger.info(f"Файл {file_path} успешно удалён (попытка {attempt})")
            return True
        except PermissionError as e:
            logger.warning(f"Попытка {attempt}/{max_attempts}: файл занят ({e}), ждём {delay}с...")
            time.sleep(delay)
        except Exception as e:
            logger.error(f"Неожиданная ошибка при удалении: {e}")
            return False
    logger.error(f"Не удалось удалить файл после {max_attempts} попыток")
    return False


async def download_template(download_dir: str, headless: bool = False) -> Optional[Path]:
    """Скачивает шаблон цен из панели Ozon."""
    client = OzonSellerClient(headless=headless, download_dir=download_dir)
    try:
        logger.info("Начинаем скачивание шаблона...")
        if not client.navigate_to_prices():
            logger.error("Не удалось перейти на страницу управления ценами")
            return None

        downloaded = client.download_price_template(timeout=120)
        if downloaded:
            logger.info(f"Шаблон скачан: {downloaded}")
            return downloaded
        else:
            logger.error("Не удалось скачать шаблон")
            return None
    finally:
        client.close()


def process_template(file_path: Path, repo: SQLiteRepository, dry_run: bool = False) -> dict:
    """Обрабатывает шаблон: парсинг, расчёт, обновление БД."""
    parser = TemplateParser(file_path)
    if not parser.load():
        logger.error("Не удалось загрузить файл")
        return {}

    results = parser.process()
    if not results:
        logger.warning("Нет результатов для обновления")
        return {}

    # Получаем все товары из БД для быстрого поиска по SKU
    db_products = repo.get_all_products()
    sku_to_product = {p.sku: p for p in db_products}
    logger.info(f"Загружено {len(sku_to_product)} товаров из БД")

    stats = {
        "total": len(results),
        "updated": 0,
        "not_found": 0,
        "skipped": 0,
        "errors": 0,
    }

    for product_data, real_price, sales_type in results:
        sku = product_data.get("sku")
        if not sku:
            stats["skipped"] += 1
            continue

        if real_price is None:
            logger.warning(f"SKU {sku}: цена не рассчитана, пропускаем")
            stats["skipped"] += 1
            continue

        if sku not in sku_to_product:
            logger.warning(f"SKU {sku} не найден в БД, пропускаем")
            stats["not_found"] += 1
            continue

        if dry_run:
            logger.info(f"DRY-RUN: SKU {sku} -> real_price = {real_price:.2f} (тип: {sales_type})")
            stats["updated"] += 1
            continue

        try:
            repo.update_real_customer_price(sku, real_price)
            logger.info(f"✅ SKU {sku}: обновлена real_price = {real_price:.2f}")
            stats["updated"] += 1
        except Exception as e:
            logger.error(f"❌ SKU {sku}: ошибка обновления: {e}")
            stats["errors"] += 1

    return stats


def main():
    register_signal_handlers()

    parser = argparse.ArgumentParser(
        description="Полный цикл синхронизации реальных цен из шаблона Ozon"
    )
    parser.add_argument(
        "--output-dir",
        default="download",
        help="Папка для сохранения скачанного файла (по умолчанию: download)"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Запустить браузер в headless-режиме (без GUI)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Тестовый режим: скачать и рассчитать, но НЕ записывать в БД"
    )
    parser.add_argument(
        "--keep-file",
        action="store_true",
        help="Не удалять файл шаблона после обработки"
    )
    parser.add_argument(
        "--force-delete",
        action="store_true",
        help="Принудительно удалить файл даже при ошибках (игнорирует --keep-file)"
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    lock = FileLock(LOCK_FILE, timeout=settings.PARSER_LOCK_TIMEOUT)
    try:
        with lock.acquire(timeout=settings.PARSER_LOCK_TIMEOUT):
            logger.info("=== Запуск полной синхронизации цен из шаблона ===")

            # 1. Скачивание
            downloaded_file = asyncio.run(
                download_template(str(output_dir), headless=args.headless)
            )
            if not downloaded_file:
                logger.error("Скачивание не удалось, выход")
                return

            # 2. Обработка
            repo = SQLiteRepository(settings.DATABASE_PATH_PATH)
            stats = process_template(downloaded_file, repo, dry_run=args.dry_run)

            if not stats:
                logger.warning("Статистика пуста, возможно, файл не содержит данных")
                # файл удалим, если принудительно
                if args.force_delete and not args.keep_file:
                    if delete_file_with_retry(downloaded_file):
                        logger.info("Файл удалён принудительно (нет данных)")
                return

            # 3. Вывод статистики в лог
            logger.info(
                f"Статистика: всего={stats['total']}, "
                f"обновлено={stats['updated']}, "
                f"не найдено={stats['not_found']}, "
                f"пропущено={stats['skipped']}, "
                f"ошибок={stats['errors']}"
            )

            # 4. Освобождение ресурсов перед удалением
            parser = None
            repo = None
            gc.collect()
            time.sleep(0.5)

            # 5. Удаление файла
            if args.dry_run:
                logger.info("Dry-run: файл не удалён")
                return

            should_delete = False
            delete_reason = ""

            if args.force_delete:
                should_delete = True
                delete_reason = "принудительное удаление (--force-delete)"
            elif args.keep_file:
                should_delete = False
                delete_reason = "файл сохранён (--keep-file)"
            elif stats['errors'] == 0:
                should_delete = True
                delete_reason = "успешная обработка без ошибок"
            else:
                should_delete = False
                delete_reason = f"обнаружены ошибки ({stats['errors']})"

            if should_delete:
                if delete_file_with_retry(downloaded_file):
                    logger.info(f"Файл {downloaded_file} удалён: {delete_reason}")
                else:
                    logger.error("Не удалось удалить файл после нескольких попыток")
            else:
                logger.info(f"Файл не удалён: {delete_reason}")

            logger.info("=== Синхронизация завершена ===")

    except Timeout:
        logger.error(
            f"Не удалось получить блокировку за {settings.PARSER_LOCK_TIMEOUT} секунд. "
            "Скрипт уже выполняется."
        )
    except Exception as e:
        logger.exception(f"Критическая ошибка: {e}")


if __name__ == "__main__":
    main()