"""
Абстрактные интерфейсы для работы с хранилищем данных.

Определяет контракты для репозитория товаров и загрузчика данных из Excel.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import pandas as pd

from .entities import PriceCalculationResult, PricingData, ProductInfo, StrategyInterval


class IProductRepository(ABC):
    """Интерфейс репозитория для работы с товарами, стратегиями и историей."""

    @abstractmethod
    def get_all_products(self) -> list[ProductInfo]:
        """Возвращает список всех товаров из БД."""
        pass

    @abstractmethod
    def upsert_product(self, product: ProductInfo) -> bool:
        """
        Создаёт или обновляет запись о товаре.

        Args:
            product: Данные товара.

        Returns:
            True в случае успеха.
        """
        pass

    @abstractmethod
    def update_real_customer_price(self, sku: str, real_price: float) -> bool:
        """
        Обновляет реальную цену покупателя для товара.

        Args:
            sku: Артикул товара.
            real_price: Реальная цена.

        Returns:
            True в случае успеха.
        """
        pass

    @abstractmethod
    def get_strategies(self, sku: str) -> list[StrategyInterval]:
        """
        Возвращает список интервалов стратегий для товара.

        Args:
            sku: Артикул товара.

        Returns:
            Список StrategyInterval.
        """
        pass

    @abstractmethod
    def set_strategies(self, sku: str, intervals: list[StrategyInterval]) -> bool:
        """
        Сохраняет интервалы стратегий для товара (заменяя существующие).

        Args:
            sku: Артикул товара.
            intervals: Список интервалов.

        Returns:
            True в случае успеха.
        """
        pass

    @abstractmethod
    def save_price_history(
        self,
        sku: str,
        pricing: PricingData,
        result: PriceCalculationResult,
        real_price: float | None = None,
    ) -> bool:
        """
        Сохраняет запись истории цен для товара.

        Args:
            sku: Артикул товара.
            pricing: Данные о ценах и комиссиях из API.
            result: Результат расчёта целевой цены и маржинальности.
            real_price: Реальная цена покупателя (опционально).

        Returns:
            True в случае успеха.
        """
        pass

    @abstractmethod
    def get_price_history(self, sku: str) -> list[dict[str, Any]]:
        """
        Возвращает историю цен для товара.

        Args:
            sku: Артикул товара.

        Returns:
            Список словарей с ключами: timestamp, customer_price, marginality.
        """
        pass

    @abstractmethod
    def save_marginality(
        self,
        sku: str,
        marginality: float,
        marginality_week: float,
        marginality_month: float,
    ) -> bool:
        """
        Сохраняет значения маржинальности (текущую, за неделю, за месяц).

        Args:
            sku: Артикул товара.
            marginality: Текущая маржинальность.
            marginality_week: Средняя за неделю.
            marginality_month: Средняя за месяц.

        Returns:
            True в случае успеха.
        """
        pass

    @abstractmethod
    def get_average_marginality(self, sku: str, days: int) -> float | None:
        """
        Возвращает среднюю маржинальность за указанное количество дней.

        Args:
            sku: Артикул товара.
            days: Количество дней.

        Returns:
            Средняя маржинальность в долях или None, если данных нет.
        """
        pass

    @abstractmethod
    def get_last_run_time(self) -> datetime | None:
        """
        Возвращает время последнего успешного запуска репрайсинга (по последней записи истории).

        Returns:
            Объект datetime или None, если данных нет.
        """
        pass

    # ---------- Обслуживание ----------

    @abstractmethod
    def delete_old_records(self, days: int) -> int:
        """
        Удаляет записи истории старше указанного количества дней.

        Args:
            days: Количество дней.

        Returns:
            Количество удалённых записей.
        """
        pass

    @abstractmethod
    def delete_records_older_than(self, months: int = 3) -> int:
        """
        Удаляет записи истории старше указанного количества месяцев.

        Args:
            months: Количество месяцев.

        Returns:
            Количество удалённых записей.
        """
        pass

    @abstractmethod
    def get_last_cleanup_date(self) -> datetime | None:
        """
        Возвращает дату последней автоматической очистки БД.

        Returns:
            Объект datetime или None.
        """
        pass

    @abstractmethod
    def set_last_cleanup_date(self, dt: datetime) -> None:
        """
        Устанавливает дату последней автоматической очистки БД.

        Args:
            dt: Дата и время очистки.
        """
        pass

    @abstractmethod
    def auto_cleanup_if_needed(self, months: int = 3, days_threshold: int = 1) -> int:
        """
        Запускает очистку БД, если с последней очистки прошло больше days_threshold дней.

        Args:
            months: Срок хранения данных в месяцах.
            days_threshold: Минимальное количество дней между очистками.

        Returns:
            Количество удалённых записей (0, если очистка не выполнялась).
        """
        pass

    # ---------- Агрегация и аналитика ----------

    @abstractmethod
    def save_daily_aggregates(
        self,
        sku: str,
        pricing: PricingData,
        result: PriceCalculationResult,
        real_price: float | None = None,
    ) -> None:
        """
        Сохраняет агрегированные данные за текущий день (avg, min, max).

        Args:
            sku: Артикул товара.
            pricing: Данные о ценах.
            result: Результат расчёта.
            real_price: Реальная цена покупателя (опционально).
        """
        pass

    @abstractmethod
    def get_daily_trends_aggregated(self, days: int = 7) -> pd.DataFrame:
        """
        Возвращает агрегированные дневные тренды (средняя цена и маржинальность) за указанный период.

        Args:
            days: Количество дней.

        Returns:
            DataFrame с колонками: day, avg_price, avg_margin.
        """
        pass


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
