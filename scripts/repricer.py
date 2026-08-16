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
        help="Не выполнять синхронизацию цен из шаблона перед запуском",
    )
    args = parser.parse_args()

    sync_service = RealPriceSyncService(output_dir="download", headless=False)

    # 1. Синхронизация ДО репрайсинга
    if not args.no_sync:
        logger.info("Выполняем синхронизацию реальных цен из шаблона (перед)...")
        stats = await sync_service.sync_real_prices_async(
            dry_run=args.dry_run,
            keep_file=args.dry_run,
            force_delete=False,
            use_lock=True,
        )
        if stats:
            logger.info(f"Синхронизация (перед) завершена: {stats}")
        else:
            logger.warning("Синхронизация (перед) не выполнена (возможно, занят lock или ошибка)")
    else:
        logger.info("Синхронизация перед репрайсингом пропущена (--no-sync)")

    # 2. Запуск репрайсинга
    use_case = container.repricing_use_case()
    stats = await use_case.execute(dry_run=args.dry_run)
    logger.info("main_finished", result=stats)

    # 3. Синхронизация ПОСЛЕ репрайсинга (если не dry-run и не отключена)
    if not args.no_sync and not args.dry_run:
        logger.info("Выполняем синхронизацию реальных цен из шаблона (после)...")
        stats_after = await sync_service.sync_real_prices_async(
            dry_run=False,
            keep_file=False,
            force_delete=False,
            use_lock=True,
        )
        if stats_after:
            logger.info(f"Синхронизация (после) завершена: {stats_after}")
        else:
            logger.warning("Синхронизация (после) не выполнена (возможно, занят lock или ошибка)")
    elif args.dry_run:
        logger.info("Синхронизация после репрайсинга пропущена (dry-run)")

    # 4. Закрытие API
    api = container.api_client()
    await api.close()


if __name__ == "__main__":
    asyncio.run(main())
