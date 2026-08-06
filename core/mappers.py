"""
Мапперы для преобразования между доменными сущностями и DTO.

Содержит функции для конвертации объектов между слоями, а также
вспомогательные функции для построения запросов к API и ViewModel.
"""

from typing import Optional

from config.settings import settings
from core.enums import StrategyType
from .dto import (
    PriceUpdateRequestDTO,
    ProductDTO,
    ProductViewModel,
    StrategyIntervalDTO,
)
from .entities import ProductInfo, StrategyInterval


def product_to_dto(product: ProductInfo) -> ProductDTO:
    """
    Преобразует доменную сущность ProductInfo в ProductDTO.

    Args:
        product: Объект ProductInfo.

    Returns:
        ProductDTO: DTO с теми же данными.
    """
    return ProductDTO(
        sku=product.sku,
        product_name=product.product_name,
        cost_price=product.cost_price,
        min_price=product.min_price,
        current_price=product.current_price,
        old_price=product.old_price,
        product_id=product.product_id,
        offer_id=product.offer_id,
        real_customer_price=product.real_customer_price,
        competitor_min_price=product.competitor_min_price,
    )


def dto_to_product(dto: ProductDTO) -> ProductInfo:
    """
    Преобразует ProductDTO обратно в доменную сущность ProductInfo.

    Args:
        dto: Объект ProductDTO.

    Returns:
        ProductInfo: Доменная сущность.
    """
    return ProductInfo(
        sku=dto.sku,
        product_name=dto.product_name,
        cost_price=dto.cost_price,
        min_price=dto.min_price,
        current_price=dto.current_price,
        old_price=dto.old_price,
        product_id=dto.product_id,
        offer_id=dto.offer_id,
        real_customer_price=dto.real_customer_price,
        competitor_min_price=dto.competitor_min_price,
    )


def strategy_interval_to_dto(interval: StrategyInterval) -> StrategyIntervalDTO:
    """
    Преобразует StrategyInterval в StrategyIntervalDTO.

    Args:
        interval: Доменный объект интервала стратегии.

    Returns:
        StrategyIntervalDTO: DTO с теми же данными.
    """
    return StrategyIntervalDTO(
        start=interval.start,
        end=interval.end,
        strategy_type=interval.strategy_type.value,
        percent=interval.percent,
    )


def dto_to_strategy_interval(dto: StrategyIntervalDTO) -> StrategyInterval:
    """
    Преобразует StrategyIntervalDTO в StrategyInterval.

    Args:
        dto: DTO интервала стратегии.

    Returns:
        StrategyInterval: Доменный объект.
    """
    return StrategyInterval(
        start=dto.start,
        end=dto.end,
        strategy_type=StrategyType(dto.strategy_type),
        percent=dto.percent,
    )


def build_price_update_request(
    product_id: int,
    price: int,
    min_price: int,
    net_price: Optional[int] = None,
    old_price: Optional[int] = None,
    manage_elastic_boosting: bool = settings.MANAGE_ELASTIC_BOOSTING,
) -> PriceUpdateRequestDTO:
    """
    Создаёт DTO для запроса обновления цены в Ozon API.

    Args:
        product_id: Идентификатор товара в Ozon.
        price: Цена для отправки.
        min_price: Минимальная цена.
        net_price: Чистая цена (себестоимость) – опционально.
        old_price: Старая цена – опционально.
        manage_elastic_boosting: Флаг управления эластичностью (берётся из настроек).

    Returns:
        PriceUpdateRequestDTO: Готовый DTO для отправки.
    """
    return PriceUpdateRequestDTO(
        product_id=product_id,
        price=price,
        min_price=min_price,
        net_price=net_price,
        old_price=old_price,
        manage_elastic_boosting_through_price=manage_elastic_boosting,
    )


def to_view_model(
    product: ProductInfo,
    last_price: Optional[float],
    last_margin: Optional[float],
    avg_week: Optional[float],
    avg_month: Optional[float],
) -> ProductViewModel:
    """
    Преобразует данные товара и исторические метрики в ViewModel для дашборда.

    Args:
        product: Доменная сущность товара.
        last_price: Последняя цена покупателя.
        last_margin: Последняя маржинальность (в долях).
        avg_week: Средняя маржинальность за неделю (в долях).
        avg_month: Средняя маржинальность за месяц (в долях).

    Returns:
        ProductViewModel: Готовая модель для отображения.
    """
    return ProductViewModel(
        sku=product.sku,
        name=product.product_name or "",
        cost_price=product.cost_price,
        min_price=product.min_price,
        current_price=last_price,
        marginality_percent=last_margin * 100 if last_margin is not None else None,
        avg_week_margin=avg_week * 100 if avg_week is not None else None,
        avg_month_margin=avg_month * 100 if avg_month is not None else None,
        competitor_min_price=product.competitor_min_price,
    )