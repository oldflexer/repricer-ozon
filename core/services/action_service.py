"""
Сервис для работы с акциями Ozon (автодобавление товаров).

Позволяет получить список товаров с автодобавлением и отключить его.
"""

import asyncio
from typing import Callable, Optional

from config.settings import settings
from core.protocols.api import IApiClient
from infrastructure.logger import logger


class ActionService:
    """Сервис для управления автодобавлением товаров в акции Ozon."""

    def __init__(self, api_client: IApiClient) -> None:
        """
        Инициализирует сервис.

        Args:
            api_client: Клиент Ozon API (должен содержать методы
                get_actions, get_auto_add_products, delete_auto_add_products).
        """
        self.api = api_client

    async def get_all_auto_add_products(
        self,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> list[tuple[int, str, int]]:
        """
        Получает все товары, у которых включено автодобавление в акции.

        Обходит все акции и даты автодобавления, используя пагинацию.

        Args:
            progress_callback: Опциональный колбэк для отображения прогресса (current, total, message).

        Returns:
            Список кортежей (action_id, auto_add_date, product_id).
        """
        actions = await self.api.get_actions()
        results = []

        # First, count total products for progress tracking
        total_products = 0
        for action in actions:
            action_id = action.get("id")
            if not action_id:
                continue
            auto_add_dates = action.get("auto_add_dates", [])
            if not auto_add_dates:
                continue
            for auto_add_date in auto_add_dates:
                # We can't easily count without fetching, so we'll track as we go
                pass

        current_product = 0

        for action in actions:
            action_id = action.get("id")
            if not action_id:
                continue
            auto_add_dates = action.get("auto_add_dates", [])
            if not auto_add_dates:
                continue

            for auto_add_date in auto_add_dates:
                offset = 0
                limit = settings.API_BATCH_SIZE
                while True:
                    resp = await self.api.get_auto_add_products(
                        action_id, auto_add_date, limit, offset
                    )
                    products = resp.get("products", [])
                    if not products:
                        break

                    for item in products:
                        product_id = item.get("product_id")
                        if product_id:
                            results.append((action_id, auto_add_date, product_id))
                            current_product += 1
                            if progress_callback:
                                progress_callback(
                                    current_product,
                                    len(results),  # Use current count as total since we don't know ahead
                                    f"Получение товаров с автодобавлением: {current_product} найдено",
                                )

                    # Если получено меньше, чем limit – это последняя страница
                    if len(products) < limit:
                        break

                    offset += limit
                    await asyncio.sleep(settings.API_BATCH_DELAY)

        return results

    async def disable_auto_add_for_products(
        self,
        products: list[tuple[int, str, int]],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> dict[str, int]:
        """
        Отключает автодобавление для переданного списка товаров.

        Группирует товары по (action_id, auto_add_date) и отправляет запросы
        на удаление батчами (максимум 1000 товаров за раз).

        Args:
            products: Список кортежей (action_id, auto_add_date, product_id).
            progress_callback: Опциональный колбэк для отображения прогресса (current, total, message).

        Returns:
            Словарь со статистикой: {"deleted": int, "errors": int}.
        """
        stats = {"deleted": 0, "errors": 0}

        # Группировка по (action_id, auto_add_date)
        groups: dict[tuple[int, str], list[int]] = {}
        for action_id, auto_add_date, product_id in products:
            key = (action_id, auto_add_date)
            groups.setdefault(key, []).append(product_id)

        # Максимальный размер батча согласно документации Ozon
        batch_size = 1000

        total_products = len(products)
        current_product = 0

        for (action_id, auto_add_date), product_ids in groups.items():
            # Разбиваем на батчи по BATCH_SIZE
            for i in range(0, len(product_ids), batch_size):
                batch = product_ids[i : i + batch_size]
                try:
                    resp = await self.api.delete_auto_add_products(action_id, auto_add_date, batch)
                    deleted = resp.get("product_ids", [])
                    stats["deleted"] += len(deleted)
                    current_product += len(batch)
                    if progress_callback:
                        progress_callback(
                            current_product,
                            total_products,
                            f"Отключение автодобавления: {current_product}/{total_products}",
                        )
                    if len(deleted) < len(batch):
                        stats["errors"] += len(batch) - len(deleted)
                        logger.warning(
                            f"Не все товары удалены для акции {action_id}: "
                            f"запрошено {len(batch)}, удалено {len(deleted)}"
                        )
                except Exception as e:
                    stats["errors"] += len(batch)
                    current_product += len(batch)
                    if progress_callback:
                        progress_callback(
                            current_product,
                            total_products,
                            f"Отключение автодобавления: {current_product}/{total_products}",
                        )
                    logger.error(f"Ошибка удаления для акции {action_id}: {e}")

                await asyncio.sleep(settings.API_BATCH_DELAY)

        return stats
