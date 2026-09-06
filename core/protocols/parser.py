"""
Protocol for Ozon price parser.

Defines the interface for fetching prices from Ozon product pages.
"""

from typing import Protocol


class OzonPriceParserProtocol(Protocol):
    """Protocol for Ozon price parser implementations."""

    def get_price(self, product_url: str) -> float | None:
        """
        Get price from Ozon product page.

        Args:
            product_url: Full URL to the Ozon product page.

        Returns:
            Price as float, -1.0 if product is out of stock,
            or None if price could not be determined.
        """
        ...

    def close(self) -> None:
        """Close the parser and release resources."""
        ...

    def restart(self) -> None:
        """Restart the parser (e.g., reinitialize browser/connection)."""
        ...