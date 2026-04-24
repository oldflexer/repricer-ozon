import time
import logging
from typing import List, Dict, Optional, Tuple

from src.ozon_api import OzonApiClient
from src.database import Database
from src.loader import DataLoader

logger = logging.getLogger(__name__)


class PriceUpdater:
    """Отправка цен в Ozon (с защитой от ошибок лимитов) и обязательное сохранение результатов локально."""

    def __init__(self, db: Database, loader: DataLoader, dry_run: bool = False):
        self.db = db
        self.loader = loader
        self.dry_run = dry_run
        self.api_client = OzonApiClient()

    def _send_prices_with_retry(self, prices_data: List[Dict], max_retries: int = 3) -> bool:
        """Отправляет цены в Ozon API с автоматическим повтором при ошибке 429."""
        for attempt in range(max_retries):
            success, status_code = self.api_client.update_prices(prices_data)
            if success:
                return True
            elif status_code == 429:
                wait_time = 2 ** attempt
                logger.warning(f"Сработал лимит запросов (429). Повторная попытка через {wait_time} сек.")
                time.sleep(wait_time)
            else:
                break
        return False

    def update(
        self,
        updates_for_ozon: List[Dict],
        margin_items: List[Dict]
    ) -> Dict:
        stats = {'prices_updated': 0, 'errors': []}

        if not updates_for_ozon:
            logger.warning("Нет данных для обработки")
            return stats

        # Всегда сохраняем локально
        for item in margin_items:
            self._save_locally(item)
        stats['prices_updated'] = len(updates_for_ozon)

        if self.dry_run:
            logger.info("DRY-RUN: локальное сохранение выполнено, отправка пропущена")
            return stats

        # Отправка с повторами
        logger.info(f"Отправка {len(updates_for_ozon)} цен в Ozon")
        success = self._send_prices_with_retry(updates_for_ozon)
        if not success:
            stats['errors'].append("Ошибка при отправке цен в Ozon API")
            logger.warning("Не удалось отправить цены, но локальные данные уже сохранены")

        return stats

    def _save_locally(self, item: Dict):
        sku = item['sku']
        target_price = item['target_price']
        margin = item['margin']

        self.db.save_price_record(sku, target_price, margin)

        updates = {
            'current_price': target_price,
            'margin': margin,
            'margin_week': self.db.get_average_margin(sku, 7),
            'margin_month': self.db.get_average_margin(sku, 30),
        }
        self.loader.update_product_in_file(sku, updates)