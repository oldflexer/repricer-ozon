"""
Доменная сущность Product (Rich Domain Model).

Инкапсулирует бизнес-логику ценообразования, стратегий и инвариантов товара.
"""

from dataclasses import dataclass, field
from datetime import time

from core.domain.pricing_rules import OzonPricingRules, get_pricing_rules
from core.domain.value_objects import (
    SKU,
    DiscountCoefficient,
    Money,
    Percentage,
    TimeInterval,
)
from core.entities import PriceCalculationResult, PricingData, StrategyInterval
from core.enums import StrategyType
from core.services.price_calculation import PriceCalculationService


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

    # Кэш для расчётов
    _discount_coef: DiscountCoefficient | None = field(default=None, init=False, repr=False)

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

    # --- Методы для расчёта цен ---

    def set_discount_coefficient(self, discount_coef: DiscountCoefficient) -> None:
        """Устанавливает коэффициент дисконта (вычисляется из индексов/реальной цены)."""
        self._discount_coef = discount_coef

    @property
    def discount_coefficient(self) -> DiscountCoefficient:
        """Возвращает коэффициент дисконта (или дефолтный)."""
        return self._discount_coef or get_pricing_rules().default_discount_coef

    def calculate_target_min_price(self, rules: OzonPricingRules) -> Money:
        """
        Рассчитывает целевую минимальную цену: RIP / discount_coef.

        Это цена, которую нужно установить как маркетинговую,
        чтобы после скидки реальная цена была >= RIP.
        """
        return rules.calculate_target_min_price(self.min_price, self.discount_coefficient)

    def select_base_price(
        self, ozon_index_price: Money | None, _rules: OzonPricingRules
    ) -> Money | None:
        """
        Выбирает базовую цену для стратегий BELOW/ABOVE.

        Приоритет:
        1. Цена конкурента (есть и > 0)
        2. Индекс Ozon (есть и > 0)
        3. None (стратегия игнорируется, используется RIP)
        """
        if self.competitor_min_price is not None and self.competitor_min_price._kopecks > 0:
            return self.competitor_min_price
        if ozon_index_price is not None and ozon_index_price._kopecks > 0:
            return ozon_index_price
        return None

    def calculate_target_price(
        self, pricing_data: PricingData, rules: OzonPricingRules, _current_time: time
    ) -> PriceCalculationResult:
        """
        Основной метод расчёта целевой цены.

        Args:
            pricing_data: Данные из Ozon API (цены, индексы, комиссии)
            rules: Бизнес-правила Ozon
            current_time: Текущее время для выбора стратегии

        Returns:
            PriceCalculationResult с целевой ценой, маржинальностью и деталями
        """
        # Используем существующий сервис расчёта для совместимости
        # Но готовим данные через доменную модель
        service = PriceCalculationService(
            default_coefficient=rules.default_discount_coef.value_float
        )

        # Конвертируем доменные объекты в формат сервиса (StrategyInterval entities)
        intervals = [
            StrategyInterval(
                start=f"{s.interval.start_hour:02d}:{s.interval.start_minute:02d}",
                end=f"{s.interval.end_hour:02d}:{s.interval.end_minute:02d}",
                strategy_type=s.strategy_type,
                percent=s.percent.percent_float,
            )
            for s in self.strategies
        ]

        result = service.calculate(
            sku=str(self.sku),
            pricing=pricing_data,
            rip=self.min_price.rubles_float,
            intervals=intervals,
            competitor_min_price=self.competitor_min_price.rubles_float
            if self.competitor_min_price
            else None,
            real_customer_price=self.real_customer_price.rubles_float
            if self.real_customer_price
            else None,
        )

        # Добавляем доменную логику валидации min_price
        target_price = Money.from_rubles(result.result_target_price)
        min_price_for_api = Money.from_rubles(
            self.min_price.rubles_float / self.discount_coefficient.value_float
        )
        validated_min_price = rules.validate_min_price(target_price, min_price_for_api)

        # Пересчитываем old_price через доменное правило
        old_price = rules.calculate_old_price(
            target_price, Money.from_rubles(self.old_price.rubles_float) if self.old_price else None
        )

        # Возвращаем результат с доменными корректировками
        return PriceCalculationResult(
            sku=result.sku,
            target_min_price=result.target_min_price,
            strategy_price=result.strategy_price,
            target_strategy_price=result.target_strategy_price,
            result_target_price=result.result_target_price,
            marginality=result.marginality,
            log_details={
                **result.log_details,
                "domain_validated_min_price": validated_min_price.rubles_float,
                "domain_old_price": old_price.rubles_float,
            },
        )

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
