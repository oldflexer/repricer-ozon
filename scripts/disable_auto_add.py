#!/usr/bin/env python3
import sys
import argparse
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.use_cases.disable_auto_add import DisableAutoAddUseCase
from infrastructure.ozon_api import OzonApiClient
from infrastructure.logger import setup_logging

logger = setup_logging('disable_auto_add.log', mode='a')

async def main():
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