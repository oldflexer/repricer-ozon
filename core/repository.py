from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime
from .entities import ProductInfo, StrategyInterval, PricingData, PriceCalculationResult

class IProductRepository(ABC):
    @abstractmethod
    def get_all_products(self) -> List[ProductInfo]: ...
    @abstractmethod
    def upsert_product(self, product: ProductInfo) -> bool: ...
    @abstractmethod
    def update_real_customer_price(self, sku: str, real_price: float) -> bool: ...
    @abstractmethod
    def get_strategies(self, sku: str) -> List[StrategyInterval]: ...
    @abstractmethod
    def set_strategies(self, sku: str, intervals: List[StrategyInterval]) -> bool: ...
    @abstractmethod
    def save_price_history(self, sku: str, pricing: PricingData,
                           result: PriceCalculationResult, real_price: Optional[float] = None) -> bool: ...
    @abstractmethod
    def get_price_history(self, sku: str) -> List[Dict[str, Any]]: ...
    @abstractmethod
    def save_marginality(self, sku: str, marginality: float,
                         marginality_week: float, marginality_month: float) -> bool: ...
    @abstractmethod
    def get_average_marginality(self, sku: str, days: int) -> Optional[float]: ...
    @abstractmethod
    def get_last_run_time(self) -> Optional[datetime]: ...


class ILoader(ABC):
    """Интерфейс для загрузки и обновления данных товаров."""
    @abstractmethod
    def load(self) -> List[ProductInfo]:
        """Загружает товары и их стратегии из источника."""
        pass

    @abstractmethod
    def get_strategy_intervals(self, product: ProductInfo) -> List[StrategyInterval]:
        """Возвращает интервалы стратегий для товара."""
        pass

    @abstractmethod
    def update_product_in_file(self, sku: str, updates: Dict[str, Any]) -> bool:
        """Обновляет данные товара в источнике."""
        pass