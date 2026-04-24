import requests
import logging
from typing import List, Dict, Optional, Any, Tuple

from config.settings import OZON_CLIENT_ID, OZON_API_KEY, OZON_API_URL

logger = logging.getLogger(__name__)


class OzonApiClient:
    """Клиент для Ozon Seller API"""

    def __init__(self):
        self.base_url = OZON_API_URL
        self.headers = {
            'Client-Id': OZON_CLIENT_ID,
            'Api-Key': OZON_API_KEY,
            'Content-Type': 'application/json'
        }

    def get_product_ids_by_skus(self, skus: List[str]) -> Dict[str, dict]:
        """
        Возвращает словарь: sku -> {"product_id": int, "offer_id": str}
        """
        url = f"{self.base_url}/v3/product/info/list"
        payload = {"sku": skus}
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            result = {}
            for item in data.get('items', []):
                sku_val = str(item.get('sku'))
                result[sku_val] = {
                    'product_id': item.get('id'),
                    'offer_id': item.get('offer_id', '')
                }
            logger.info(f"Получены product_id для {len(result)}/{len(skus)} SKU")
            return result
        except Exception as e:
            logger.error(f"Ошибка получения product_id: {e}")
            return {}

    def update_prices(self, prices_data: List[Dict]) -> Tuple[bool, Optional[int]]:
        """
        Отправляет цены на Ozon.
        Возвращает (успех, HTTP-статус).
        """
        url = f"{self.base_url}/v1/product/import/prices"
        payload = {"prices": prices_data}

        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            status_code = response.status_code
            if status_code == 200:
                result = response.json()
                if result.get('result'):
                    logger.info(f"Цены успешно обновлены для {len(prices_data)} товаров")
                    return True, status_code
                else:
                    logger.error(f"Ошибка в ответе API: {result}")
                    return False, status_code
            else:
                logger.warning(f"Неожиданный статус {status_code}: {response.text[:200]}")
                return False, status_code
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при вызове Ozon API: {e}")
            return False, None