"""
Парсер цен конкурентов с Ozon.
Запускается независимо от основного сервиса репрайсинга (например, через cron 2 раза в день).
Принадлежность к магазину определяется переменной окружения INSTANCE_NAME в .env.

Использование:
    python update_competitor_prices.py
    python update_competitor_prices.py --dry-run

Логирование:
    Все логи парсера (включая UC, WDM, selenium) пишутся в parser.log
    и НЕ попадают в repricer.log. Изоляция достигается через:
    - отдельный FileHandler для модулей парсера;
    - propagate=False для суб-логгеров UC/WDM/patcher
      (их логи не «всплывают» в корневой логгер repricer.log).
"""
import argparse
import logging
import os
import sys
import time
import random
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

# Корректный путь до модулей проекта
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import settings
from infrastructure.ozon_parser import OzonPriceParser

# === Изолированное логирование парсера ===
# Парсер пишет в parser.log, отдельный обработчик не даёт логам
# попасть в repricer.log (куда StructLog пишет репрайсер).
# Sub-логгеры UC/WDM/patcher также направляем в parser.log с propagate=False.
_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
_LOG_FILE = Path(__file__).resolve().parent / 'parser.log'

# Модули, чьи логи нужно изолировать в parser.log
_PARSER_LOGGERS = [
    'update_competitor_prices',
    'infrastructure.ozon_parser',
    'undetected_chromedriver',
    'undetected_chromedriver.patcher',
    'uc',
    'WDM',
    'selenium',
    'urllib3',
    'webdriver_manager',
]


def setup_parser_logging() -> logging.Logger:
    """
    Настраивает изолированное логирование для парсера.

    - parser.log: единый файл для всех компонентов парсера.
    - RotatingFileHandler 5 MB × 3 файла (защита от бесконтрольного роста).
    - propagate=False для всех суб-логгеров UC/WDM/patcher.
    - Корневой логгер НЕ модифицируется (repricer.log остаётся чистым).
    """
    file_handler = RotatingFileHandler(
        _LOG_FILE, maxBytes=5_000_000, backupCount=3, encoding='utf-8'
    )
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    file_handler.setLevel(logging.INFO)

    # Консольный обработчик — чтобы видеть прогресс при ручном запуске из CLI
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    console_handler.setLevel(logging.INFO)

    for name in _PARSER_LOGGERS:
        sub = logging.getLogger(name)
        sub.setLevel(logging.INFO)
        # Снимаем все внешние обработчики (на случай повторного вызова из Streamlit)
        sub.handlers.clear()
        sub.addHandler(file_handler)
        sub.addHandler(console_handler)
        # Запрещаем всплывание в корневой логгер (repricer.log)
        sub.propagate = False

    log = logging.getLogger(__name__)
    log.setLevel(logging.INFO)
    log.handlers.clear()
    log.addHandler(file_handler)
    log.addHandler(console_handler)
    log.propagate = False
    return log


logger = setup_parser_logging()

MAX_COMPETITORS = 5
REQUEST_DELAY_RANGE = (2, 4)  # Задержка между запросами для защиты от бана
PARSER_RETRIES = 2             # Кол-во попыток парсинга одной ссылки
LOCK_WAIT_TIMEOUT = 60        # Таймаут ожидания разблокировки Excel (в секундах)


def wait_for_excel_available(file_path: Path, timeout: int = LOCK_WAIT_TIMEOUT) -> bool:
    """
    Проверяет, доступен ли файл для записи (не открыт ли он другим процессом).

    Опрос с интервалом 2 сек. в течение timeout сек.
    Простая проверка попыткой создания и удаления файла-маркера.
    """
    test_file = file_path.with_suffix('.lock_test')
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            # Пытаемся создать файл-маркер, если получилось — Excel свободен
            with open(test_file, 'w') as f:
                f.write('lock_test')
            os.remove(test_file)
            return True
        except PermissionError:
            logger.warning(f"Файл {file_path} занят. Ожидание освобождения...")
            time.sleep(2)
        except Exception as e:
            logger.error(f"Непредвиденная ошибка доступа к файлу: {e}")
            return False
    logger.error(f"Файл {file_path} оставался занятым дольше {timeout} сек.")
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
    """Делает несколько попыток получить цену.

    Между попытками перезапускает драйвер, т.к. если get_price вернул None
    из-за зависшего/упавшего браузера, повторный запрос к тому же драйверу
    бессмысленен. restart() закрывает и пересоздаёт браузер с нуля.
    """
    for attempt in range(1, PARSER_RETRIES + 1):
        try:
            price = parser.get_price(url)
            if price is not None and price > 0:
                return price
            logger.warning(f"Попытка {attempt}/{PARSER_RETRIES}: цена не получена для {url}")
        except Exception as e:
            logger.error(f"Попытка {attempt}/{PARSER_RETRIES}: ошибка парсинга {url}: {e}")

        # Перезапуск драйвера между попытками — иначе повтор упадёт в тот же
        # зависший браузер и весь цикл парсинга пройдёт впустую.
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
    # headless=True для прод-запуска через cron/systemd (без иксов)
    parser = OzonPriceParser(headless=False)

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

    except Exception:
        logger.exception("Критическая ошибка во время парсинга. Сохраняем то, что успели.")
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
            logger.error("Файл стал недоступен перед сохранением. Данные не сохранены.")
    else:
        logger.info("Dry-run режим. Данные в Excel не записаны.")
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
