import logging
from typing import List, Dict, Optional, Tuple

from src.calculator import PriceCalculator, MarginCalculator
from src.database import Database

logger = logging.getLogger(__name__)


class PriceMaker:
    """Расчёт цен на основе актуальных данных в БД (без отправки и записи в Excel)."""

    def __init__(self, db: Database):
        self.db = db
        self.calculator = PriceCalculator()
        self.margin_calc = MarginCalculator(db)

    def calculate(
        self,
        products: List[Dict],
        real_prices: Dict[str, Optional[float]]
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Возвращает кортеж:
        - updates_for_ozon: список словарей для отправки в Ozon API
        - margin_items: список словарей с offer_id, target_price, margin для сохранения истории и обновления Excel
        """
        updates_for_ozon = []
        margin_items = []

        for product in products:
            offer_id = product['offer_id']
            real_price = real_prices.get(offer_id)
            if real_price is None:
                real_price = product.get('current_price')

            # Последние цены конкурентов из БД
            comps = self.db.get_competitors_for_product(offer_id)
            competitor_prices = []
            for c in comps:
                hist = self.db.get_competitor_price_history(c['id'])
                if hist:
                    competitor_prices.append(hist[-1]['price'])

            min_price = product.get('min_price', 0.0)
            intervals = product['intervals']

            target_price = self.calculator.calculate_target_price(
                competitor_prices=competitor_prices,
                intervals=intervals,
                min_price=min_price,
                real_price=real_price
            )

            cost_price = product.get('cost_price', 0.0)
            current_margin = self.margin_calc.calculate_margin(target_price, cost_price)

            logger.info(
                f"Товар {offer_id}: target={target_price:.2f}, "
                f"margin={current_margin:.2f}%"
            )

            updates_for_ozon.append({
                'offer_id': str(offer_id),
                'price': f"{target_price:.2f}",
                'old_price': f"{product.get('current_price', target_price):.2f}",
                'min_price': f"{min_price:.2f}"
            })

            margin_items.append({
                'offer_id': offer_id,
                'target_price': target_price,
                'margin': current_margin,
            })

        return updates_for_ozon, margin_items