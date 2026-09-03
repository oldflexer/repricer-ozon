"""
Tests for SaveHistoryStep.
"""
import pytest
from unittest.mock import MagicMock
from core.pipeline.steps.save_history import SaveHistoryStep, _convert_product_to_product_info, _convert_pricing_strategies_to_intervals
from core.pipeline.steps.base import PipelineContext
from core.entities import PriceCalculationResult, ProductInfo, StrategyInterval
from core.domain.product import Product, PricingStrategy
from core.domain.value_objects import SKU, Money, Percentage, TimeInterval
from core.enums import StrategyType


class TestConvertProductToProductInfo:
    """Tests for _convert_product_to_product_info helper."""

    def test_convert_basic(self, sample_product):
        """Test basic conversion."""
        product_info = _convert_product_to_product_info(sample_product)

        assert isinstance(product_info, ProductInfo)
        assert product_info.sku == "TEST-001"
        assert product_info.product_id == 12345
        assert product_info.offer_id == "67890"
        assert product_info.product_name == "Test Product"
        assert product_info.cost_price == 100.0
        assert product_info.min_price == 120.0
        assert product_info.current_price == 150.0
        assert product_info.old_price == 140.0
        assert product_info.real_customer_price == 145.0
        assert product_info.competitor_min_price == 130.0


class TestConvertPricingStrategiesToIntervals:
    """Tests for _convert_pricing_strategies_to_intervals helper."""

    def test_convert_strategies(self, sample_product):
        """Test conversion of strategies to intervals."""
        intervals = _convert_pricing_strategies_to_intervals(sample_product.strategies)

        assert len(intervals) == 1
        interval = intervals[0]
        assert isinstance(interval, StrategyInterval)
        assert interval.start == "09:00"
        assert interval.end == "18:00"
        assert interval.strategy_type.value == 1  # StrategyType.BELOW = 1
        assert interval.percent == 5.0


class TestSaveHistoryStep:
    """Tests for SaveHistoryStep."""

    @pytest.fixture
    def step(self, mock_product_repo, mock_history_repo, mock_analytics_repo, mock_marginality_repo):
        return SaveHistoryStep(
            product_repo=mock_product_repo,
            history_repo=mock_history_repo,
            analytics_repo=mock_analytics_repo,
            marginality_repo=mock_marginality_repo,
        )

    @pytest.fixture
    def sample_calculation_result(self) -> PriceCalculationResult:
        """Sample PriceCalculationResult for testing."""
        return PriceCalculationResult(
            sku="TEST-001",
            target_min_price=100.0,
            strategy_price=150.0,
            target_strategy_price=150.0,
            result_target_price=150.0,
            marginality=25.0,
            log_details={"discount_coef": 1.0},
        )

    @pytest.mark.asyncio
    async def test_execute_success(self, step, mock_product_repo, mock_history_repo, mock_marginality_repo, pipeline_context_full, sample_pricing_data, sample_calculation_result):
        """Test successful history saving."""
        pipeline_context_full.calculation_results["TEST-001"] = sample_calculation_result

        await step.execute(pipeline_context_full)

        mock_product_repo.upsert_product.assert_called_once()
        mock_product_repo.set_strategies.assert_called_once()
        mock_history_repo.save_price_history.assert_called_once()
        mock_marginality_repo.save_marginality.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_skips_no_result(self, step, mock_product_repo, pipeline_context_full):
        """Test skips products without calculation result."""
        await step.execute(pipeline_context_full)

        mock_product_repo.upsert_product.assert_not_called()
        mock_product_repo.set_strategies.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_skips_no_pricing_data(self, step, mock_product_repo, mock_history_repo, pipeline_context_with_products, sample_calculation_result):
        """Test skips price history when no pricing data."""
        pipeline_context_with_products.products[0].product_id = 12345
        pipeline_context_with_products.calculation_results["TEST-001"] = sample_calculation_result
        # No pricing data in context

        await step.execute(pipeline_context_with_products)

        mock_product_repo.upsert_product.assert_called_once()
        mock_history_repo.save_price_history.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_error_handling(self, step, mock_product_repo, pipeline_context_full, sample_calculation_result):
        """Test error handling when saving fails."""
        mock_product_repo.upsert_product.side_effect = Exception("DB Error")
        pipeline_context_full.calculation_results["TEST-001"] = sample_calculation_result

        await step.execute(pipeline_context_full)

        assert len(pipeline_context_full.errors) == 1
        assert "Failed to save history" in pipeline_context_full.errors[0]