"""
Протоколы (Interfaces) для загрузчиков данных.

Определяют контракты для работы с Excel и другими источниками данных.
"""

from abc import abstractmethod
from typing import Any, Protocol

from core.entities import ProductInfo, StrategyInterval


class ILoader(Protocol):
    """Интерфейс загрузчика данных из Excel."""

    @abstractmethod
    def load(self) -> tuple[list[ProductInfo], list[str]]:
        """
        Загружает товары из Excel-файла.

        Returns:
            Кортеж (список товаров, список предупреждений/ошибок).
        """
        ...

    @abstractmethod
    def get_strategy_intervals(self, product: ProductInfo) -> list[StrategyInterval]:
        """
        Возвращает интервалы стратегий для заданного товара (из загруженных данных).

        Args:
            product: Объект товара.

        Returns:
            Список StrategyInterval.
        """
        ...

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
        ...
