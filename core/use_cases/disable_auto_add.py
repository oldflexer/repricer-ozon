"""
Use‑case для отключения автодобавления товаров в акции Ozon.

Выполняет получение списка всех товаров с активным автодобавлением
через Ozon API и удаляет их (или показывает, сколько будет удалено, в dry‑run).
"""

from core.services import ActionService
from infrastructure.logger import logger
from infrastructure.ozon_api import OzonApiClient


class DisableAutoAddUseCase:
    """
    Use‑case для отключения автодобавления в акции.

    Использует ActionService для получения всех товаров с автодобавлением
    и последующего удаления.
    """

    def __init__(self, api_client: OzonApiClient) -> None:
        """
        Инициализирует use‑case.

        Args:
            api_client: Клиент Ozon API (OzonApiClient).
        """
        self.service = ActionService(api_client)

    async def execute(self, dry_run: bool = False) -> dict[str, int]:
        """
        Запускает процесс отключения автодобавления.

        Args:
            dry_run: Если True, только выводит количество найденных записей,
                     не выполняя фактического удаления.

        Returns:
            Словарь со статистикой:
                - found: количество найденных записей (всегда равно len(products)).
                - deleted: количество реально удалённых записей.
                - errors: количество ошибок при удалении.
        """
        logger.info("=== Запуск отключения автодобавления в акции ===")

        # 1. Получаем все товары с автодобавлением
        products = await self.service.get_all_auto_add_products()
        logger.info(f"Найдено товаров с автодобавлением: {len(products)}")

        if dry_run:
            logger.info(f"DRY-RUN: будет удалено {len(products)} записей")
            return {"found": len(products), "deleted": 0, "errors": 0}

        # 2. Удаляем автодобавление
        stats = await self.service.disable_auto_add_for_products(products)
        logger.info(f"=== Завершено. Удалено: {stats['deleted']}, ошибок: {stats['errors']} ===")

        return stats
