import logging
import sys
import argparse
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import DATA_FILE, settings
from infrastructure.loader import DataLoader
from infrastructure.db import SQLiteRepository
from infrastructure.ozon_api import OzonApiClient
from infrastructure.mail_notifier import MailNotifier
from core.use_cases import RepricingUseCase

log_file = Path(__file__).parent / 'repricer.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, mode='w', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    repo = SQLiteRepository()
    api = OzonApiClient()
    notifier = MailNotifier()
    loader = DataLoader(DATA_FILE)

    use_case = RepricingUseCase(repo, api, notifier, loader)
    stats = await use_case.execute(dry_run=args.dry_run)

    logger.info(f"Результат: {stats}")
    await api.close()


if __name__ == "__main__":
    asyncio.run(main())