#!/usr/bin/env python3
"""
Заглушка для будущего парсера XLSX-образцов.

Планируется:
- Чтение файла с образцами (xlsx)
- Извлечение данных
- Сохранение в БД или Excel
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.logger import setup_logging
from scripts.common import register_signal_handlers

logger = setup_logging("xlsx_sample_parser.log", mode="a")


async def main_async(dry_run: bool = False) -> None:
    """Заглушка для будущей реализации."""
    logger.info("=== Запуск парсера XLSX-образцов (заглушка) ===")
    if dry_run:
        logger.info("Dry-run режим: ничего не будет изменено.")
    logger.info("=== Завершено (заглушка) ===")


def main() -> None:
    register_signal_handlers()

    parser = argparse.ArgumentParser(
        description="Парсер XLSX-образцов (заглушка для будущей реализации)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Тестовый режим: только показать, что будет сделано",
    )
    args = parser.parse_args()

    try:
        asyncio.run(main_async(dry_run=args.dry_run))
    except KeyboardInterrupt:
        logger.info("Прервано пользователем")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
