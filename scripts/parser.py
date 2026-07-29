"""
Парсер цен конкурентов с Ozon.
Запускается независимо от основного сервиса репрайсинга (например, через cron 2 раза в день).
Принадлежность к магазину определяется переменной окружения INSTANCE_NAME в .env.

Использование:
    python update_competitor_prices.py
    python update_competitor_prices.py --dry-run

Логирование:
    Все логи парсера (включая UC, WDM, selenium) пишутся в parser.log
    и НЕ попадают в repricer.log. Настройка логирования делегирована в
    infrastructure.logger.setup_parser_logging().
"""
import argparse
import os
import sys
import tempfile
import time
import random
from pathlib import Path
from typing import Dict, Optional
from filelock import FileLock, Timeout

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import settings
from infrastructure.ozon_parser import OzonPriceParser
from infrastructure.logger import setup_parser_logging
from infrastructure.file_utils import wait_for_excel_available, save_safely
from infrastructure.x_display import get_available_display

logger = setup_parser_logging(f'parser-{settings.INSTANCE_NAME}.log', mode='a')

MAX_COMPETITORS = 5
REQUEST_DELAY_RANGE = (5, 10)
PARSER_RETRIES = 2
LOCK_WAIT_TIMEOUT = 60

LOCK_FILE = os.path.join(tempfile.gettempdir(), 'repricer_parser.lock')
LOCK_TIMEOUT = 1800


def parse_price_with_retry(parser: OzonPriceParser, url: str) -> Optional[float]:
    for attempt in range(1, PARSER_RETRIES + 1):
        try:
            price = parser.get_price(url)
            if price == -1.0:
                # товар закончился, не повторяем
                return -1.0
            if price is not None and price > 0:
                return price
            logger.warning(f"Попытка {attempt}/{PARSER_RETRIES}: цена не получена для {url}")
        except Exception as e:
            logger.error(f"Попытка {attempt}/{PARSER_RETRIES}: ошибка парсинга {url}: {e}")

        if attempt < PARSER_RETRIES:
            logger.info(f"Перезапуск драйвера перед повторной попыткой {attempt + 1}...")
            try:
                parser.restart()
            except Exception as restart_err:
                logger.error(f"Не удалось перезапустить драйвер: {restart_err}")
                return None
            time.sleep(random.uniform(2.0, 4.0))

    return None


def update_prices(dry_run: bool = False) -> Dict[str, int]:
    """Основная логика обновления цен конкурентов."""
    excel_path = settings.DATA_FILE_PATH

    if not excel_path.exists():
        logger.error(f"Файл не найден: {excel_path}")
        return {"updated": 0, "errors": 0, "skipped": 0}

    if not wait_for_excel_available(excel_path):
        return {"updated": 0, "errors": 0, "skipped": 0}

    try:
        df = pd.read_excel(excel_path, engine='openpyxl')
        df.columns = df.columns.str.strip()
    except Exception as e:
        logger.error(f"Не удалось прочитать Excel: {e}")
        return {"updated": 0, "errors": 0, "skipped": 0}

    col_indices = {}
    for i in range(1, MAX_COMPETITORS + 1):
        url_col_name = f'Конкурент {i}'
        price_col_name = f'Цена {i}'
        if url_col_name in df.columns and price_col_name in df.columns:
            col_indices[i] = {
                'url_col': df.columns.get_loc(url_col_name) + 1,
                'price_col': df.columns.get_loc(price_col_name) + 1,
            }

    if not col_indices:
        logger.error("Не найдены колонки 'Конкурент N' / 'Цена N' в файле.")
        return {"updated": 0, "errors": 0, "skipped": 0}

    stats = {"updated": 0, "errors": 0, "skipped": 0}
    parser = OzonPriceParser(headless=False)
    excel_updates = {}

    try:
        for row_num, (_, row) in enumerate(df.iterrows(), start=2):
            sku = row.get('SKU') or row.get('sku') or f"row_{row_num}"

            for i in range(1, MAX_COMPETITORS + 1):
                cols = col_indices.get(i)
                if not cols:
                    stats["skipped"] += 1
                    continue

                url = row.get(f'Конкурент {i}')
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
                    excel_updates[(row_num, cols['price_col'])] = new_price
                    stats["updated"] += 1
                    logger.info(f"SKU {sku}, конкурент {i}: {new_price} ₽")
                else:
                    stats["errors"] += 1
                    old_price = row.get(f'Цена {i}')
                    old_display = f"{old_price} ₽" if pd.notna(old_price) else "нет данных"
                    logger.warning(f"SKU {sku}, конкурент {i}: ошибка парсинга. Оставлена прежняя цена: {old_display}")

                time.sleep(random.uniform(*REQUEST_DELAY_RANGE))

    except Exception:
        logger.exception("Критическая ошибка во время парсинга. Сохраняем то, что успели.")
    finally:
        parser.close()

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


def main():
    # Определяем DISPLAY только на Linux/Unix
    if not sys.platform.startswith('win'):
        if 'DISPLAY' not in os.environ:
            from infrastructure.x_display import get_available_display
            display = get_available_display()
            if display:
                os.environ['DISPLAY'] = display
                logger.info(f"Установлен DISPLAY={display}")
            else:
                logger.error("Не найден доступный X-сервер. Парсинг невозможен.")
                return

    parser = argparse.ArgumentParser(description="Парсер цен конкурентов для Ozon.")
    parser.add_argument('--dry-run', action='store_true', help="Тестовый режим: парсить, но не сохранять в Excel")
    args = parser.parse_args()

    lock = FileLock(LOCK_FILE, timeout=LOCK_TIMEOUT)
    try:
        with lock.acquire(timeout=LOCK_TIMEOUT):
            logger.info("=== Запуск парсера конкурентов ===")
            stats = update_prices(dry_run=args.dry_run)
            logger.info(f"=== Завершено. Обновлено: {stats['updated']}, ошибок: {stats['errors']}, пропущено: {stats['skipped']} ===")
    except Timeout:
        logger.error(f"Не удалось получить блокировку парсера за {LOCK_TIMEOUT} секунд. Парсер уже выполняется.")
    except Exception as e:
        logger.exception(f"Критическая ошибка: {e}")


if __name__ == '__main__':
    main()