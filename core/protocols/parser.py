"""
Protocol for Ozon competitor price parser.

Defines the interface for fetching competitor prices from Ozon product pages.
"""

from abc import ABC, abstractmethod
from typing import Protocol


class OzonPriceParserProtocol(Protocol):
    """Protocol for Ozon price parser implementations."""

    async def get_price(self, product_url: str) -> float | None:
        """
        Get competitor price from Ozon product page.

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


class OzonPriceParserBase(ABC):
    """Abstract base class for Ozon price parsers."""

    @abstractmethod
    async def get_price(self, product_url: str) -> float | None:
        """Get competitor price from Ozon product page."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the parser and release resources."""
        pass

    @abstractmethod
    def restart(self) -> None:
        """Restart the parser."""
        pass