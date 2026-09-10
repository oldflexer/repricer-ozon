"""
Абстрактные интерфейсы для работы с хранилищем данных.

Определяет контракты для репозитория товаров и загрузчика данных из Excel.
"""

from abc import ABC, abstractmethod
from typing import Any

from .entities import ProductInfo, StrategyInterval
from .protocols.repository import (
    IAnalyticsRepository,
    IMaintenanceRepository,
    IMarginalityRepository,
    IPriceHistoryRepository,
    IProductRepository,
    IRepository,
)

__all__ = [
    "IProductRepository",
    "IPriceHistoryRepository",
    "IMarginalityRepository",
    "IAnalyticsRepository",
    "IMaintenanceRepository",
    "IRepository",
    "ILoader",
]


class ILoader(ABC):
    """Интерфейс загрузчика данных из Excel."""

    @abstractmethod
    def load(self) -> tuple[list[ProductInfo], list[str]]:
        """
        Загружает товары из Excel-файла.

        Returns:
            Кортеж (список товаров, список предупреждений/ошибок).
        """
        pass

    @abstractmethod
    def get_strategy_intervals(self, product: ProductInfo) -> list[StrategyInterval]:
        """
        Возвращает интервалы стратегий для заданного товара (из загруженных данных).

        Args:
            product: Объект товара.

        Returns:
            Список StrategyInterval.
        """
        pass

    @abstractmethod
    def update_product_in_file(self, sku: str, updates: dict[str, Any]) -> bool:
        """
        Обновляет данные товара в Excel-файле.

        Args:
            sku: Артикул товара.
            updates: Словарь с обновляемыми полями и их значениями.

        Returns:
            True в случае успеха.
        """
        pass
