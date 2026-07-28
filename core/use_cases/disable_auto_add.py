from typing import Dict

from core.services import ActionService
from infrastructure.logger import logger

class DisableAutoAddUseCase:
    def __init__(self, api_client):
        self.service = ActionService(api_client)

    async def execute(self, dry_run: bool = False) -> Dict:
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