#!/usr/bin/env python3
import sys
import argparse
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings
from infrastructure.excel_loader import ExcelLoader
from infrastructure.db import SQLiteRepository
from infrastructure.ozon_api import OzonApiClient
from infrastructure.mail_notifier import MailNotifier
from core.use_cases import RepricingUseCase
from infrastructure.logger import logger


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
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