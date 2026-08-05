#!/usr/bin/env python3
"""
Парсер цен конкурентов с Ozon.

Читает Excel-файл, для каждого товара и каждого конкурента (до MAX_COMPETITORS)
загружает страницу товара и извлекает цену с помощью Selenium (undetected-chromedriver).

Обновляет колонки Цена 1..N в Excel-файле точечно, сохраняя форматирование.

Использование:
    python scripts/parser.py [--dry-run]
"""

import argparse
import os
import random
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
from filelock import FileLock, Timeout

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from infrastructure.file_utils import save_safely, wait_for_excel_available
from infrastructure.ozon_parser import OzonPriceParser
from infrastructure.x_display import get_available_display
from scripts.common import register_signal_handlers, run_migrations_once, is_shutdown_requested, setup_parser_logging

logger = setup_parser_logging("parser")

LOCK_FILE = os.path.join(tempfile.gettempdir(), "repricer_parser.lock")


def parse_price_with_retry(parser: OzonPriceParser, url: str) -> Optional[float]:
    """
    Пытается получить цену по URL с повторными попытками (до PARSER_RETRIES).

    Args:
        parser: Экземпляр OzonPriceParser.
        url: URL страницы товара.

    Returns:
        Цена (float), -1.0 если товар закончился, None при ошибке.
    """
    for attempt in range(1, settings.PARSER_RETRIES + 1):
        if is_shutdown_requested():
            logger.info("Shutdown requested, stopping price parsing")
            return None
            
        try:
            price = parser.get_price(url)
            if price == -1.0:
                # товар закончился, повторять не нужно
                return -1.0
            if price is not None and price > 0:
                return price
            logger.warning(
                f"Попытка {attempt}/{settings.PARSER_RETRIES}: цена не получена для {url}"
            )
        except Exception as e:
            logger.error(
                f"Попытка {attempt}/{settings.PARSER_RETRIES}: ошибка парсинга {url}: {e}"
            )

        if attempt < settings.PARSER_RETRIES:
            logger.info(f"Перезапуск драйвера перед повторной попыткой {attempt + 1}...")
            try:
                parser.restart()
            except Exception as restart_err:
                logger.error(f"Не удалось перезапустить драйвер: {restart_err}")
                return None
            time.sleep(random.uniform(2.0, 4.0))

    return None


def update_prices(dry_run: bool = False) -> Dict[str, int]:
    """
    Основная логика обновления цен конкурентов.

    Args:
        dry_run: Если True, данные в Excel не записываются.

    Returns:
        Словарь со статистикой: updated, errors, skipped.
    """
    excel_path = settings.DATA_FILE_PATH

    if not excel_path.exists():
        logger.error(f"Файл не найден: {excel_path}")
        return {"updated": 0, "errors": 0, "skipped": 0}

    if not wait_for_excel_available(excel_path):
        return {"updated": 0, "errors": 0, "skipped": 0}

    try:
        df = pd.read_excel(excel_path, engine="openpyxl")
        df.columns = df.columns.str.strip()
    except Exception as e:
        logger.error(f"Не удалось прочитать Excel: {e}")
        return {"updated": 0, "errors": 0, "skipped": 0}

    # Определяем индексы колонок для каждого конкурента (используем настраиваемые префиксы)
    url_prefix = settings.COMPETITOR_URL_COLUMN_PREFIX
    price_prefix = settings.COMPETITOR_PRICE_COLUMN_PREFIX
    
    col_indices = {}
    for i in range(1, settings.MAX_COMPETITORS + 1):
        url_col_name = f"{url_prefix} {i}"
        price_col_name = f"{price_prefix} {i}"
        if url_col_name in df.columns and price_col_name in df.columns:
            col_indices[i] = {
                "url_col": df.columns.get_loc(url_col_name) + 1,  # 1-based для openpyxl
                "price_col": df.columns.get_loc(price_col_name) + 1,
            }

    if not col_indices:
        logger.error(f"Не найдены колонки '{url_prefix} N' / '{price_prefix} N' в файле.")
        return {"updated": 0, "errors": 0, "skipped": 0}

    stats = {"updated": 0, "errors": 0, "skipped": 0}
    parser = OzonPriceParser(headless=False)
    excel_updates = {}

    try:
        for row_num, (_, row) in enumerate(df.iterrows(), start=2):
            if is_shutdown_requested():
                logger.info("Shutdown requested, stopping row processing")
                break
                
            sku = row.get("SKU") or row.get("sku") or f"row_{row_num}"

            for i in range(1, settings.MAX_COMPETITORS + 1):
                if is_shutdown_requested():
                    break
                    
                cols = col_indices.get(i)
                if not cols:
                    stats["skipped"] += 1
                    continue

                url = row.get(f"{url_prefix} {i}")
                if pd.isna(url) or not str(url).strip():
                    stats["skipped"] += 1
                    continue

                logger.info(f"Парсинг SKU {sku}, конкурент {i}...")
                new_price = parse_price_with_retry(parser, str(url))
                if new_price == -1.0:
                    stats["skipped"] += 1
                    logger.info(f"SKU {sku}, конкурент {i}: товар закончился, пропускаем")
                    continue
                elif new_price is not None:
                    excel_updates[(row_num, cols["price_col"])] = new_price
                    stats["updated"] += 1
                    logger.info(f"SKU {sku}, конкурент {i}: {new_price} ₽")
                else:
                    stats["errors"] += 1
                    old_price = row.get(f"{price_prefix} {i}")
                    old_display = f"{old_price} ₽" if pd.notna(old_price) else "нет данных"
                    logger.warning(
                        f"SKU {sku}, конкурент {i}: ошибка парсинга. "
                        f"Оставлена прежняя цена: {old_display}"
                    )

                time.sleep(
                    random.uniform(
                        settings.PARSER_REQUEST_DELAY_MIN,
                        settings.PARSER_REQUEST_DELAY_MAX,
                    )
                )

    except Exception:
        logger.exception("Критическая ошибка во время парсинга. Сохраняем то, что успели.")
    finally:
        parser.close()

    if is_shutdown_requested():
        logger.info("Graceful shutdown: saving partial results before exit")
    
    if not dry_run:
        if excel_updates:
            if wait_for_excel_available(excel_path):
                try:
                    save_safely(excel_updates, excel_path)
                except Exception:
                    pass
            else:
                logger.error("Файл стал недоступен перед сохранением. Данные не сохранены.")
        elif stats["updated"] == 0:
            logger.info("Нет обновлённых цен — файл не перезаписывается.")
    else:
        logger.info("Dry-run режим. Данные в Excel не записаны.")
        logger.info(f"Статистика: {stats}")

    return stats


def main() -> None:
    """
    Основная точка входа.

    Определяет доступный DISPLAY (Linux), запускает миграции,
    получает блокировку на выполнение и запускает update_prices().
    """
    # Регистрируем обработчики сигналов
    register_signal_handlers()

    # Определяем DISPLAY только на Linux/Unix
    if not sys.platform.startswith("win"):
        if "DISPLAY" not in os.environ:
            display = get_available_display()
            if display:
                os.environ["DISPLAY"] = display
                logger.info(f"Установлен DISPLAY={display}")
            else:
                logger.error("Не найден доступный X-сервер. Парсинг невозможен.")
                return

    # Применяем миграции (для согласованности)
    run_migrations_once()

    parser = argparse.ArgumentParser(description="Парсер цен конкурентов для Ozon.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Тестовый режим: парсить, но не сохранять в Excel",
    )
    args = parser.parse_args()

    lock = FileLock(LOCK_FILE, timeout=settings.PARSER_LOCK_TIMEOUT)
    try:
        with lock.acquire(timeout=settings.PARSER_LOCK_TIMEOUT):
            logger.info("=== Запуск парсера конкурентов ===")
            stats = update_prices(dry_run=args.dry_run)
            logger.info(
                f"=== Завершено. Обновлено: {stats['updated']}, "
                f"ошибок: {stats['errors']}, пропущено: {stats['skipped']} ==="
            )
    except Timeout:
        logger.error(
            f"Не удалось получить блокировку парсера за {settings.PARSER_LOCK_TIMEOUT} секунд. "
            "Парсер уже выполняется."
        )
    except Exception as e:
        logger.exception(f"Критическая ошибка: {e}")


if __name__ == "__main__":
    main()