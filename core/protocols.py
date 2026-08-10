"""
Infrastructure protocols - typed interfaces for external dependencies.

Defines Protocol classes for API client, Data Loader, Notifier, and Parser
to enable dependency injection and improve testability.
"""

from typing import Any, Protocol

from core.entities import PriceCalculationResult, PricingData, ProductInfo, StrategyInterval


class IApiClient(Protocol):
    """Protocol for Ozon API client."""

    async def get_product_ids_by_skus(self, skus: list[str]) -> dict[str, dict]:
        """Get product_id, offer_id, and product_name for a list of SKUs."""
        ...

    async def get_product_prices(self, product_ids: list[int]) -> list[PricingData]:
        """Get prices, indexes, and commissions for a list of product IDs."""
        ...

    async def update_prices(self, prices_data: list[dict]) -> dict[int, dict]:
        """Send price updates to Ozon API."""
        ...

    async def get_actions(self) -> list[dict]:
        """Get list of all available promotions/actions."""
        ...

    async def get_auto_add_products(
        self, action_id: int, auto_add_date: str, limit: int = 100, offset: int = 0
    ) -> dict:
        """Get products with auto-add for a specific action."""
        ...

    async def delete_auto_add_products(
        self, action_id: int, auto_add_date: str, product_ids: list[int]
    ) -> dict:
        """Delete products from auto-add in a promotion."""
        ...

    async def close(self) -> None:
        """Close the HTTP client."""
        ...


class IDataLoader(Protocol):
    """Protocol for Excel data loader."""

    def load(self) -> tuple[list[ProductInfo], list[str]]:
        """Load products from Excel file. Returns (products, warnings)."""
        ...

    def get_strategy_intervals(self, product: ProductInfo) -> list[StrategyInterval]:
        """Get strategy intervals for a product."""
        ...

    def update_product_in_file(self, sku: str, updates: dict[str, Any]) -> bool:
        """Update product data in Excel file."""
        ...

    def build_excel_updates(
        self,
        product: ProductInfo,
        result: PriceCalculationResult,
        marginality_week: float,
        marginality_month: float,
        old_price_update: int | None,
    ) -> dict[str, Any]:
        """Build updates dictionary for Excel from calculation results."""
        ...


class INotifier(Protocol):
    """Protocol for notification service."""

    def send_detailed_report(
        self,
        updates: list[dict[str, Any]],
        errors: list[str],
        dry_run: bool = False,
    ) -> None:
        """Send detailed email report with CSV attachment if needed."""
        ...


class IParser(Protocol):
    """Protocol for competitor price parser."""

    def get_price(self, product_url: str) -> float | None:
        """Get price from competitor product URL. Returns -1.0 if out of stock, None on error."""
        ...

    def close(self) -> None:
        """Close the parser and release resources."""
        ...

    def restart(self) -> None:
        """Restart the parser (recreate driver)."""
        ...
