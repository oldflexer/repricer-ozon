"""
Use‑case для обновления таймера актуальности минимальной цены.
"""

from typing import Dict, List

from infrastructure.logger import logger


class UpdatePriceTimerUseCase:
    def __init__(self, api_client):
        self.api = api_client

    async def execute(self, product_ids: List[int]) -> Dict[str, int]:
        """
        Выполняет обновление таймера для списка товаров.

        Args:
            product_ids: Список product_id.

        Returns:
            Словарь со статистикой: {"success": N, "failed": N}.
        """
        if not product_ids:
            logger.warning("Список product_ids пуст")
            return {"success": 0, "failed": 0}

        logger.info(f"Обновление таймера для {len(product_ids)} товаров...")
        results = await self.api.update_price_timer(product_ids)

        success_count = sum(1 for r in results.values() if r.get("success"))
        failed_count = len(results) - success_count

        if failed_count:
            errors = [
                f"{pid}: {r['error']}"
                for pid, r in results.items()
                if not r.get("success")
            ]
            logger.warning(f"Ошибки обновления таймера: {errors}")

        logger.info(f"Обновление таймера завершено: успешно {success_count}, ошибок {failed_count}")
        return {"success": success_count, "failed": failed_count}