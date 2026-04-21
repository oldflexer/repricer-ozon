from datetime import datetime
from typing import List, Optional, Dict, Any
import json


class PriceCalculator:
    """Расчёт целевой цены по стратегиям и временным интервалам"""

    @staticmethod
    def get_strategy_for_time(schedule: Optional[str]) -> Optional[Dict[str, Any]]:
        if not schedule:
            return None
        try:
            intervals = json.loads(schedule)
        except:
            return None

        now = datetime.now().time()
        for interval in intervals:
            start = datetime.strptime(interval['start'], '%H:%M').time()
            end = datetime.strptime(interval['end'], '%H:%M').time()
            if start <= now <= end:
                return {
                    'strategy': interval.get('strategy', 3),
                    'percent': interval.get('percent', 0)
                }
        return None

    @staticmethod
    def calculate_target_price(
        competitor_prices: List[float],
        base_strategy: int,
        base_percent: float,
        min_price: float,
        schedule: Optional[str] = None
    ) -> float:
        if not competitor_prices:
            return min_price

        active = PriceCalculator.get_strategy_for_time(schedule)
        if active:
            strategy = active['strategy']
            percent = active['percent']
        else:
            strategy = base_strategy
            percent = base_percent

        min_comp_price = min(competitor_prices)

        if strategy == 1:
            target = min_comp_price * (1 - percent / 100)
        elif strategy == 2:
            target = min_comp_price * (1 + percent / 100)
        else:
            target = min_comp_price

        target = round(max(target, min_price))
        return target


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

    def get_average_margin(self, offer_id: str, days: int) -> Optional[float]:
        # Реализация в database.py
        pass