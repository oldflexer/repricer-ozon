"""
Парсер цен конкурентов с Ozon.
Запускается независимо от основного сервиса репрайсинга (например, через cron 2 раза в день).
Принадлежность к магазину определяется переменной окружения INSTANCE_NAME в .env.

Использование:
    python update_competitor_prices.py
    python update_competitor_prices.py --dry-run
"""
import argparse
import logging
import os
import sys
import time
import random
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

# Корректный путь до модулей проекта
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import settings
from infrastructure.ozon_parser import OzonPriceParser
from infrastructure.logger import logger as struct_logger

# Базовая настройка логирования для консоли
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

MAX_COMPETITORS = 5
REQUEST_DELAY_RANGE = (2, 4)  # Задержка между запросами для защиты от бана
PARSER_RETRIES = 2             # Кол-во попыток парсинга одной ссылки
LOCK_WAIT_TIMEOUT = 60        # Таймаут ожидания разблокировки Excel (в секундах)


def wait_for_excel_available(file_path: Path, timeout: int = 300) -> bool:
    """
    Проверяет, доступен ли файл для записи (не открыт ли он другим процессом).
    Простая проверка попыткой переименования/удаления временного файла.
    """
    test_file = file_path.with_suffix('.lock_test')
    try:
        # Пытаемся создать файл-маркер, если получилось — Excel свободен
        with open(test_file, 'w') as f:
            f.write('lock_test')
        os.remove(test_file)
        return True
    except PermissionError:
        logger.error(f"Файл {file_path} занят другим процессом (прод-циклом?).")
        return False
    except Exception as e:
        logger.error(f"Непредвиденная ошибка доступа к файлу: {e}")
        return False


def save_safely(df: pd.DataFrame, file_path: Path):
    """
    Атомарное сохранение Excel.
    Сначала пишем во временный файл, затем заменяем оригинальный.
    Защищает от потери данных при падении во время сохранения.
    """
    tmp_path = file_path.with_suffix('.tmp.xlsx')
    try:
        df.to_excel(tmp_path, index=False, engine='openpyxl')
        os.replace(tmp_path, file_path)
        logger.info(f"Файл {file_path} успешно сохранен.")
    except Exception as e:
        logger.error(f"Ошибка при сохранении файла {file_path}: {e}")
        if tmp_path.exists():
            os.remove(tmp_path)
        raise


def parse_price_with_retry(parser: OzonPriceParser, url: str) -> Optional[float]:
    """Делает несколько попыток получить цену."""
    for attempt in range(1, PARSER_RETRIES + 1):
        try:
            price = parser.get_price(url)
            if price is not None and price > 0:
                return price
            logger.warning(f"Попытка {attempt}/{PARSER_RETRIES}: цена не получена для {url}")
        except Exception as e:
            logger.error(f"Попытка {attempt}/{PARSER_RETRIES}: ошибка парсинга {url}: {e}")

        if attempt < PARSER_RETRIES:
            time.sleep(random.uniform(2.0, 4.0))

    return None


def update_prices(dry_run: bool = False) -> Dict[str, int]:
    """Основная логика обновления цен конкурентов."""
    excel_path = settings.DATA_FILE

    if not excel_path.exists():
        logger.error(f"Файл не найден: {excel_path}")
        return {"updated": 0, "errors": 0, "skipped": 0}

    # Проверяем доступность файла перед тяжелыми операциями
    if not wait_for_excel_available(excel_path):
        return {"updated": 0, "errors": 0, "skipped": 0}

    # Загружаем данные
    try:
        df = pd.read_excel(excel_path, engine='openpyxl')
    except Exception as e:
        logger.error(f"Не удалось прочитать Excel: {e}")
        return {"updated": 0, "errors": 0, "skipped": 0}

    # Гарантируем наличие колонок для цен конкурентов (в файле они называются "Цена 1"..."Цена 5")
    price_cols = [f'Цена {i}' for i in range(1, MAX_COMPETITORS + 1)]
    for col in price_cols:
        if col not in df.columns:
            df[col] = None

    stats = {"updated": 0, "errors": 0, "skipped": 0}
    parser = OzonPriceParser(headless=True)

    try:
        # Проходим по всем строкам и всем 5 конкурентам
        for idx, row in df.iterrows():
            sku = row.get('SKU') or row.get('sku') or f"row_{idx}"

            for i in range(1, MAX_COMPETITORS + 1):
                url_col = f'Конкурент {i}'
                price_col = f'Цена {i}'

                url = row.get(url_col)

                # Пропускаем только если нет URL конкурента
                if pd.isna(url) or not str(url).strip():
                    stats["skipped"] += 1
                    continue

                logger.info(f"Парсинг SKU {sku}, конкурент {i}...")
                new_price = parse_price_with_retry(parser, str(url))

                if new_price is not None:
                    # Успешно получили цену — обновляем
                    df.at[idx, price_col] = new_price
                    stats["updated"] += 1
                    logger.info(f"SKU {sku}, конкурент {i}: {new_price} ₽")
                else:
                    # Ошибка парсинга — оставляем старую цену как есть!
                    stats["errors"] += 1
                    old_price = row.get(price_col)
                    old_display = f"{old_price} ₽" if pd.notna(old_price) else "нет данных"
                    logger.warning(f"SKU {sku}, конкурент {i}: ошибка парсинга. Оставлена прежняя цена: {old_display}")

                # Задержка между запросами
                time.sleep(random.uniform(*REQUEST_DELAY_RANGE))

    except Exception as e:
        logger.exception(f"Критическая ошибка во время парсинга. Сохраняем то, что успели.")
    finally:
        parser.close()

    # Сохраняем результат, если не dry-run и файл не занят
    if not dry_run:
        if wait_for_excel_available(excel_path):
            try:
                save_safely(df, excel_path)
            except Exception:
                pass # Ошибки уже залогированы в save_safely
        else:
            logger.error(f"Файл стал недоступен перед сохранением. Данные не сохранены.")
    else:
        logger.info(f"Dry-run режим. Данные в Excel не записаны.")
        logger.info(f"Статистика: {stats}")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Парсер цен конкурентов для Ozon.")
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Тестовый режим: парсить, но не сохранять в Excel"
    )
    args = parser.parse_args()

    logger.info("=== Запуск парсера конкурентов ===")
    stats = update_prices(dry_run=args.dry_run)
    logger.info(f"=== Завершено. Обновлено: {stats['updated']}, ошибок: {stats['errors']}, пропущено: {stats['skipped']} ===")


if __name__ == '__main__':
    main()

