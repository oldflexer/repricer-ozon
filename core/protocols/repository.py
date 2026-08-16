"""
Специализированные протоколы репозиториев (Interface Segregation Principle).

Разбивает монолитный IProductRepository на узкоспециализированные интерфейсы.
"""

from abc import abstractmethod
from datetime import datetime
from typing import Any, Protocol

import pandas as pd

from core.entities import PriceCalculationResult, PricingData, ProductInfo, StrategyInterval


class IProductRepository(Protocol):
    """Репозиторий для CRUD операций с товарами и стратегиями."""

    @abstractmethod
    def get_all_products(self) -> list[ProductInfo]:
        """Возвращает список всех товаров из БД."""
        ...

    @abstractmethod
    def upsert_product(self, product: ProductInfo) -> bool:
        """Создаёт или обновляет запись о товаре."""
        ...

    @abstractmethod
    def update_real_customer_price(self, sku: str, real_price: float) -> bool:
        """Обновляет реальную цену покупателя для товара."""
        ...

    @abstractmethod
    def get_strategies(self, sku: str) -> list[StrategyInterval]:
        """Возвращает список интервалов стратегий для товара."""
        ...

    @abstractmethod
    def set_strategies(self, sku: str, intervals: list[StrategyInterval]) -> bool:
        """Сохраняет интервалы стратегий для товара (заменяя существующие)."""
        ...


class IPriceHistoryRepository(Protocol):
    """Репозиторий для работы с историей цен."""

    @abstractmethod
    def save_price_history(
        self,
        sku: str,
        pricing: PricingData,
        result: PriceCalculationResult,
        real_price: float | None = None,
    ) -> bool:
        """Сохраняет запись истории цен для товара."""
        ...

    @abstractmethod
    def get_price_history(self, sku: str) -> list[dict[str, Any]]:
        """
        Возвращает историю цен для товара.

        Returns:
            Список словарей с ключами: timestamp, customer_price, marginality.
        """
        ...

    @abstractmethod
    def get_last_run_time(self) -> datetime | None:
        """Возвращает время последнего успешного запуска репрайсинга."""
        ...


class IMarginalityRepository(Protocol):
    """Репозиторий для работы с маржинальностью."""

    @abstractmethod
    def save_marginality(
        self,
        sku: str,
        marginality: float,
        marginality_week: float,
        marginality_month: float,
    ) -> bool:
        """Сохраняет значения маржинальности (текущую, за неделю, за месяц)."""
        ...

    @abstractmethod
    def get_average_marginality(self, sku: str, days: int) -> float | None:
        """Возвращает среднюю маржинальность за указанное количество дней."""
        ...


class IAnalyticsRepository(Protocol):
    """Репозиторий для аналитических запросов (дашборд, отчёты)."""

    @abstractmethod
    def save_daily_aggregates(
        self,
        sku: str,
        result: PriceCalculationResult,
        real_price: float | None = None,
    ) -> None:
        """Сохраняет агрегированные данные за текущий день (avg, min, max)."""
        ...

    @abstractmethod
    def get_daily_trends_aggregated(self, days: int = 7) -> pd.DataFrame:
        """
        Возвращает агрегированные дневные тренды за указанный период.

        Returns:
            DataFrame с колонками: day, avg_price, avg_margin.
        """
        ...

    @abstractmethod
    def get_daily_deviation(self, days: int = 30) -> pd.DataFrame:
        """Возвращает среднее отношение цены к индексу Ozon по дням."""
        ...

    @abstractmethod
    def get_kpi_metrics(self) -> dict[str, Any]:
        """Возвращает KPI метрики для дашборда."""
        ...

    @abstractmethod
    def get_strategy_roi(self) -> pd.DataFrame:
        """Возвращает ROI по стратегиям."""
        ...

    @abstractmethod
    def get_ozon_index_vs_price(self) -> pd.DataFrame:
        """Возвращает сравнение цены и индекса Ozon."""
        ...

    @abstractmethod
    def get_all_last_prices(self) -> pd.DataFrame:
        """Возвращает последние цены и маржинальность для всех товаров."""
        ...

    @abstractmethod
    def get_top_bottom_marginality(self, limit: int = 3) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Возвращает топ и худшие товары по маржинальности."""
        ...


class IMaintenanceRepository(Protocol):
    """Репозиторий для обслуживания БД (очистка, настройки)."""

    @abstractmethod
    def delete_old_records(self, days: int) -> int:
        """Удаляет записи истории старше указанного количества дней."""
        ...

    @abstractmethod
    def delete_records_older_than(self, months: int = 3) -> int:
        """Удаляет записи истории старше указанного количества месяцев."""
        ...

    @abstractmethod
    def get_last_cleanup_date(self) -> datetime | None:
        """Возвращает дату последней автоматической очистки БД."""
        ...

    @abstractmethod
    def set_last_cleanup_date(self, dt: datetime) -> None:
        """Устанавливает дату последней автоматической очистки БД."""
        ...

    @abstractmethod
    def auto_cleanup_if_needed(self, months: int = 3, days_threshold: int = 1) -> int:
        """
        Запускает очистку БД, если с последней очистки прошло больше days_threshold дней.

        Returns:
            Количество удалённых записей (0, если очистка не выполнялась).
        """
        ...


# Композитный протокол для обратной совместимости
class IRepository(
    IProductRepository,
    IPriceHistoryRepository,
    IMarginalityRepository,
    IAnalyticsRepository,
    IMaintenanceRepository,
    Protocol,
):
    """Полный интерфейс репозитория (для постепенной миграции)."""

    ...
