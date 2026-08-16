"""
Доменные сущности приложения.

Содержит основные бизнес-сущности: товар, интервал стратегии,
данные о ценах и комиссиях из API, результат расчёта цены.
"""

from dataclasses import dataclass, field
from datetime import datetime, time

from core.enums import StrategyType, parse_strategy_value


@dataclass
class ProductInfo:
    """
    Доменная модель товара.

    Атрибуты:
        sku: Артикул товара (обязательный).
        product_name: Название товара.
        cost_price: Себестоимость.
        min_price: Минимальная цена (РИЦ).
        current_price: Текущая цена покупателя.
        old_price: Старая цена (до скидки).
        product_id: Идентификатор товара в Ozon.
        offer_id: Offer ID товара.
        real_customer_price: Реальная цена покупателя (из индексов).
        competitor_min_price: Минимальная цена конкурента.
    """

    sku: str
    product_name: str | None = None
    cost_price: float = 0.0
    min_price: float = 0.0
    current_price: float = 0.0
    old_price: float | None = None
    product_id: int | None = None
    offer_id: str | None = None
    real_customer_price: float | None = None
    competitor_min_price: float | None = None


@dataclass
class StrategyInterval:
    """
    Временной интервал стратегии ценообразования.

    Атрибуты:
        start: Время начала интервала (HH:MM).
        end: Время окончания интервала (HH:MM).
        strategy_type: Тип стратегии (StrategyType enum).
        percent: Процент отклонения для стратегий BELOW и ABOVE.
        start_time, end_time: Объекты time, вычисляемые автоматически.
    """

    start: str
    end: str
    strategy_type: StrategyType  # Enum: BELOW=1, ABOVE=2, EQUAL=3
    percent: float = 0.0
    start_time: time = field(init=False)
    end_time: time = field(init=False)

    def __post_init__(self) -> None:
        """Преобразует строки start/end в объекты time и strategy_type в Enum."""
        self.start_time = datetime.strptime(self.start, "%H:%M").time()
        self.end_time = datetime.strptime(self.end, "%H:%M").time()
        # Если передано число или строка, преобразуем в Enum
        if isinstance(self.strategy_type, int):
            self.strategy_type = StrategyType(self.strategy_type)
        elif isinstance(self.strategy_type, str):
            self.strategy_type = parse_strategy_value(self.strategy_type)


@dataclass
class PricingData:
    """
    Данные о ценах и комиссиях товара, полученные из Ozon API (v5).

    Атрибуты:
        product_id: Идентификатор товара.
        price: Текущая цена (price).
        old_price: Старая цена.
        min_price: Минимальная цена.
        net_price: Чистая цена (себестоимость).
        marketing_seller_price: Маркетинговая цена продавца.
        external_index_data_price, external_index_data_index: Данные внешнего индекса.
        ozon_index_data_price, ozon_index_data_index: Данные индекса Ozon.
        self_marketplaces_index_data_price, self_marketplaces_index_data_index:
            Данные индекса собственных маркетплейсов.
        sales_percent_fbs: Процент комиссии FBS.
        acquiring: Комиссия за эквайринг.
        fbs_first_mile_min_amount, fbs_first_mile_max_amount: Комиссия за первую милю (FBS).
        fbs_direct_flow_trans_min_amount, fbs_direct_flow_trans_max_amount: Комиссия за прямую доставку (FBS).
        fbs_deliv_to_customer_amount: Доставка до покупателя (FBS).
        fbo_direct_flow_trans_min_amount, fbo_direct_flow_trans_max_amount:
            Комиссия за прямую доставку (FBO).
        fbo_deliv_to_customer_amount: Доставка до покупателя (FBO).
    """

    product_id: int
    price: float = 0.0
    old_price: float = 0.0
    min_price: float = 0.0
    net_price: float = 0.0
    marketing_seller_price: float = 0.0

    external_index_data_price: float | None = None
    external_index_data_index: float | None = None
    ozon_index_data_price: float | None = None
    ozon_index_data_index: float | None = None
    self_marketplaces_index_data_price: float | None = None
    self_marketplaces_index_data_index: float | None = None

    acquiring: float = 0.0
    fbo_deliv_to_customer_amount: float = 0.0
    fbo_direct_flow_trans_max_amount: float = 0.0
    fbo_direct_flow_trans_min_amount: float = 0.0
    fbo_return_flow_amount: float = 0.0
    fbs_deliv_to_customer_amount: float = 0.0
    fbs_direct_flow_trans_max_amount: float = 0.0
    fbs_direct_flow_trans_min_amount: float = 0.0
    fbs_first_mile_max_amount: float = 0.0
    fbs_first_mile_min_amount: float = 0.0
    fbs_return_flow_amount: float = 0.0
    sales_percent_fbo: float = 0.0
    sales_percent_fbs: float = 0.0


@dataclass
class PriceCalculationResult:
    """
    Результат расчёта целевой цены и маржинальности товара.

    Атрибуты:
        sku: Артикул товара.
        target_min_price: Целевая минимальная цена (РИЦ / discount_coef).
        strategy_price: Цена, рассчитанная по стратегии (без дисконта).
        target_strategy_price: Цена по стратегии с учётом дисконта.
        result_target_price: Итоговая цена для отправки в Ozon (округлённая).
        marginality: Рассчитанная маржинальность (в долях).
        log_details: Дополнительная информация для логирования (словарь).
    """

    sku: str
    target_min_price: float
    strategy_price: float | None
    target_strategy_price: float | None
    result_target_price: float
    marginality: float
    log_details: dict = field(default_factory=dict)


@dataclass
class UpdateRequest:
    """
    Запрос на обновление цены в Ozon API (устаревший, использовать PriceUpdateRequestDTO).

    Этот класс оставлен для обратной совместимости и будет удалён в будущих версиях.
    """

    product_id: int
    price: float
    min_price: float
    net_price: float | None = None
    old_price: float | None = None
