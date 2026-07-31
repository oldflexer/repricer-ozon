"""
Data Transfer Objects (DTO) для обмена данными между слоями приложения.

Содержит простые dataclass-контейнеры, используемые для передачи данных
между доменным слоем, инфраструктурой и представлением.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ProductDTO:
    """
    DTO для передачи информации о товаре.

    Атрибуты:
        sku: Артикул товара (обязательный).
        product_name: Название товара.
        cost_price: Себестоимость товара.
        min_price: Минимальная цена (РИЦ).
        current_price: Текущая цена покупателя.
        old_price: Старая цена (до скидки).
        product_id: Идентификатор товара в Ozon.
        offer_id: Offer ID товара.
        real_customer_price: Реальная цена покупателя (полученная из индексов).
        competitor_min_price: Минимальная цена среди конкурентов.
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
class StrategyIntervalDTO:
    """
    DTO для временного интервала стратегии ценообразования.

    Атрибуты:
        start: Время начала интервала (в формате HH:MM).
        end: Время окончания интервала (в формате HH:MM).
        strategy_type: Тип стратегии (1 – ниже, 2 – выше, 3 – равна).
        percent: Процент отклонения для стратегий 1 и 2.
    """
    start: str
    end: str
    strategy_type: int
    percent: float = 0.0


@dataclass
class PriceUpdateRequestDTO:
    """
    DTO для запроса обновления цены в Ozon API.

    Атрибуты:
        product_id: Идентификатор товара в Ozon.
        price: Цена, которую нужно установить.
        min_price: Минимальная допустимая цена.
        net_price: Чистая цена (себестоимость).
        old_price: Старая цена (для отображения скидки).
        manage_elastic_boosting_through_price: Флаг управления эластичностью.
    """
    product_id: int
    price: int
    min_price: int
    net_price: Optional[int] = None
    old_price: Optional[int] = None
    manage_elastic_boosting_through_price: bool = False


@dataclass
class ProductViewModel:
    """
    ViewModel для отображения информации о товаре в веб-интерфейсе.

    Атрибуты:
        sku: Артикул товара.
        name: Название товара.
        cost_price: Себестоимость.
        min_price: Минимальная цена (РИЦ).
        current_price: Текущая цена покупателя.
        marginality_percent: Маржинальность в процентах (текущая).
        avg_week_margin: Средняя маржинальность за неделю (%).
        avg_month_margin: Средняя маржинальность за месяц (%).
        competitor_min_price: Минимальная цена конкурента.
    """
    sku: str
    name: str
    cost_price: float
    min_price: float
    current_price: Optional[float]
    marginality_percent: Optional[float]
    avg_week_margin: Optional[float]
    avg_month_margin: Optional[float]
    competitor_min_price: Optional[float] = None