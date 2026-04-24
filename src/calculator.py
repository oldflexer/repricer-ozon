from datetime import datetime
from typing import List, Optional, Dict, Any
import json


class PriceCalculator:
    @staticmethod
    def get_active_strategy(intervals: List[Dict]) -> Optional[Dict[str, Any]]:
        """Возвращает словарь {'strategy': int, 'percent': float} для текущего времени."""
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
        """Рассчитывает цену на основе минимальной цены конкурента и активной стратегии."""
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