import requests
import logging
import time
from typing import List, Dict, Optional, Any

from config.settings import OZON_CLIENT_ID, OZON_API_KEY, OZON_API_URL
from core.entities import PricingData

logger = logging.getLogger(__name__)


class OzonApiClient:
    def __init__(self):
        self.base_url = OZON_API_URL
        self.headers = {
            'Client-Id': OZON_CLIENT_ID,
            'Api-Key': OZON_API_KEY,
            'Content-Type': 'application/json'
        }

    # ----------------------------------------------------------------
    # Получение product_id, offer_id, product_name по SKU
    # ----------------------------------------------------------------
    def get_product_ids_by_skus(self, skus: List[str]) -> Dict[str, dict]:
        url = f"{self.base_url}/v3/product/info/list"
        result = {}
        batch_size = 100
        unique_skus = list({str(sku).strip() for sku in skus if sku})
        for i in range(0, len(unique_skus), batch_size):
            batch = unique_skus[i:i+batch_size]
            payload = {"sku": batch}
            try:
                resp = self._post(url, payload)
                if resp and 'items' in resp:
                    for item in resp['items']:
                        sku = str(item.get('sku', ''))
                        if sku:
                            result[sku] = {
                                'product_id': item.get('id'),
                                'offer_id': item.get('offer_id', ''),
                                'price': float(item.get('price', 0)) if item.get('price') else None,
                                'product_name': item.get('name')
                            }
                else:
                    logger.warning(f"Неожиданный ответ от API: {resp}")
            except Exception as e:
                logger.error(f"Ошибка batch SKU: {e}")
            time.sleep(0.1)
        logger.info(f"Получены product_id для {len(result)}/{len(unique_skus)} SKU")
        return result

    # ----------------------------------------------------------------
    # Получение цен по product_id
    # ----------------------------------------------------------------
    def get_product_prices(self, product_ids: List[int]) -> List[PricingData]:
        url = f"{self.base_url}/v5/product/info/prices"
        all_prices = []
        batch_size = 100
        for i in range(0, len(product_ids), batch_size):
            batch = product_ids[i:i+batch_size]
            payload = {"filter": {"product_id": batch}, "limit": batch_size}
            try:
                resp = self._post(url, payload)
                if resp and 'items' in resp:
                    for item in resp['items']:
                        all_prices.append(PricingData.from_api_response(item))
                else:
                    logger.warning(f"Неожиданный ответ от API цен: {resp}")
            except Exception as e:
                logger.error(f"Ошибка batch prices: {e}")
            time.sleep(0.2)
        return all_prices

    # ----------------------------------------------------------------
    # Отправка цен с детальным ответом по каждому товару
    # ----------------------------------------------------------------
    def update_prices(self, prices_data: List[Dict]) -> Dict[int, Dict]:
        """
        Отправляет цены в Ozon API.
        Возвращает словарь: { product_id: {'updated': bool, 'errors': list} }
        """
        url = f"{self.base_url}/v1/product/import/prices"
        payload: dict[str, Any] = {"prices": prices_data}
        result_map = {}
        try:
            resp = requests.post(url, headers=self.headers, json=payload, timeout=30)
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

    # ----------------------------------------------------------------
    # Общий POST с повторными попытками
    # ----------------------------------------------------------------
    def _post(self, url: str, payload: Any) -> Optional[dict]:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                resp = requests.post(url, headers=self.headers, json=payload, timeout=30)
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(f"POST {url} returned {resp.status_code}, body: {resp.text[:500]}, attempt {attempt+1}")
                time.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"POST error: {e}, attempt {attempt+1}")
                time.sleep(2 ** attempt)
        return None