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
from scripts.common import register_signal_handlers, setup_script_logging

logger = setup_script_logging("repricer")


async def main() -> None:
    register_signal_handlers()

    parser = argparse.ArgumentParser(description="Запуск репрайсинга товаров")
    parser.add_argument(
        "--dry-run", action="store_true", help="Тестовый режим: расчёт без отправки цен"
    )
    args = parser.parse_args()

    # Запуск репрайсинга (синхронизация цен теперь встроена в pipeline)
    use_case = container.repricing_use_case()
    stats = await use_case.execute(dry_run=args.dry_run)
    logger.info("main_finished", result=stats)

    # Закрытие API
    api = container.api_client()
    await api.close()


if __name__ == "__main__":
    asyncio.run(main())
