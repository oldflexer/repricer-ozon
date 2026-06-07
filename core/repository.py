from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from .entities import ProductInfo, StrategyInterval, PricingData, PriceCalculationResult


class IProductRepository(ABC):
    @abstractmethod
    def get_all_products(self) -> List[ProductInfo]:
        pass

    @abstractmethod
    def upsert_product(self, product: ProductInfo) -> bool:
        pass

    @abstractmethod
    def update_real_customer_price(self, sku: str, real_price: float) -> bool:
        pass

    @abstractmethod
    def get_strategies(self, sku: str) -> List[StrategyInterval]:
        pass

    @abstractmethod
    def set_strategies(self, sku: str, intervals: List[StrategyInterval]) -> bool:
        pass

    @abstractmethod
    def save_price_history(self, sku: str, pricing: PricingData,
                           result: PriceCalculationResult, real_price: Optional[float] = None) -> bool:
        pass

    @abstractmethod
    def get_price_history(self, sku: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def save_marginality(self, sku: str, marginality: float,
                         marginality_week: float, marginality_month: float) -> bool:
        pass

    @abstractmethod
    def get_average_marginality(self, sku: str, days: int) -> Optional[float]:
        pass

    @abstractmethod
    def get_last_run_time(self) -> Optional[datetime]:
        pass

    # ------------------- Обслуживание БД (ручная очистка) -------------------
    @abstractmethod
    def delete_old_records(self, days: int) -> int:
        """Ручная очистка записей старше указанного количества дней."""
        pass

    # ------------------- Автоматическая очистка (старше 3 месяцев) -------------------
    @abstractmethod
    def delete_records_older_than(self, months: int = 3) -> int:
        """Удаляет записи старше указанного числа месяцев."""
        pass

    @abstractmethod
    def get_last_cleanup_date(self) -> Optional[datetime]:
        """Возвращает дату последней автоматической очистки."""
        pass

    @abstractmethod
    def set_last_cleanup_date(self, dt: datetime):
        """Сохраняет дату последней очистки."""
        pass

    @abstractmethod
    def auto_cleanup_if_needed(self, months: int = 3, days_threshold: int = 1) -> int:
        """
        Автоматически запускает очистку, если с последней очистки прошло больше days_threshold дней.
        Возвращает количество удалённых записей (0, если очистка не производилась).
        """
        pass


class ILoader(ABC):
    @abstractmethod
    def load(self) -> Tuple[List[ProductInfo], List[str]]:
        pass

    @abstractmethod
    def get_strategy_intervals(self, product: ProductInfo) -> List[StrategyInterval]:
        pass

    @abstractmethod
    def update_product_in_file(self, sku: str, updates: Dict[str, Any]) -> bool:
        pass