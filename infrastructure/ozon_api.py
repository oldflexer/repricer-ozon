import asyncio
from typing import List, Dict, Optional, Any
import httpx

from config.settings import settings
from core.entities import PricingData
from infrastructure.logger import logger


class OzonApiClient:
    def __init__(self):
        self.base_url = settings.OZON_API_URL
        self.headers = {
            'Client-Id': settings.OZON_CLIENT_ID,
            'Api-Key': settings.OZON_API_KEY,
            'Content-Type': 'application/json'
        }
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def _get(self, url: str, max_retries: int = 3) -> Optional[dict]:
        """Выполняет GET-запрос с повторными попытками."""
        for attempt in range(max_retries):
            try:
                resp = await self.client.get(url, headers=self.headers)
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(f"GET {url} returned {resp.status_code}, body: {resp.text[:500]}, attempt {attempt+1}")
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"GET error: {e}, attempt {attempt+1}")
                await asyncio.sleep(2 ** attempt)
        return None

    async def _post(self, url: str, payload: Any, max_retries: int = 3) -> Optional[dict]:
        for attempt in range(max_retries):
            try:
                resp = await self.client.post(url, headers=self.headers, json=payload)
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(f"POST {url} returned {resp.status_code}, body: {resp.text[:500]}, attempt {attempt+1}")
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"POST error: {e}, attempt {attempt+1}")
                await asyncio.sleep(2 ** attempt)
        return None

    async def get_product_ids_by_skus(self, skus: List[str]) -> Dict[str, dict]:
        url = f"{self.base_url}/v3/product/info/list"
        result = {}
        batch_size = 100
        unique_skus = list({str(sku).strip() for sku in skus if sku})
        for i in range(0, len(unique_skus), batch_size):
            batch = unique_skus[i:i+batch_size]
            payload = {"sku": batch}
            resp_data = await self._post(url, payload)
            if resp_data and 'items' in resp_data:
                for item in resp_data['items']:
                    sku = str(item.get('sku', ''))
                    if sku:
                        result[sku] = {
                            'product_id': item.get('id'),
                            'offer_id': item.get('offer_id', ''),
                            'price': float(item.get('price', 0)) if item.get('price') else None,
                            'product_name': item.get('name')
                        }
            await asyncio.sleep(0.1)
        logger.info(f"Получены product_id для {len(result)}/{len(unique_skus)} SKU")
        return result

    async def get_product_prices(self, product_ids: List[int]) -> List[PricingData]:
        """
        Получает цены, индексы и комиссии для списка товаров.
        
        :param product_ids: Список идентификаторов товаров в Ozon.
        :return: Список объектов PricingData с информацией о ценах.
        """
        url = f"{self.base_url}/v5/product/info/prices"
        all_prices = []
        batch_size = 100
        for i in range(0, len(product_ids), batch_size):
            batch = product_ids[i:i+batch_size]
            payload = {"filter": {"product_id": batch}, "limit": batch_size}
            resp_data = await self._post(url, payload)
            if resp_data and 'items' in resp_data:
                for item in resp_data['items']:
                    all_prices.append(PricingData.from_api_response(item))
            await asyncio.sleep(0.2)
        return all_prices

    async def update_prices(self, prices_data: List[Dict]) -> Dict[int, Dict]:
        """
        Отправляет новые цены в Ozon.
        
        :param prices_data: Список словарей с данными для обновления (product_id, price, min_price и т.д.)
        :return: Словарь {product_id: {'updated': bool, 'errors': list}}.
        """
        url = f"{self.base_url}/v1/product/import/prices"
        payload = {"prices": prices_data}
        result_map = {}
        try:
            resp = await self.client.post(url, headers=self.headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                if 'result' in data:
                    for item in data['result']:
                        pid = item.get('product_id')
                        result_map[pid] = {
                            'updated': item.get('updated', False),
                            'errors': item.get('errors', [])
                        }
                else:
                    logger.warning(f"Неожиданный ответ: {data}")
                    for item in prices_data:
                        result_map[item['product_id']] = {'updated': False, 'errors': [{'code': 'UNKNOWN', 'message': 'Неожиданный ответ API'}]}
            else:
                logger.warning(f"Update prices failed: {resp.status_code} {resp.text[:200]}")
                for item in prices_data:
                    result_map[item['product_id']] = {'updated': False, 'errors': [{'code': 'HTTP_ERROR', 'message': f'HTTP {resp.status_code}'}]}
        except Exception as e:
            logger.error(f"Update error: {e}")
            for item in prices_data:
                result_map[item['product_id']] = {'updated': False, 'errors': [{'code': 'EXCEPTION', 'message': str(e)}]}
        return result_map

    async def get_actions(self) -> List[Dict]:
        """Получить список всех доступных акций (/v1/actions)."""
        url = f"{self.base_url}/v1/actions"
        resp = await self._get(url)
        return resp.get('result', []) if resp else []

    async def get_auto_add_products(self, action_id: int, auto_add_date: str,
                                    limit: int = 100, offset: int = 0) -> Dict:
        """Получить список товаров с автодобавлением для конкретной акции."""
        url = f"{self.base_url}/v1/actions/auto-add/products/list"
        payload = {
            "action_id": action_id,
            "auto_add_date": auto_add_date,
            "limit": limit,
            "offset": offset
        }
        return await self._post(url, payload) or {}

    async def delete_auto_add_products(self, action_id: int, auto_add_date: str,
                                    product_ids: List[int]) -> Dict:
        """Удалить товары из автодобавления в акцию."""
        url = f"{self.base_url}/v1/actions/auto-add/products/delete"
        payload = {
            "action_id": action_id,
            "auto_add_date": auto_add_date,
            "product_ids": [str(pid) for pid in product_ids]  # документация требует строки
        }
        return await self._post(url, payload) or {}