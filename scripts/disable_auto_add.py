#!/usr/bin/env python3
"""
Точка входа для отключения автодобавления товаров в акции Ozon.

Запускает use‑case DisableAutoAddUseCase, который:
    1. Получает все товары с автодобавлением через Ozon API.
    2. Удаляет их (или выводит список в dry‑run).

Использование:
    python scripts/disable_auto_add.py [--dry-run]
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from core.use_cases.disable_auto_add import DisableAutoAddUseCase
from infrastructure.db import run_migrations_once
from infrastructure.logger import setup_logging
from infrastructure.ozon_api import OzonApiClient

logger = setup_logging(f"disable_auto_add-{settings.INSTANCE_NAME}.log", mode="a")


async def main() -> None:
    """
    Запускает процесс отключения автодобавления.

    Читает аргумент --dry-run и выполняет соответствующее действие.
    """
    # Применяем миграции (если БД ещё не создана)
    run_migrations_once()

    parser = argparse.ArgumentParser(description="Отключение автодобавления в акции Ozon")
    parser.add_argument("--dry-run", action="store_true", help="Тестовый режим: только показать, что будет удалено")
    args = parser.parse_args()

    api = OzonApiClient()
    use_case = DisableAutoAddUseCase(api)

    try:
        stats = await use_case.execute(dry_run=args.dry_run)
        logger.info(f"Статистика: {stats}")
    finally:
        await api.close()


if __name__ == "__main__":
    asyncio.run(main())