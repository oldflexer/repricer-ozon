"""
Доменная сущность Product (Rich Domain Model).

Инкапсулирует бизнес-логику ценообразования, стратегий и инвариантов товара.
"""

from dataclasses import dataclass, field
from datetime import time

from core.domain.pricing_rules import OzonPricingRules
from core.domain.value_objects import (
    SKU,
    Money,
    Percentage,
    TimeInterval,
)
from core.enums import StrategyType


@dataclass(slots=True)
class PricingStrategy:
    """
    Стратегия ценообразования для временного интервала.

    Value Object - неизменяем, не имеет идентичности.
    """

    interval: TimeInterval
    strategy_type: StrategyType
    percent: Percentage = field(default_factory=lambda: Percentage.from_percent(0))

    def is_active_at(self, current_time: time) -> bool:
        """Проверяет, активна ли стратегия в данное время."""
        return self.interval.contains(current_time.hour, current_time.minute)

    def calculate_price(
        self, base_price: Money, target_min_price: Money, rules: OzonPricingRules
    ) -> Money:
        """
        Рассчитывает цену согласно стратегии.

        Args:
            base_price: Базовая цена (цена конкурента или индекс Ozon)
            target_min_price: Целевая минимальная цена (RIP / discount_coef)
            rules: Бизнес-правила Ozon

        Returns:
            Рассчитанная целевая цена
        """
        match self.strategy_type:
            case StrategyType.BELOW:
                return rules.apply_strategy_below(base_price, self.percent)
            case StrategyType.ABOVE:
                return rules.apply_strategy_above(base_price, self.percent)
            case StrategyType.EQUAL:
                return rules.apply_strategy_equal(target_min_price)
            case _:
                return rules.apply_strategy_equal(target_min_price)


@dataclass(slots=True)
class Product:
    """
    Доменная сущность Товар.

    Инкапсулирует:
    - Идентификаторы (SKU, product_id, offer_id)
    - Ценовые параметры (себестоимость, РИЦ, текущая цена)
    - Стратегии ценообразования по времени
    - Данные конкурентов
    - Реальную цену покупателя (из шаблона Ozon / страницы управления ценами)
    """

    sku: SKU
    product_id: int | None = None
    offer_id: str | None = None
    product_name: str | None = None
    cost_price: Money = field(default_factory=lambda: Money.from_rubles(0))
    min_price: Money = field(default_factory=lambda: Money.from_rubles(0))  # RIP
    current_price: Money = field(default_factory=lambda: Money.from_rubles(0))
    old_price: Money | None = None
    competitor_min_price: Money | None = None
    real_customer_price: Money | None = None      # Реальная цена покупателя
    strategies: list[PricingStrategy] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Валидация инвариантов после инициализации."""
        if self.cost_price._kopecks < 0:
            raise ValueError("Cost price cannot be negative")
        if self.min_price._kopecks < 0:
            raise ValueError("Min price (RIP) cannot be negative")

    # --- Методы для работы со стратегиями ---

    def add_strategy(self, strategy: PricingStrategy) -> None:
        """Добавляет стратегию и сортирует по времени начала."""
        self.strategies.append(strategy)
        self.strategies.sort(key=lambda s: s.interval.start_minutes)

    def set_strategies(self, strategies: list[PricingStrategy]) -> None:
        """Заменяет все стратегии."""
        self.strategies = sorted(strategies, key=lambda s: s.interval.start_minutes)

    def get_active_strategy(self, current_time: time) -> PricingStrategy:
        """
        Возвращает активную стратегию для текущего времени.

        Если активная не найдена - возвращает стратегию 'Равная' на весь день.
        """
        for strategy in self.strategies:
            if strategy.is_active_at(current_time):
                return strategy

        # Fallback: стратегия "Равная" на весь день
        return PricingStrategy(
            interval=TimeInterval(0, 0, 23, 59),
            strategy_type=StrategyType.EQUAL,
            percent=Percentage.from_percent(0),
        )

    def validate_min_price(self, price: Money, rules: OzonPricingRules) -> Money:
        """Валидирует min_price через доменные правила."""
        return rules.validate_min_price(price, self.min_price)

    def calculate_old_price(self, price: Money, rules: OzonPricingRules) -> Money:
        """Рассчитывает старую цену через доменные правила."""
        return rules.calculate_old_price(price, self.old_price)

    # --- Методы обновления состояния ---

    def update_real_customer_price(self, price: Money) -> None:
        """Обновляет реальную цену покупателя (из шаблона Ozon / страницы управления ценами)."""
        self.real_customer_price = price

    def update_ozon_ids(self, product_id: int, offer_id: str, name: str | None = None) -> None:
        """Обновляет идентификаторы из Ozon API."""
        self.product_id = product_id
        self.offer_id = offer_id
        if name:
            self.product_name = name

    def update_competitor_price(self, price: Money) -> None:
        """Обновляет минимальную цену конкурента."""
        self.competitor_min_price = price

    def __str__(self) -> str:
        return f"Product(sku={self.sku}, name={self.product_name}, cost={self.cost_price}, rip={self.min_price})"
