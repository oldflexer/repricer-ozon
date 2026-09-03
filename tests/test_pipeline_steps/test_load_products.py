"""
Tests for LoadProductsStep.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from core.pipeline.steps.load_products import LoadProductsStep, _convert_product_info_to_product
from core.pipeline.steps.base import PipelineContext
from core.entities import ProductInfo, StrategyInterval
from core.domain.product import Product, PricingStrategy
from core.domain.value_objects import SKU, Money, Percentage, TimeInterval
from core.enums import StrategyType


class TestConvertProductInfoToProduct:
    """Tests for _convert_product_info_to_product helper."""

    def test_convert_basic(self, sample_product_info):
        """Test basic conversion."""
        product = _convert_product_info_to_product(sample_product_info)

        assert product.sku == SKU("TEST-001")
        assert product.product_id == 12345
        assert product.offer_id == "67890"
        assert product.product_name == "Test Product"
        assert product.cost_price == Money.from_rubles(100.0)
        assert product.min_price == Money.from_rubles(120.0)
        assert product.current_price == Money.from_rubles(150.0)
        assert product.old_price == Money.from_rubles(140.0)
        assert product.real_customer_price == Money.from_rubles(145.0)
        assert product.competitor_min_price == Money.from_rubles(130.0)
        assert product.strategies == []

    def test_convert_with_strategies(self, sample_product_info, sample_strategy_intervals):
        """Test conversion with strategies."""
        product = _convert_product_info_to_product(sample_product_info, sample_strategy_intervals)

        assert len(product.strategies) == 1
        strategy = product.strategies[0]
        assert strategy.interval.start_hour == 9
        assert strategy.interval.end_hour == 18
        assert strategy.strategy_type.value == 1  # StrategyType.BELOW = 1
        assert strategy.percent.percent_float == 5.0


class TestLoadProductsStep:
    """Tests for LoadProductsStep."""

    @pytest.fixture
    def step(self, mock_loader, mock_product_repo):
        return LoadProductsStep(loader=mock_loader, product_repo=mock_product_repo)

    @pytest.mark.asyncio
    async def test_execute_success(self, step, mock_loader, mock_product_repo, pipeline_context, sample_product_info):
        """Test successful product loading."""
        mock_loader.load.return_value = ([sample_product_info], [])
        mock_product_repo.get_strategies.return_value = []

        await step.execute(pipeline_context)

        assert len(pipeline_context.products) == 1
        assert pipeline_context.products[0].sku == SKU("TEST-001")
        mock_loader.load.assert_called_once()
        mock_product_repo.get_strategies.assert_called_once_with("TEST-001")

    @pytest.mark.asyncio
    async def test_execute_with_loader_strategies(self, step, mock_loader, mock_product_repo, pipeline_context, sample_product_info, sample_strategy_intervals):
        """Test loading with strategies from loader."""
        mock_loader.load.return_value = ([sample_product_info], [])
        mock_loader._strategies = {"TEST-001": sample_strategy_intervals}
        mock_product_repo.get_strategies.return_value = []

        await step.execute(pipeline_context)

        assert len(pipeline_context.products[0].strategies) == 1

    @pytest.mark.asyncio
    async def test_execute_with_db_strategies(self, step, mock_loader, mock_product_repo, pipeline_context, sample_product_info, sample_strategy_intervals):
        """Test loading with strategies from database."""
        mock_loader.load.return_value = ([sample_product_info], [])
        mock_loader._strategies = {}
        mock_product_repo.get_strategies.return_value = sample_strategy_intervals

        await step.execute(pipeline_context)

        assert len(pipeline_context.products[0].strategies) == 1

    @pytest.mark.asyncio
    async def test_execute_warnings(self, step, mock_loader, pipeline_context):
        """Test warnings from loader are added to context."""
        mock_loader.load.return_value = ([], ["Warning 1", "Warning 2"])

        await step.execute(pipeline_context)

        assert len(pipeline_context.warnings) == 2
        assert "Warning 1" in pipeline_context.warnings
        assert "Warning 2" in pipeline_context.warnings

    @pytest.mark.asyncio
    async def test_execute_error_handling(self, step, mock_loader, pipeline_context):
        """Test error handling when loader fails."""
        mock_loader.load.side_effect = Exception("Load failed")

        await step.execute(pipeline_context)

        assert len(pipeline_context.errors) == 1
        assert "Failed to load products" in pipeline_context.errors[0]
        assert pipeline_context.should_stop is True