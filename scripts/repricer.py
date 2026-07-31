#!/usr/bin/env python3
"""
Точка входа для запуска полного цикла репрайсинга.

Загружает товары из Excel, получает данные из Ozon API, рассчитывает
целевые цены, отправляет обновления и сохраняет историю.

Использование:
    python scripts/repricer.py [--dry-run]
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from core.use_cases import RepricingUseCase
from infrastructure.db import SQLiteRepository, run_migrations_once
from infrastructure.excel_loader import ExcelLoader
from infrastructure.logger import setup_logging
from infrastructure.mail_notifier import MailNotifier
from infrastructure.ozon_api import OzonApiClient

logger = setup_logging(f"repricer-{settings.INSTANCE_NAME}.log", mode="a")


async def main() -> None:
    """
    Запускает полный цикл репрайсинга.

    Читает аргумент --dry-run и выполняет соответствующее действие.
    """
    # Применяем миграции перед работой с БД
    run_migrations_once()

    parser = argparse.ArgumentParser(description="Запуск репрайсинга товаров")
    parser.add_argument("--dry-run", action="store_true", help="Тестовый режим: расчёт без отправки цен")
    args = parser.parse_args()

    repo = SQLiteRepository(settings.DATABASE_PATH_PATH)
    api = OzonApiClient()
    notifier = MailNotifier()
    loader = ExcelLoader(settings.DATA_FILE_PATH)

    use_case = RepricingUseCase(repo, api, notifier, loader)
    stats = await use_case.execute(dry_run=args.dry_run)

    logger.info("main_finished", result=stats)
    await api.close()


if __name__ == "__main__":
    asyncio.run(main())