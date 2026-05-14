import logging
from datetime import datetime
from typing import List, Optional
from .entities import StrategyInterval, PricingData, PriceCalculationResult

logger = logging.getLogger(__name__)

class PriceCalculationService:
    """Полный расчёт целевой цены согласно новому алгоритму."""

    def __init__(self, default_coefficient: float = 0.5):
        self.default_coefficient = default_coefficient

    def calculate(self, sku: str, pricing: PricingData, rip: float,
                  intervals: List[StrategyInterval]) -> PriceCalculationResult:
        # 1. Приблизительная реальная цена на основе индексов
        index_prices = []
        if pricing.external_index_data_index and pricing.external_index_data_index != 0:
            index_prices.append(pricing.external_index_data_price)
        if pricing.ozon_index_data_index and pricing.ozon_index_data_index != 0:
            index_prices.append(pricing.ozon_index_data_price)
        if pricing.self_marketplaces_index_data_index and pricing.self_marketplaces_index_data_index != 0:
            index_prices.append(pricing.self_marketplaces_index_data_price)

        if index_prices:
            approx_real_price = sum(index_prices) / len(index_prices)
        else:
            approx_real_price = None

        # 2. Коэффициент скидки
        if approx_real_price is not None and pricing.marketing_seller_price and pricing.marketing_seller_price > 0:
            discount_coef = approx_real_price / pricing.marketing_seller_price
        else:
            discount_coef = self.default_coefficient

        # 3. target_min_price = rip / discount_coef
        target_min_price = rip / discount_coef if discount_coef else rip

        # 4. Активная стратегия
        now = datetime.now().time()
        active = next(
            (inv for inv in intervals
             if datetime.strptime(inv.start, "%H:%M").time() <= now <= datetime.strptime(inv.end, "%H:%M").time()),
            None
        )
        strategy_type = active.strategy_type if active else 3
        percent = active.percent if active else 0.0

        # 5. Расчёт стратегической цены
        target_strategy_price = None
        strategy_price = None
        if pricing.ozon_index_data_price and pricing.ozon_index_data_price != 0:
            base = pricing.ozon_index_data_price
            if strategy_type == 1:
                strategy_price = base * (1 - percent / 100)
            elif strategy_type == 2:
                strategy_price = base * (1 + percent / 100)
            else:
                strategy_price = base
            target_strategy_price = strategy_price / discount_coef if discount_coef else strategy_price
            result_target_price = max(target_strategy_price, target_min_price)
        else:
            result_target_price = target_min_price

        # 6. Маржинальность
        real_price = result_target_price * discount_coef
        if pricing.net_price and real_price:
            marginality = (real_price - pricing.net_price) / real_price
        else:
            marginality = 0.0

        result_target_price = round(result_target_price)

        log_details = {
            "approx_real_price": approx_real_price,
            "discount_coef": discount_coef,
            "default_coef_used": approx_real_price is None,
            "target_min_price": target_min_price,
            "strategy_type": strategy_type,
            "strategy_price": strategy_price,
            "target_strategy_price": target_strategy_price,
            "ozon_index_data_price": pricing.ozon_index_data_price,
            "intervals_used": len(intervals),
            "index_prices_count": len(index_prices),
        }

        return PriceCalculationResult(
            sku=sku,
            target_min_price=target_min_price,
            strategy_price=strategy_price,
            target_strategy_price=target_strategy_price,
            result_target_price=result_target_price,
            marginality=marginality,
            log_details=log_details
        )