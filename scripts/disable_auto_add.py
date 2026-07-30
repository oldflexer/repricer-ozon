#!/usr/bin/env python3
import sys
import argparse
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from core.use_cases.disable_auto_add import DisableAutoAddUseCase
from infrastructure.ozon_api import OzonApiClient
from infrastructure.logger import setup_logging
from infrastructure.db import run_migrations_once

# Используем имя файла с подстановкой INSTANCE_NAME
logger = setup_logging(f'disable_auto_add-{settings.INSTANCE_NAME}.log', mode='a')

async def main():
    # Применяем миграции (если БД ещё не создана)
    run_migrations_once()

    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
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