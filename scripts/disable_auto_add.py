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

from core.container import container
from infrastructure.logger import setup_logging

logger = setup_logging(f"disable_auto_add-{container.config.INSTANCE_NAME()}.log", mode="a")


async def main() -> None:
    """
    Запускает процесс отключения автодобавления.

    Читает аргумент --dry-run и выполняет соответствующее действие.
    """

    parser = argparse.ArgumentParser(description="Отключение автодобавления в акции Ozon")
    parser.add_argument("--dry-run", action="store_true", help="Тестовый режим: только показать, что будет удалено")
    args = parser.parse_args()

    use_case = container.disable_auto_add_use_case()

    try:
        stats = await use_case.execute(dry_run=args.dry_run)
        logger.info(f"Статистика: {stats}")
    finally:
        api = container.api_client()
        await api.close()


if __name__ == "__main__":
    asyncio.run(main())