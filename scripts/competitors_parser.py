#!/usr/bin/env python3
"""
Парсер цен конкурентов с Ozon.

Точка входа для CLI. Запускает ParseCompetitorPricesUseCase.
"""

import argparse
import asyncio
import os
import sys
import tempfile
from pathlib import Path

from filelock import FileLock, Timeout

# Добавляем корень проекта в sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from core.container import container
from core.use_cases.parse_competitor_prices import ParseCompetitorPricesUseCase
from scripts.common import register_signal_handlers, setup_parser_logging

logger = setup_parser_logging("parser")

LOCK_FILE = Path(tempfile.gettempdir()) / "repricer_parser.lock"


async def main_async(dry_run: bool) -> None:
    """Асинхронная обёртка для выполнения UseCase."""
    parser = container.parser()
    use_case = ParseCompetitorPricesUseCase(parser)
    stats = await use_case.execute(dry_run=dry_run)
    logger.info(
        f"=== Завершено. Обновлено: {stats['updated']}, "
        f"ошибок: {stats['errors']}, пропущено: {stats['skipped']} ==="
    )


def main() -> None:
    """
    Основная точка входа.

    Получает блокировку на выполнение и запускает UseCase.
    """
    register_signal_handlers()

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
            asyncio.run(main_async(args.dry_run))
    except Timeout:
        logger.error(
            f"Не удалось получить блокировку парсера за {settings.PARSER_LOCK_TIMEOUT} секунд. "
            "Парсер уже выполняется."
        )
    except Exception as e:
        logger.exception(f"Критическая ошибка: {e}")


if __name__ == "__main__":
    main()
