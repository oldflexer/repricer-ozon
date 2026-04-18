from datetime import datetime
from typing import List, Optional, Dict, Any
import json


class PriceCalculator:
    """Расчёт целевой цены по стратегиям и временным интервалам"""

    @staticmethod
    def get_strategy_for_time(schedule: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Определяет активную стратегию в зависимости от текущего времени.
        schedule - JSON строка вида:
        [
            {"start": "09:00", "end": "12:00", "strategy": 2, "percent": 5},
            {"start": "12:00", "end": "18:00", "strategy": 1, "percent": 3},
            ...
        ]
        Возвращает словарь с параметрами активной стратегии.
        Если расписание не задано или не найдено – возвращает None.
        """
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
        """
        Рассчитывает целевую цену с учётом временных интервалов.

        competitor_prices: список цен конкурентов (уже спарсенные)
        base_strategy: базовая стратегия (1 - ниже, 2 - выше, 3 - равная)
        base_percent: базовый процент для стратегий 1 и 2
        min_price: минимально допустимая цена
        schedule: JSON расписание (может быть None)

        Возвращает рассчитанную цену.
        """
        if not competitor_prices:
            return min_price

        # Определяем активную стратегию
        active = PriceCalculator.get_strategy_for_time(schedule)
        if active:
            strategy = active['strategy']
            percent = active['percent']
        else:
            strategy = base_strategy
            percent = base_percent

        # Базовая цена по минимальной цене конкурента
        min_comp_price = min(competitor_prices)

        if strategy == 1:   # Ниже конкурента на X%
            target = min_comp_price * (1 - percent / 100)
        elif strategy == 2: # Выше конкурента на X%
            target = min_comp_price * (1 + percent / 100)
        else:               # Такая же
            target = min_comp_price

        # Не ниже разрешённого минимума
        return max(target, min_price)


class MarginCalculator:
    """Расчёт маржинальности с учётом комиссий Ozon"""

    # Примерные значения (в реальности нужно получать через API или таблицу)
    DEFAULT_COMMISSION = 0.15  # 15%
    DEFAULT_LOGISTICS = 50     # 50 руб за единицу

    def __init__(self, db_connection):
        self.db = db_connection

    def calculate_margin(self, price: float, cost_price: float,
                         commission: Optional[float] = None,
                         logistics: Optional[float] = None) -> float:
        """
        Возвращает маржинальность в процентах.
        """
        commission = commission or self.DEFAULT_COMMISSION
        logistics = logistics or self.DEFAULT_LOGISTICS

        profit = price - cost_price - (price * commission) - logistics
        if price == 0:
            return 0.0
        return (profit / price) * 100

    def get_average_margin(self, offer_id: str, days: int) -> Optional[float]:
        """
        Получает среднюю маржинальность за последние `days` дней из истории.
        """
        # Будет реализовано после создания БД
        pass