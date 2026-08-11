"""
Simple Dependency Injection Container for the Ozon Repricer.

Provides a single point of configuration for all dependencies
using plain Python (no external DI library).
"""

from config.settings import settings
from core.price_coordinator import PriceUpdateCoordinator
from core.services.price_calculation import PriceCalculationService
from core.use_cases.disable_auto_add import DisableAutoAddUseCase
from core.use_cases.repricing import RepricingUseCase
from infrastructure.db import SQLiteRepository
from infrastructure.excel_loader import ExcelLoader
from infrastructure.mail_notifier import MailNotifier
from infrastructure.ozon_api import OzonApiClient
from infrastructure.ozon_competitor import OzonPriceParser


class Container:
    """Simple DI container managing component lifecycle."""

    def __init__(self):
        self._repository = None
        self._api_client = None
        self._loader = None
        self._notifier = None
        self._parser = None
        self._price_calculation_service = None

    # ------------------------------------------------------------------
    # Infrastructure singletons
    # ------------------------------------------------------------------

    @property
    def repository(self) -> SQLiteRepository:
        """Get or create the database repository (singleton)."""
        if self._repository is None:
            self._repository = SQLiteRepository(settings.DATABASE_PATH_PATH)
        return self._repository

    @property
    def api_client(self) -> OzonApiClient:
        """Get or create the Ozon API client (singleton)."""
        if self._api_client is None:
            self._api_client = OzonApiClient()
        return self._api_client

    @property
    def loader(self) -> ExcelLoader:
        """Get or create the Excel loader (singleton)."""
        if self._loader is None:
            self._loader = ExcelLoader(settings.DATA_FILE_PATH)
        return self._loader

    @property
    def notifier(self) -> MailNotifier:
        """Get or create the mail notifier (singleton)."""
        if self._notifier is None:
            self._notifier = MailNotifier()
        return self._notifier

    # ------------------------------------------------------------------
    # Infrastructure (Factory - new instance each time)
    # ------------------------------------------------------------------

    def parser(self) -> OzonPriceParser:
        """Create a new parser instance (factory)."""
        return OzonPriceParser()

    # ------------------------------------------------------------------
    # Core Services (Singletons)
    # ------------------------------------------------------------------

    @property
    def price_calculation_service(self) -> PriceCalculationService:
        """Get or create the price calculation service (singleton)."""
        if self._price_calculation_service is None:
            self._price_calculation_service = PriceCalculationService(
                default_coefficient=settings.COEFFICIENT_OZON
            )
        return self._price_calculation_service

    # ------------------------------------------------------------------
    # Coordinators / Use Cases (Factories - new for each run)
    # ------------------------------------------------------------------

    def price_coordinator(self) -> PriceUpdateCoordinator:
        """Create a new price update coordinator."""
        return PriceUpdateCoordinator(
            repository=self.repository,
            api_client=self.api_client,
            loader=self.loader,
            notifier=self.notifier,
        )

    def repricing_use_case(self) -> RepricingUseCase:
        """Create a new repricing use case."""
        return RepricingUseCase(
            repository=self.repository,
            api_client=self.api_client,
            mail_notifier=self.notifier,
            loader=self.loader,
        )

    def disable_auto_add_use_case(self) -> DisableAutoAddUseCase:
        """Create a new disable auto-add use case."""
        return DisableAutoAddUseCase(
            api_client=self.api_client,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close all resources (API client connections, etc.)."""
        if self._api_client is not None:
            await self._api_client.close()
            self._api_client = None


# Global container instance
container = Container()

