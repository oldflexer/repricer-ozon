from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

@dataclass
class ProductInfo:
    sku: str
    product_name: Optional[str] = None
    cost_price: float = 0.0
    min_price: float = 0.0  # РИЦ (rip)
    current_price: float = 0.0
    product_id: Optional[int] = None
    offer_id: Optional[str] = None

@dataclass
class StrategyInterval:
    start: str      # "HH:MM"
    end: str        # "HH:MM"
    strategy_type: int  # 1-ниже, 2-выше, 3-равная
    percent: float = 0.0

@dataclass
class PricingData:
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

    @classmethod
    def from_api_response(cls, data: dict) -> 'PricingData':
        price_obj = data.get('price', {})
        indexes = data.get('price_indexes', {})

        def _get_index(index_name: str) -> tuple[Optional[float], Optional[float]]:
            idx = indexes.get(index_name)
            if isinstance(idx, dict):
                min_price = idx.get('min_price')
                if min_price == '' or min_price is None:
                    min_price_val = None
                else:
                    try:
                        min_price_val = float(min_price)
                    except (ValueError, TypeError):
                        min_price_val = None
                idx_val = idx.get('price_index_value')
                if idx_val == '' or idx_val is None:
                    idx_value = None
                else:
                    try:
                        idx_value = float(idx_val)
                    except (ValueError, TypeError):
                        idx_value = None
                return min_price_val, idx_value
            return None, None

        ext_price, ext_index = _get_index('external_index_data')
        ozon_price, ozon_index = _get_index('ozon_index_data')
        self_price, self_index = _get_index('self_marketplaces_index_data')

        return cls(
            product_id=data['product_id'],
            price=float(price_obj.get('price', 0)),
            old_price=float(price_obj.get('old_price', 0)),
            min_price=float(price_obj.get('min_price', 0)),
            net_price=float(price_obj.get('net_price', 0)),
            marketing_seller_price=float(price_obj.get('marketing_seller_price', 0)),
            external_index_data_price=ext_price,
            external_index_data_index=ext_index,
            ozon_index_data_price=ozon_price,
            ozon_index_data_index=ozon_index,
            self_marketplaces_index_data_price=self_price,
            self_marketplaces_index_data_index=self_index
        )

@dataclass
class PriceCalculationResult:
    sku: str
    target_min_price: float
    strategy_price: Optional[float]
    target_strategy_price: Optional[float]
    result_target_price: float
    marginality: float
    log_details: dict = field(default_factory=dict)

@dataclass
class UpdateRequest:
    product_id: int
    price: float
    min_price: float
    net_price: Optional[float] = None
    old_price: Optional[float] = None