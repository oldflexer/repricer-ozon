import requests
import logging
import time
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
        Возвращает словарь: sku -> {"product_id": int, "offer_id": str, "price": float}
        """
        url = f"{self.base_url}/v3/product/info/list"
        result = {}

        for sku in skus:
            sku_str = str(sku).strip()
            if not sku_str:
                continue
            payload = {"sku": [sku_str]}
            response = None
            try:
                response = requests.post(url, headers=self.headers, json=payload, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('items', [])
                    if items:
                        item = items[0]
                        price_val = None
                        price_str = item.get('price')
                        if price_str:
                            try:
                                price_val = float(price_str)
                            except ValueError:
                                pass
                        result[sku_str] = {
                            'product_id': item.get('id'),
                            'offer_id': item.get('offer_id', ''),
                            'price': price_val
                        }
                    else:
                        logger.warning(f"SKU {sku_str}: товар не найден в ответе")
                else:
                    logger.warning(f"SKU {sku_str}: статус {response.status_code}")
            except Exception as e:
                logger.error(f"SKU {sku_str}: ошибка запроса — {e}")
            time.sleep(0.1)

        logger.info(f"Получены product_id для {len(result)}/{len(skus)} SKU")
        return result

    def update_prices(self, prices_data: List[Dict]) -> Tuple[bool, Optional[int]]:
        """
        Отправляет цены на Ozon.
        Возвращает (успех, HTTP-статус).
        """
        url = f"{self.base_url}/v1/product/import/prices"
        payload = {"prices": prices_data}

        logger.debug(f"Отправка цен: URL={url}, payload={payload}")
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            status_code = response.status_code
            logger.debug(f"Ответ: статус={status_code}, тело={response.text[:500]}")
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