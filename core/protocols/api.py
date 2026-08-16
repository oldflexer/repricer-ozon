"""
Протоколы (Interfaces) для API клиентов.

Определяют контракты для взаимодействия с внешними API.
"""

from abc import abstractmethod
from typing import Any, Protocol


class IApiClient(Protocol):
    """Интерфейс клиента Ozon Seller API."""

    @abstractmethod
    async def get_product_ids_by_skus(self, skus: list[str]) -> dict[str, dict]:
        """
        Получает product_id, offer_id и название для списка SKU.

        Args:
            skus: Список SKU (артикулов продавца).

        Returns:
            Словарь {sku: {product_id, offer_id, price, product_name}}.
        """
        ...

    @abstractmethod
    async def get_product_prices(self, product_ids: list[int]) -> list[Any]:
        """
        Получает цены, индексы и комиссии для списка товаров.

        Args:
            product_ids: Список идентификаторов товаров в Ozon.

        Returns:
            Список объектов PricingData.
        """
        ...

    @abstractmethod
    async def update_prices(self, prices_data: list[dict]) -> dict[int, dict]:
        """
        Отправляет новые цены в Ozon.

        Args:
            prices_data: Список словарей с полями:
                product_id, offer_id, price, min_price, net_price,
                old_price, manage_elastic_boosting_through_price.

        Returns:
            Словарь {product_id: {"updated": bool, "errors": list}}.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Закрывает HTTP-клиент и освобождает ресурсы."""
        ...

    # Опциональные методы для работы с акциями
    @abstractmethod
    async def get_actions(self) -> list[dict]:
        """Получает список всех доступных акций."""
        ...

    @abstractmethod
    async def get_auto_add_products(
        self, action_id: int, auto_add_date: str, limit: int = 100, offset: int = 0
    ) -> dict:
        """Получает список товаров с автодобавлением для конкретной акции."""
        ...

    @abstractmethod
    async def delete_auto_add_products(
        self, action_id: int, auto_add_date: str, product_ids: list[int]
    ) -> dict:
        """Удаляет товары из автодобавления в акцию."""
        ...

    @abstractmethod
    async def update_price_timer(self, product_ids: list[int]) -> dict[int, dict]:
        """Обновляет таймер актуальности минимальной цены для указанных товаров."""
        ...


class ICompetitorPriceParser(Protocol):
    """Интерфейс парсера цен конкурентов."""

    @abstractmethod
    async def get_price(self, product_url: str) -> float | None:
        """
        Получает цену товара по его URL.

        Args:
            product_url: Полный URL страницы товара на Ozon.

        Returns:
            Цена в виде float, -1.0 если товар закончился, или None при ошибке.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Закрывает парсер и освобождает ресурсы."""
        ...

    @abstractmethod
    async def restart(self) -> None:
        """Перезапускает парсер (например, после ошибки)."""
        ...
