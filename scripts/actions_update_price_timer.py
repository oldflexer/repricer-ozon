#!/usr/bin/env python3
"""
Обновление таймера актуальности минимальной цены для товаров.

Использование:
    python scripts/actions_update_price_timer.py --product-ids 123456,789012,345678
    python scripts/actions_update_price_timer.py --all   # обновить для всех товаров в БД
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from core.container import container
from core.use_cases.update_price_timer import UpdatePriceTimerUseCase
from infrastructure.db import SQLiteRepository
from scripts.common import register_signal_handlers, setup_script_logging

logger = setup_script_logging("update_price_timer")


def parse_product_ids(arg: str) -> list[int]:
    return [int(x.strip()) for x in arg.split(",") if x.strip()]


async def main() -> None:
    register_signal_handlers()

    parser = argparse.ArgumentParser(description="Обновление таймера актуальности минимальной цены")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--product-ids", type=str, help="Список product_id через запятую (например, 123456,789012)"
    )
    group.add_argument("--all", action="store_true", help="Обновить для всех товаров в базе данных")
    args = parser.parse_args()

    if args.all:
        repo = SQLiteRepository(settings.database_path_path)
        products = repo.get_all_products()
        product_ids = [p.product_id for p in products if p.product_id]
        logger.info(f"Загружено {len(product_ids)} товаров из БД")
    else:
        product_ids = parse_product_ids(args.product_ids)
        logger.info(f"Получено {len(product_ids)} product_id из аргументов")

    if not product_ids:
        logger.error("Нет product_id для обновления")
        sys.exit(1)

    api = container.api_client
    use_case = UpdatePriceTimerUseCase(api)

    try:
        stats = await use_case.execute(product_ids)
        logger.info(f"Результат: {stats}")
    finally:
        await api.close()


if __name__ == "__main__":
    asyncio.run(main())
