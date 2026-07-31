"""
Доменные сущности приложения.

Содержит основные бизнес-сущности: товар, интервал стратегии,
данные о ценах и комиссиях из API, результат расчёта цены.
"""

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Optional, List


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
    product_name: Optional[str] = None
    cost_price: float = 0.0
    min_price: float = 0.0
    current_price: float = 0.0
    old_price: Optional[float] = None
    product_id: Optional[int] = None
    offer_id: Optional[str] = None
    real_customer_price: Optional[float] = None
    competitor_min_price: Optional[float] = None


@dataclass
class StrategyInterval:
    """
    Временной интервал стратегии ценообразования.

    Атрибуты:
        start: Время начала интервала (HH:MM).
        end: Время окончания интервала (HH:MM).
        strategy_type: Тип стратегии: 1 – ниже, 2 – выше, 3 – равна.
        percent: Процент отклонения для стратегий 1 и 2.
        start_time, end_time: Объекты time, вычисляемые автоматически.
    """
    start: str
    end: str
    strategy_type: int  # 1 - ниже, 2 - выше, 3 - равна
    percent: float = 0.0
    start_time: time = field(init=False)
    end_time: time = field(init=False)

    def __post_init__(self) -> None:
        """Преобразует строки start/end в объекты time."""
        self.start_time = datetime.strptime(self.start, "%H:%M").time()
        self.end_time = datetime.strptime(self.end, "%H:%M").time()


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

    external_index_data_price: Optional[float] = None
    external_index_data_index: Optional[float] = None
    ozon_index_data_price: Optional[float] = None
    ozon_index_data_index: Optional[float] = None
    self_marketplaces_index_data_price: Optional[float] = None
    self_marketplaces_index_data_index: Optional[float] = None

    sales_percent_fbs: float = 0.0
    acquiring: float = 0.0

    fbs_first_mile_min_amount: float = 0.0
    fbs_first_mile_max_amount: float = 0.0
    fbs_direct_flow_trans_min_amount: float = 0.0
    fbs_direct_flow_trans_max_amount: float = 0.0
    fbs_deliv_to_customer_amount: float = 0.0

    fbo_direct_flow_trans_min_amount: float = 0.0
    fbo_direct_flow_trans_max_amount: float = 0.0
    fbo_deliv_to_customer_amount: float = 0.0

    @classmethod
    def from_api_response(cls, data: dict) -> "PricingData":
        """
        Создаёт экземпляр PricingData из ответа Ozon API (/v5/product/info/prices).

        Args:
            data: Словарь с данными ответа API.

        Returns:
            PricingData: Объект с заполненными полями.
        """
        price_obj = data.get("price", {})
        indexes = data.get("price_indexes", {})
        commissions = data.get("commissions", {})

        def _get_index(index_name: str) -> tuple[Optional[float], Optional[float]]:
            """Извлекает цену и значение индекса из блока price_indexes."""
            idx = indexes.get(index_name)
            if isinstance(idx, dict):
                min_price = idx.get("min_price")
                if min_price in ("", None):
                    min_price_val = None
                else:
                    try:
                        min_price_val = float(min_price)
                    except (ValueError, TypeError):
                        min_price_val = None

                idx_val = idx.get("price_index_value")
                if idx_val in ("", None):
                    idx_value = None
                else:
                    try:
                        idx_value = float(idx_val)
                    except (ValueError, TypeError):
                        idx_value = None
                return min_price_val, idx_value
            return None, None

        ext_price, ext_index = _get_index("external_index_data")
        ozon_price, ozon_index = _get_index("ozon_index_data")
        self_price, self_index = _get_index("self_marketplaces_index_data")

        return cls(
            product_id=data["product_id"],
            price=float(price_obj.get("price", 0)),
            old_price=float(price_obj.get("old_price", 0)),
            min_price=float(price_obj.get("min_price", 0)),
            net_price=float(price_obj.get("net_price", 0)),
            marketing_seller_price=float(price_obj.get("marketing_seller_price", 0)),
            external_index_data_price=ext_price,
            external_index_data_index=ext_index,
            ozon_index_data_price=ozon_price,
            ozon_index_data_index=ozon_index,
            self_marketplaces_index_data_price=self_price,
            self_marketplaces_index_data_index=self_index,
            sales_percent_fbs=float(commissions.get("sales_percent_fbs", 0)),
            acquiring=float(data.get("acquiring", 0)),
            fbs_first_mile_min_amount=float(commissions.get("fbs_first_mile_min_amount", 0)),
            fbs_first_mile_max_amount=float(commissions.get("fbs_first_mile_max_amount", 0)),
            fbs_direct_flow_trans_min_amount=float(commissions.get("fbs_direct_flow_trans_min_amount", 0)),
            fbs_direct_flow_trans_max_amount=float(commissions.get("fbs_direct_flow_trans_max_amount", 0)),
            fbs_deliv_to_customer_amount=float(commissions.get("fbs_deliv_to_customer_amount", 0)),
            fbo_direct_flow_trans_min_amount=float(commissions.get("fbo_direct_flow_trans_min_amount", 0)),
            fbo_direct_flow_trans_max_amount=float(commissions.get("fbo_direct_flow_trans_max_amount", 0)),
            fbo_deliv_to_customer_amount=float(commissions.get("fbo_deliv_to_customer_amount", 0)),
        )


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
    strategy_price: Optional[float]
    target_strategy_price: Optional[float]
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
    net_price: Optional[float] = None
    old_price: Optional[float] = None