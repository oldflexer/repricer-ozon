"""
Use‑case для обновления таймера актуальности минимальной цены.
"""

from typing import Callable, Optional

from infrastructure.logger import logger
from infrastructure.ozon_api import OzonApiClient


class UpdatePriceTimerUseCase:
    def __init__(self, api_client: OzonApiClient) -> None:
        self.api = api_client

    async def execute(
        self,
        product_ids: list[int],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> dict[str, int]:
        """
        Выполняет обновление таймера для списка товаров.

        Args:
            product_ids: Список product_id.
            progress_callback: Опциональный колбэк для отображения прогресса (current, total, message).

        Returns:
            Словарь со статистикой: {"success": N, "failed": N}.
        """
        if not product_ids:
            logger.warning("Список product_ids пуст")
            return {"success": 0, "failed": 0}

        logger.info(f"Обновление таймера для {len(product_ids)} товаров...")
        results = await self.api.update_price_timer(product_ids)

        success_count = 0
        failed_count = 0
        total = len(product_ids)

        for i, (pid, result) in enumerate(results.items(), 1):
            if result.get("success"):
                success_count += 1
            else:
                failed_count += 1

            if progress_callback:
                progress_callback(i, total, f"Обновление таймера: {i}/{total}")

        if failed_count:
            errors = [f"{pid}: {r['error']}" for pid, r in results.items() if not r.get("success")]
            logger.warning(f"Ошибки обновления таймера: {errors}")

        logger.info(f"Обновление таймера завершено: успешно {success_count}, ошибок {failed_count}")
        return {"success": success_count, "failed": failed_count}
