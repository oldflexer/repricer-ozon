"""
Клиент для Ozon Seller API.

Реализует методы для работы с товарами, ценами, индексами и акциями.
Поддерживает повторные попытки при ошибках и батчирование запросов.
"""

import asyncio
from typing import Any, Dict, List, Optional

import httpx

from config.settings import settings
from core.entities import PricingData
from infrastructure.http_retry import retry_on_error
from infrastructure.logger import logger


class OzonApiClient:
    """
    Асинхронный клиент для Ozon Seller API.

    Использует httpx.AsyncClient с настройками таймаута из конфигурации.
    """

    def __init__(self) -> None:
        """Инициализирует клиент с заголовками и HTTP-клиентом."""
        self.base_url = settings.OZON_API_URL
        self.headers = {
            "Client-Id": settings.OZON_CLIENT_ID,
            "Api-Key": settings.OZON_API_KEY,
            "Content-Type": "application/json",
        }
        self.client = httpx.AsyncClient(timeout=settings.API_HTTP_TIMEOUT)

    async def close(self) -> None:
        """Закрывает HTTP-клиент."""
        await self.client.aclose()

    # ------------------------------------------------------------------
    # Базовые HTTP-методы с повторными попытками
    # ------------------------------------------------------------------

    @retry_on_error(max_retries=settings.API_MAX_RETRIES)
    async def _get(self, url: str) -> Optional[dict]:
        """
        Выполняет GET-запрос с повторными попытками.

        Args:
            url: Полный URL для запроса.
            max_retries: Максимальное количество попыток.

        Returns:
            Ответ в виде словаря или None при ошибке.
        """
        resp = await self.client.get(url, headers=self.headers)
        if resp.status_code == 200:
            return resp.json()
        logger.warning(f"GET {url} returned {resp.status_code}, body: {resp.text[:500]}")
        return None

    @retry_on_error(max_retries=settings.API_MAX_RETRIES)
    async def _post(self, url: str, payload: Any) -> Optional[dict]:
        """
        Выполняет POST-запрос с повторными попытками.

        Args:
            url: Полный URL для запроса.
            payload: Данные для отправки (JSON-сериализуемые).
            max_retries: Максимальное количество попыток.

        Returns:
            Ответ в виде словаря или None при ошибке.
        """
        resp = await self.client.post(url, headers=self.headers, json=payload)
        if resp.status_code == 200:
            return resp.json()
        logger.warning(f"POST {url} returned {resp.status_code}, body: {resp.text[:500]}")
        return None

    # ------------------------------------------------------------------
    # Методы для работы с товарами и ценами
    # ------------------------------------------------------------------

    async def get_product_ids_by_skus(self, skus: List[str]) -> Dict[str, dict]:
        """
        Получает product_id, offer_id и название для списка SKU.

        Использует /v3/product/info/list с батчированием.

        Args:
            skus: Список SKU (артикулов продавца).

        Returns:
            Словарь {sku: {product_id, offer_id, price, product_name}}.
        """
        url = f"{self.base_url}/v3/product/info/list"
        result = {}
        batch_size = settings.API_BATCH_SIZE
        unique_skus = list({str(sku).strip() for sku in skus if sku})

        for i in range(0, len(unique_skus), batch_size):
            batch = unique_skus[i:i + batch_size]
            payload = {"sku": batch}
            resp_data = await self._post(url, payload)
            if resp_data and "items" in resp_data:
                for item in resp_data["items"]:
                    sku = str(item.get("sku", ""))
                    if sku:
                        result[sku] = {
                            "product_id": item.get("id"),
                            "offer_id": item.get("offer_id", ""),
                            "price": float(item.get("price", 0)) if item.get("price") else None,
                            "product_name": item.get("name"),
                        }
            await asyncio.sleep(settings.API_BATCH_DELAY)

        logger.info(f"Получены product_id для {len(result)}/{len(unique_skus)} SKU")
        return result

    async def get_product_prices(self, product_ids: List[int]) -> List[PricingData]:
        """
        Получает цены, индексы и комиссии для списка товаров.

        Использует /v5/product/info/prices с батчированием.

        Args:
            product_ids: Список идентификаторов товаров в Ozon.

        Returns:
            Список объектов PricingData.
        """
        url = f"{self.base_url}/v5/product/info/prices"
        all_prices = []
        batch_size = settings.API_BATCH_SIZE

        for i in range(0, len(product_ids), batch_size):
            batch = product_ids[i:i + batch_size]
            payload = {"filter": {"product_id": batch}, "limit": batch_size}
            resp_data = await self._post(url, payload)
            if resp_data and "items" in resp_data:
                for item in resp_data["items"]:
                    all_prices.append(PricingData.from_api_response(item))
            await asyncio.sleep(settings.API_BATCH_DELAY)

        return all_prices

    async def update_prices(self, prices_data: List[Dict]) -> Dict[int, Dict]:
        """
        Отправляет новые цены в Ozon.

        Использует /v1/product/import/prices.

        Args:
            prices_data: Список словарей с полями:
                product_id, offer_id, price, min_price, net_price,
                old_price, manage_elastic_boosting_through_price.

        Returns:
            Словарь {product_id: {"updated": bool, "errors": list}}.
        """
        url = f"{self.base_url}/v1/product/import/prices"
        payload = {"prices": prices_data}
        result_map = {}

        try:
            resp = await self.client.post(url, headers=self.headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                if "result" in data:
                    for item in data["result"]:
                        pid = item.get("product_id")
                        result_map[pid] = {
                            "updated": item.get("updated", False),
                            "errors": item.get("errors", []),
                        }
                else:
                    logger.warning(f"Неожиданный ответ: {data}")
                    for item in prices_data:
                        result_map[item["product_id"]] = {
                            "updated": False,
                            "errors": [{"code": "UNKNOWN", "message": "Неожиданный ответ API"}],
                        }
            else:
                logger.warning(
                    f"Update prices failed: {resp.status_code} {resp.text[:200]}"
                )
                for item in prices_data:
                    result_map[item["product_id"]] = {
                        "updated": False,
                        "errors": [{"code": "HTTP_ERROR", "message": f"HTTP {resp.status_code}"}],
                    }
        except Exception as e:
            logger.error(f"Update error: {e}")
            for item in prices_data:
                result_map[item["product_id"]] = {
                    "updated": False,
                    "errors": [{"code": "EXCEPTION", "message": str(e)}],
                }

        return result_map

    # ------------------------------------------------------------------
    # Методы для работы с акциями (автодобавление)
    # ------------------------------------------------------------------

    async def get_actions(self) -> List[Dict]:
        """
        Получает список всех доступных акций.

        Использует GET /v1/actions.

        Returns:
            Список акций (словарей).
        """
        url = f"{self.base_url}/v1/actions"
        resp = await self._get(url)
        return resp.get("result", []) if resp else []

    async def get_auto_add_products(
        self, action_id: int, auto_add_date: str, limit: int = 100, offset: int = 0
    ) -> Dict:
        """
        Получает список товаров с автодобавлением для конкретной акции.

        Использует POST /v1/actions/auto-add/products/list.

        Args:
            action_id: ID акции.
            auto_add_date: Дата автодобавления (строка).
            limit: Количество записей на страницу.
            offset: Смещение для пагинации.

        Returns:
            Словарь с ключом "products" (список товаров).
        """
        url = f"{self.base_url}/v1/actions/auto-add/products/list"
        payload = {
            "action_id": action_id,
            "auto_add_date": auto_add_date,
            "limit": limit,
            "offset": offset,
        }
        return await self._post(url, payload) or {}

    async def delete_auto_add_products(
        self, action_id: int, auto_add_date: str, product_ids: List[int]
    ) -> Dict:
        """
        Удаляет товары из автодобавления в акцию.

        Использует POST /v1/actions/auto-add/products/delete.

        Args:
            action_id: ID акции.
            auto_add_date: Дата автодобавления.
            product_ids: Список идентификаторов товаров.

        Returns:
            Словарь с ключом "product_ids" (список удалённых ID).
        """
        url = f"{self.base_url}/v1/actions/auto-add/products/delete"
        payload = {
            "action_id": action_id,
            "auto_add_date": auto_add_date,
            "product_ids": [str(pid) for pid in product_ids],
        }
        return await self._post(url, payload) or {}

    async def update_price_timer(self, product_ids: List[int]) -> Dict[int, Dict]:
        """
        Обновляет таймер актуальности минимальной цены для указанных товаров.

        Эндпоинт: POST /v1/product/action/timer/update

        Args:
            product_ids: Список product_id (макс. 1000 элементов).

        Returns:
            Словарь {product_id: {"success": bool, "error": Optional[str]}}.
        """
        url = f"{self.base_url}/v1/product/action/timer/update"
        result_map = {}

        # API принимает не более 1000 ID за раз
        batch_size = 1000
        for i in range(0, len(product_ids), batch_size):
            batch = product_ids[i:i + batch_size]
            payload = {"product_ids": batch}

            try:
                resp = await self.client.post(url, headers=self.headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    if "result" in data:
                        for item in data["result"]:
                            pid = item.get("product_id")
                            error = item.get("error")
                            result_map[pid] = {
                                "success": error is None,
                                "error": error
                            }
                    else:
                        logger.warning(f"Unexpected response structure: {data}")
                        for pid in batch:
                            result_map[pid] = {"success": True, "error": None}
                else:
                    logger.warning(
                        f"Update price timer failed: {resp.status_code} {resp.text[:200]}"
                    )
                    for pid in batch:
                        result_map[pid] = {
                            "success": False,
                            "error": f"HTTP {resp.status_code}"
                        }
            except Exception as e:
                logger.error(f"Update price timer error: {e}")
                for pid in batch:
                    result_map[pid] = {
                        "success": False,
                        "error": str(e)
                    }

            # Пауза между батчами, чтобы не перегружать API
            if i + batch_size < len(product_ids):
                await asyncio.sleep(settings.API_BATCH_DELAY)

        return result_map