"""
Dependency Injection Container using dependency-injector.

Provides a declarative container for all dependencies with proper scoping.
"""

from collections.abc import AsyncGenerator
from typing import cast

from dependency_injector import containers, providers

from config.settings import settings
from core.pipeline.orchestrator import PipelineDependencies, create_repricing_pipeline
from core.protocols.repository import (
    IAnalyticsRepository,
    IMaintenanceRepository,
    IMarginalityRepository,
    IPriceHistoryRepository,
    IProductRepository,
)
from core.services.price_calculation import PriceCalculationService
from core.use_cases.disable_auto_add import DisableAutoAddUseCase
from core.use_cases.parse_competitor_prices import ParseCompetitorPricesUseCase
from core.use_cases.repricing import RepricingUseCase
from infrastructure.db import SQLiteRepository
from infrastructure.excel_loader import ExcelLoader
from infrastructure.mail_notifier import MailNotifier
from infrastructure.ozon_api import OzonApiClient
from infrastructure.ozon_competitor import OzonPriceParser


class Container(containers.DeclarativeContainer):
    """Declarative DI container with proper scoping."""

    # Configuration
    config = providers.Configuration()

    # ------------------------------------------------------------------
    # Infrastructure singletons
    # ------------------------------------------------------------------

    repository = providers.Singleton(
        SQLiteRepository,
        db_path=config.db.path,
    )

    api_client = providers.Singleton(
        OzonApiClient,
    )

    loader = providers.Singleton(
        ExcelLoader,
        file_path=config.data.path,
    )

    notifier = providers.Singleton(
        MailNotifier,
    )

    # ------------------------------------------------------------------
    # Infrastructure (Factory - new instance each time)
    # ------------------------------------------------------------------

    parser = providers.Factory(
        OzonPriceParser,
    )

    # ------------------------------------------------------------------
    # Core Services (Singletons)
    # ------------------------------------------------------------------

    price_calculation_service = providers.Singleton(
        PriceCalculationService,
        default_coefficient=config.pricing.coefficient_ozon,
    )

    # ------------------------------------------------------------------
    # Repository protocols (extracted from the main repository)
    # ------------------------------------------------------------------

    product_repo: IProductRepository = cast(IProductRepository, repository)
    history_repo: IPriceHistoryRepository = cast(IPriceHistoryRepository, repository)
    analytics_repo: IAnalyticsRepository = cast(IAnalyticsRepository, repository)
    marginality_repo: IMarginalityRepository = cast(IMarginalityRepository, repository)
    maintenance_repo: IMaintenanceRepository = cast(IMaintenanceRepository, repository)

    # ------------------------------------------------------------------
    # Coordinators / Use Cases (Factories - new for each run)
    # ------------------------------------------------------------------

    repricing_use_case = providers.Factory(
        RepricingUseCase,
        product_repo=product_repo,
        history_repo=history_repo,
        analytics_repo=analytics_repo,
        marginality_repo=marginality_repo,
        maintenance_repo=maintenance_repo,
        api_client=api_client,
        mail_notifier=notifier,
        loader=loader,
    )

    disable_auto_add_use_case = providers.Factory(
        DisableAutoAddUseCase,
        api_client=api_client,
    )

    parse_competitor_prices_use_case = providers.Factory(
        ParseCompetitorPricesUseCase,
        parser=parser,
    )

    # ------------------------------------------------------------------
    # Pipeline (Factory - new for each run)
    # ------------------------------------------------------------------

    repricing_pipeline = providers.Factory(
        create_repricing_pipeline,
        deps=providers.Factory(
            PipelineDependencies,
            loader=loader,
            api_client=api_client,
            product_repo=product_repo,
            history_repo=history_repo,
            analytics_repo=analytics_repo,
            marginality_repo=marginality_repo,
            maintenance_repo=maintenance_repo,
            notifier=notifier,
            calculator=price_calculation_service,
            dry_run=False,  # Will be overridden per call
        ),
    )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @providers.Resource
    async def api_client_lifecycle(self) -> AsyncGenerator[OzonApiClient, None]:
        """Manages API client lifecycle."""
        client = OzonApiClient()
        yield client
        await client.close()


# Create container instance and wire configuration
container = Container()
container.config.from_pydantic(settings)

# Export for backward compatibility
__all__ = ["container"]
