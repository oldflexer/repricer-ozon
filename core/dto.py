from dataclasses import dataclass
from typing import Optional

# DTO для загрузки/передачи товара между слоями
@dataclass
class ProductDTO:
    sku: str
    product_name: Optional[str] = None
    cost_price: float = 0.0
    min_price: float = 0.0
    current_price: float = 0.0
    old_price: Optional[float] = None
    product_id: Optional[int] = None
    offer_id: Optional[str] = None
    real_customer_price: Optional[float] = None

@dataclass
class StrategyIntervalDTO:
    start: str
    end: str
    strategy_type: int
    percent: float = 0.0

@dataclass
class PriceUpdateRequestDTO:
    product_id: int
    price: int
    min_price: int
    net_price: Optional[int] = None
    old_price: Optional[int] = None
    manage_elastic_boosting_through_price: bool = False

@dataclass
class ProductViewModel:
    sku: str
    name: str
    cost_price: float
    min_price: float
    current_price: Optional[float]
    marginality_percent: Optional[float]
    avg_week_margin: Optional[float]
    avg_month_margin: Optional[float]