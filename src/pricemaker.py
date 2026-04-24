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
        updates_for_ozon = []      # эти цены уйдут в Ozon (с поправкой на коэффициент)
        margin_items = []          # эти цены будут сохранены локально (без поправки)

        for product in products:
            sku = product['sku']
            real_price = real_prices.get(sku)
            if real_price is None:
                real_price = product.get('current_price')

            # Последние цены конкурентов из БД
            comps = self.db.get_competitors_for_product(sku)
            competitor_prices = []
            for c in comps:
                hist = self.db.get_competitor_price_history(c['id'])
                if hist:
                    competitor_prices.append(hist[-1]['price'])

            min_price = product.get('min_price', 0.0)
            intervals = product['intervals']

            # 1. Стратегическая цена (чистая, не ниже РРЦ)
            strategy_price = self.calculator.calculate_strategy_price(
                competitor_prices=competitor_prices,
                intervals=intervals,
                min_price=min_price
            )

            # 2. Коэффициент Ozon (скидка)
            ozon_coef = self.calculator.calculate_ozon_coefficient(real_price, min_price)

            # 3. Финальная цена для Ozon = стратегическая / коэффициент
            target_price = round(strategy_price / ozon_coef)

            # Маржинальность по чистой стратегической цене
            cost_price = product.get('cost_price', 0.0)
            local_margin = self.margin_calc.calculate_margin(strategy_price, cost_price)

            logger.info(
                f"Товар {sku}: strategy={strategy_price:.2f}, target={target_price:.2f} (для Ozon), margin={local_margin:.2f}%"
            )

            # Данные для отправки в Ozon (только price и идентификаторы)
            updates_for_ozon.append({
                'product_id': product.get('product_id'),
                'offer_id': '',
                'price': f"{target_price:.2f}",
            })

            margin_items.append({
                'sku': sku,
                'target_price': strategy_price,   # сохраняем чистую стратегическую цену
                'margin': local_margin,
            })

        return updates_for_ozon, margin_items