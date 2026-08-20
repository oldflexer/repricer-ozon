#!/usr/bin/env python3
"""
Точка входа для запуска полного цикла репрайсинга.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.container import container
from core.services.real_price_sync import RealPriceSyncService
from scripts.common import register_signal_handlers, setup_script_logging

logger = setup_script_logging("repricer")


async def main() -> None:
    register_signal_handlers()

    parser = argparse.ArgumentParser(description="Запуск репрайсинга товаров")
    parser.add_argument(
        "--dry-run", action="store_true", help="Тестовый режим: расчёт без отправки цен"
    )
    parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Не выполнять синхронизацию цен из шаблона",
    )
    args = parser.parse_args()

    sync_service = RealPriceSyncService(
        output_dir=str(Path("download").resolve()), headless=False
    )

    # 1. Синхронизация ДО репрайсинга
    if not args.no_sync:
        logger.info("Выполняем синхронизацию реальных цен из шаблона...")
        stats = await sync_service.sync_real_prices_async(
            dry_run=args.dry_run,
            keep_file=args.dry_run,
            force_delete=False,
            use_lock=True,
        )
        if stats:
            logger.info(f"Синхронизация завершена: {stats}")
        else:
            logger.warning("Синхронизация не выполнена (возможно, занят lock или ошибка)")
    else:
        logger.info("Синхронизация пропущена (--no-sync)")

    # 2. Запуск репрайсинга
    use_case = container.repricing_use_case()
    stats = await use_case.execute(dry_run=args.dry_run)
    logger.info("main_finished", result=stats)

    # 3. Закрытие API
    api = container.api_client()
    await api.close()


if __name__ == "__main__":
    asyncio.run(main())
