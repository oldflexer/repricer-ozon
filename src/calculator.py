from datetime import datetime
from typing import List, Optional, Dict, Any
import json


class PriceCalculator:
    @staticmethod
    def get_active_strategy(intervals: List[Dict]) -> Optional[Dict[str, Any]]:
        """intervals: список словарей с start, end, strategy, percent."""
        now = datetime.now().time()
        for inv in intervals:
            start = datetime.strptime(inv['start'], '%H:%M').time()
            end = datetime.strptime(inv['end'], '%H:%M').time()
            if start <= now <= end:
                return {'strategy': inv['strategy'], 'percent': inv['percent']}
        return None

    @staticmethod
    def calculate_strategy_price(
        competitor_prices: List[float],
        intervals: List[Dict],
        min_price: float
    ) -> float:
        """Рассчитывает цену только на основе стратегии и конкурентов."""
        if min_price is None:
            min_price = 0.0

        valid_prices = [p for p in competitor_prices if p is not None]
        if not valid_prices:
            return min_price

        active = PriceCalculator.get_active_strategy(intervals)
        if active:
            strategy = active['strategy']
            percent = active['percent']
        else:
            strategy = intervals[0]['strategy'] if intervals else 3
            percent = intervals[0]['percent'] if intervals else 0.0

        min_comp_price = min(valid_prices)

        if strategy == 1:
            target = min_comp_price * (1 - percent / 100)
        elif strategy == 2:
            target = min_comp_price * (1 + percent / 100)
        else:
            target = min_comp_price

        return round(max(target, min_price))

    @staticmethod
    def calculate_target_price(
        competitor_prices: List[float],
        intervals: List[Dict],
        min_price: float,
        real_price: Optional[float] = None
    ) -> float:
        """
        Основной метод расчёта целевой цены с учётом реальной цены.
        min_price – это РРЦ (цена РИЦ).
        """
        if min_price is None:
            min_price = 0.0

        strategy_price = PriceCalculator.calculate_strategy_price(
            competitor_prices, intervals, min_price
        )

        if real_price is not None and real_price > 0 and real_price < min_price:
            # РРЦ выше реальной цены
            rrp_diff_percent = (min_price - real_price) / real_price * 100
            required_price = min_price * (1 + rrp_diff_percent / 100)
            target = max(strategy_price, required_price)
        else:
            target = max(strategy_price, min_price)

        return round(target)


class MarginCalculator:
    DEFAULT_COMMISSION = 0.15
    DEFAULT_LOGISTICS = 50

    def __init__(self, db_connection):
        self.db = db_connection

    def calculate_margin(self, price: float, cost_price: float,
                         commission: Optional[float] = None,
                         logistics: Optional[float] = None) -> float:
        commission = commission or self.DEFAULT_COMMISSION
        logistics = logistics or self.DEFAULT_LOGISTICS

        profit = price - cost_price - (price * commission) - logistics
        if price == 0:
            return 0.0
        return (profit / price) * 100