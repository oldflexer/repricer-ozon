"""
Shared fixtures for pipeline step tests.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import time
from typing import Any

from core.domain.product import Product, PricingStrategy
from core.domain.value_objects import Money, Percentage, TimeInterval, SKU
from core.domain.pricing_rules import OzonPricingRules
from core.entities import (
    ProductInfo,
    PricingData,
    PriceCalculationResult,
    StrategyInterval,
)
from core.pipeline.steps.base import PipelineContext
from core.protocols.loader import ILoader
from core.protocols.repository import (
    IProductRepository,
    IPriceHistoryRepository,
    IAnalyticsRepository,
    IMarginalityRepository,
    IMaintenanceRepository,
)
from core.protocols.api import IApiClient
from core.protocols.notifier import INotifier
from core.services.price_calculation import PriceCalculationService
from core.services.real_price_sync import RealPriceSyncService
from core.enums import StrategyType


@pytest.fixture
def mock_loader() -> MagicMock:
    """Mock ILoader."""
    loader = MagicMock(spec=ILoader)
    loader.load.return_value = ([], [])
    loader._strategies = {}
    loader.update_product_in_file.return_value = True
    return loader


@pytest.fixture
def mock_product_repo() -> MagicMock:
    """Mock IProductRepository."""
    repo = MagicMock(spec=IProductRepository)
    repo.get_strategies.return_value = []
    repo.upsert_product.return_value = None
    repo.set_strategies.return_value = None
    return repo


@pytest.fixture
def mock_history_repo() -> MagicMock:
    """Mock IPriceHistoryRepository."""
    repo = MagicMock(spec=IPriceHistoryRepository)
    repo.save_price_history.return_value = None
    return repo


@pytest.fixture
def mock_analytics_repo() -> MagicMock:
    """Mock IAnalyticsRepository."""
    repo = MagicMock(spec=IAnalyticsRepository)
    return repo


@pytest.fixture
def mock_marginality_repo() -> MagicMock:
    """Mock IMarginalityRepository."""
    repo = MagicMock(spec=IMarginalityRepository)
    repo.save_marginality.return_value = None
    return repo


@pytest.fixture
def mock_maintenance_repo() -> MagicMock:
    """Mock IMaintenanceRepository."""
    repo = MagicMock(spec=IMaintenanceRepository)
    repo.auto_cleanup_if_needed.return_value = 0
    return repo


@pytest.fixture
def mock_api_client() -> AsyncMock:
    """Mock IApiClient."""
    client = AsyncMock(spec=IApiClient)
    client.get_product_ids_by_skus.return_value = {}
    client.get_product_prices.return_value = []
    client.update_prices.return_value = {}
    return client


@pytest.fixture
def mock_notifier() -> MagicMock:
    """Mock INotifier."""
    notifier = MagicMock(spec=INotifier)
    notifier.send_detailed_report.return_value = None
    notifier.notify_cycle_complete.return_value = None
    return notifier


@pytest.fixture
def mock_calculator() -> AsyncMock:
    """Mock PriceCalculationService."""
    calc = AsyncMock(spec=PriceCalculationService)
    calc.calculate.return_value = PriceCalculationResult(
        sku="TEST-001",
        target_min_price=100.0,
        strategy_price=150.0,
        target_strategy_price=150.0,
        result_target_price=150.0,
        marginality=25.0,
        log_details={
            "strategy_type_name": "BELOW",
            "discount_coef": 1.0,
            "min_price_validated": 100.0,
        },
    )
    return calc


@pytest.fixture
def mock_sync_service() -> AsyncMock:
    """Mock RealPriceSyncService."""
    service = AsyncMock(spec=RealPriceSyncService)
    service.sync_real_prices_async.return_value = {}
    return service


@pytest.fixture
def pricing_rules() -> OzonPricingRules:
    """Real OzonPricingRules instance for testing."""
    return OzonPricingRules()


@pytest.fixture
def sample_product() -> Product:
    """Sample product for testing."""
    return Product(
        sku=SKU("TEST-001"),
        product_id=12345,
        offer_id="67890",
        product_name="Test Product",
        cost_price=Money.from_rubles(100.0),
        min_price=Money.from_rubles(120.0),
        current_price=Money.from_rubles(150.0),
        old_price=Money.from_rubles(140.0),
        competitor_min_price=Money.from_rubles(130.0),
        real_customer_price=Money.from_rubles(145.0),
        strategies=[
            PricingStrategy(
                interval=TimeInterval(start_hour=9, start_minute=0, end_hour=18, end_minute=0),
                strategy_type=StrategyType.BELOW,
                percent=Percentage.from_ratio(0.05),
            )
        ],
    )


@pytest.fixture
def sample_product_no_id() -> Product:
    """Sample product without product_id for testing edge cases."""
    return Product(
        sku=SKU("TEST-002"),
        product_id=None,
        offer_id=None,
        product_name="Test Product No ID",
        cost_price=Money.from_rubles(100.0),
        min_price=Money.from_rubles(120.0),
        current_price=Money.from_rubles(150.0),
    )


@pytest.fixture
def sample_product_info() -> ProductInfo:
    """Sample ProductInfo entity."""
    return ProductInfo(
        sku="TEST-001",
        product_id=12345,
        offer_id="67890",
        product_name="Test Product",
        cost_price=100.0,
        min_price=120.0,
        current_price=150.0,
        old_price=140.0,
        real_customer_price=145.0,
        competitor_min_price=130.0,
    )


@pytest.fixture
def sample_pricing_data() -> PricingData:
    """Sample PricingData entity."""
    return PricingData(
        product_id=12345,
        price=150.0,
        old_price=140.0,
        min_price=120.0,
        net_price=100.0,
        marketing_seller_price=145.0,
        acquiring=2.0,
        sales_percent_fbs=15.0,
        sales_percent_fbo=18.0,
        fbs_deliv_to_customer_amount=20.0,
        fbo_deliv_to_customer_amount=25.0,
    )


@pytest.fixture
def sample_strategy_intervals() -> list[StrategyInterval]:
    """Sample StrategyInterval entities."""
    return [
        StrategyInterval(
            start="09:00",
            end="18:00",
            strategy_type=StrategyType.BELOW,
            percent=5.0,
        )
    ]


@pytest.fixture
def pipeline_context() -> PipelineContext:
    """Fresh PipelineContext for each test."""
    return PipelineContext(dry_run=True)


@pytest.fixture
def pipeline_context_with_products(pipeline_context: PipelineContext, sample_product: Product) -> PipelineContext:
    """PipelineContext with sample products."""
    pipeline_context.products = [sample_product]
    return pipeline_context


@pytest.fixture
def pipeline_context_full(
    pipeline_context: PipelineContext,
    sample_product: Product,
    sample_pricing_data: PricingData,
) -> PipelineContext:
    """PipelineContext with products and pricing data."""
    pipeline_context.products = [sample_product]
    pipeline_context.pricing_data = {12345: sample_pricing_data}
    pipeline_context.current_time = time(12, 0)
    return pipeline_context


# Type alias for test context
TestContext = dict[str, Any]