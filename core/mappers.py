from typing import Optional
from .entities import ProductInfo, StrategyInterval
from .dto import ProductDTO, StrategyIntervalDTO, PriceUpdateRequestDTO, ProductViewModel
from config.settings import settings


def product_to_dto(product: ProductInfo) -> ProductDTO:
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
    )


def dto_to_product(dto: ProductDTO) -> ProductInfo:
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
    )


def strategy_interval_to_dto(interval: StrategyInterval) -> StrategyIntervalDTO:
    return StrategyIntervalDTO(
        start=interval.start,
        end=interval.end,
        strategy_type=interval.strategy_type,
        percent=interval.percent,
    )


def dto_to_strategy_interval(dto: StrategyIntervalDTO) -> StrategyInterval:
    return StrategyInterval(
        start=dto.start,
        end=dto.end,
        strategy_type=dto.strategy_type,
        percent=dto.percent,
    )


def build_price_update_request(product_id: int, price: int, min_price: int,
                               net_price: Optional[int] = None,
                               old_price: Optional[int] = None,
                               manage_elastic_boosting: bool = settings.MANAGE_ELASTIC_BOOSTING) -> PriceUpdateRequestDTO:
    return PriceUpdateRequestDTO(
        product_id=product_id,
        price=price,
        min_price=min_price,
        net_price=net_price,
        old_price=old_price,
        manage_elastic_boosting_through_price=manage_elastic_boosting,
    )


def to_view_model(product: ProductInfo, last_price: Optional[float], last_margin: Optional[float],
                  avg_week: Optional[float], avg_month: Optional[float]) -> ProductViewModel:
    return ProductViewModel(
        sku=product.sku,
        name=product.product_name or "",
        cost_price=product.cost_price,
        min_price=product.min_price,
        current_price=last_price,
        marginality_percent=last_margin * 100 if last_margin is not None else None,
        avg_week_margin=avg_week * 100 if avg_week is not None else None,
        avg_month_margin=avg_month * 100 if avg_month is not None else None,
    )