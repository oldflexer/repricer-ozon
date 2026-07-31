import asyncio
from typing import List, Dict, Tuple
from config.settings import settings
from infrastructure.logger import logger

class ActionService:
    def __init__(self, api_client):
        self.api = api_client

    async def get_all_auto_add_products(self) -> List[Tuple[int, str, int]]:
        """
        Получить все товары с автодобавлением.
        Возвращает: список кортежей (action_id, auto_add_date, product_id)
        """
        actions = await self.api.get_actions()
        results = []
        
        for action in actions:
            action_id = action.get('id')
            if not action_id:
                continue
            auto_add_dates = action.get('auto_add_dates', [])
            if not auto_add_dates:
                continue
            
            for auto_add_date in auto_add_dates:
                offset = 0
                limit = settings.API_BATCH_SIZE
                while True:
                    resp = await self.api.get_auto_add_products(
                        action_id, auto_add_date, limit, offset
                    )
                    products = resp.get('products', [])
                    if not products:
                        break
                    
                    for item in products:
                        product_id = item.get('product_id')
                        if product_id:
                            results.append((action_id, auto_add_date, product_id))
                    
                    # Если получено меньше, чем limit – это последняя страница
                    if len(products) < limit:
                        break
                    
                    offset += limit
                    await asyncio.sleep(settings.API_BATCH_DELAY)  # пауза между запросами
                
        return results

    async def disable_auto_add_for_products(self,
                                           products: List[Tuple[int, str, int]]) -> Dict:
        """
        Удалить автодобавление для списка товаров.
        Группирует по (action_id, auto_add_date) и отправляет батчами.
        """
        stats = {"deleted": 0, "errors": 0}
        
        # Группировка по (action_id, auto_add_date)
        groups = {}
        for action_id, auto_add_date, product_id in products:
            key = (action_id, auto_add_date)
            groups.setdefault(key, []).append(product_id)
        
        for (action_id, auto_add_date), product_ids in groups.items():
            # Разбиваем на батчи по 1000 (максимум согласно документации)
            for i in range(0, len(product_ids), 1000):
                batch = product_ids[i:i+1000]
                try:
                    resp = await self.api.delete_auto_add_products(
                        action_id, auto_add_date, batch
                    )
                    deleted = resp.get('product_ids', [])
                    stats["deleted"] += len(deleted)
                    if len(deleted) < len(batch):
                        stats["errors"] += (len(batch) - len(deleted))
                        logger.warning(
                            f"Не все товары удалены для акции {action_id}: "
                            f"запрошено {len(batch)}, удалено {len(deleted)}"
                        )
                except Exception as e:
                    stats["errors"] += len(batch)
                    logger.error(f"Ошибка удаления для акции {action_id}: {e}")
                
                await asyncio.sleep(0.2)
        
        return stats