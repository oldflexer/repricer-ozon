import requests
import logging
from typing import List, Dict, Optional
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

    def update_prices(self, prices_data: List[Dict]) -> bool:
        """
        Отправляет цены на Ozon.

        prices_data: список словарей вида:
        [
            {
                "offer_id": "12345",
                "price": "1990.00",
                "old_price": "2490.00",
                "min_price": "1500.00"
            },
            ...
        ]

        Возвращает True при успехе, иначе False.
        """
        url = f"{self.base_url}/v1/product/import/prices"
        payload = {"prices": prices_data}

        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()

            if result.get('result'):
                logger.info(f"Цены успешно обновлены для {len(prices_data)} товаров")
                return True
            else:
                logger.error(f"Ошибка в ответе API: {result}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при вызове Ozon API: {e}")
            return False

    def get_product_info(self, offer_ids: List[str]) -> Optional[Dict]:
        """
        Получает информацию о товарах (опционально, может пригодиться).
        """
        url = f"{self.base_url}/v2/product/info/list"
        payload = {"offer_id": offer_ids}

        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Ошибка получения информации о товарах: {e}")
            return None