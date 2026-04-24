import logging
from typing import List, Dict, Optional

from src.ozon_api import OzonApiClient
from src.database import Database
from src.loader import DataLoader

logger = logging.getLogger(__name__)


class PriceUpdater:
    """Отправка цен в Ozon (опционально) и обязательное сохранение результатов локально."""

    def __init__(self, db: Database, loader: DataLoader, dry_run: bool = False):
        self.db = db
        self.loader = loader
        self.dry_run = dry_run
        self.api_client = OzonApiClient()

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

        # Отправляем на Ozon, только если не dry_run
        if not self.dry_run:
            logger.info(f"Отправка {len(updates_for_ozon)} цен в Ozon")
            success = self.api_client.update_prices(updates_for_ozon)
            if not success:
                stats['errors'].append("Ошибка при отправке цен в Ozon API")
                logger.warning("Не удалось отправить цены, но локальные данные уже сохранены")
        else:
            logger.info("DRY-RUN: цены сохранены локально, отправка пропущена")

        return stats

    def _save_locally(self, item: Dict):
        offer_id = item['offer_id']
        target_price = item['target_price']
        margin = item['margin']

        self.db.save_price_record(offer_id, target_price, margin)

        updates = {
            'current_price': target_price,
            'margin': margin,
            'margin_week': self.db.get_average_margin(offer_id, 7),
            'margin_month': self.db.get_average_margin(offer_id, 30),
        }
        self.loader.update_product_in_file(offer_id, updates)