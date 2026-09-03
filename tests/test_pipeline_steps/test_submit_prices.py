"""
Tests for SubmitPricesToOzonStep.
"""
import pytest
from unittest.mock import AsyncMock
from core.pipeline.steps.submit_prices import SubmitPricesToOzonStep
from core.pipeline.steps.base import PipelineContext
from core.entities import PriceCalculationResult
from core.domain.product import Product
from core.domain.value_objects import SKU, Money, Percentage, TimeInterval
from core.domain.pricing_rules import OzonPricingRules
from core.enums import StrategyType


class TestSubmitPricesToOzonStep:
    """Tests for SubmitPricesToOzonStep."""

    @pytest.fixture
    def step(self, mock_api_client, pricing_rules):
        return SubmitPricesToOzonStep(api_client=mock_api_client, pricing_rules=pricing_rules)

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
    async def test_execute_dry_run(self, step, mock_api_client, pipeline_context_full, sample_calculation_result):
        """Test dry run mode skips API call."""
        pipeline_context_full.dry_run = True
        pipeline_context_full.calculation_results["TEST-001"] = sample_calculation_result

        await step.execute(pipeline_context_full)

        mock_api_client.update_prices.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_success(self, step, mock_api_client, pipeline_context_full, sample_calculation_result):
        """Test successful price submission."""
        pipeline_context_full.dry_run = False
        pipeline_context_full.calculation_results["TEST-001"] = sample_calculation_result
        mock_api_client.update_prices.return_value = {
            12345: {"updated": True, "errors": []},
        }

        await step.execute(pipeline_context_full)

        mock_api_client.update_prices.assert_called_once()
        call_args = mock_api_client.update_prices.call_args[0][0]
        assert len(call_args) == 1
        update = call_args[0]
        assert update["product_id"] == 12345
        assert update["offer_id"] == "67890"
        assert "price" in update
        assert "min_price" in update
        assert "old_price" in update

    @pytest.mark.asyncio
    async def test_execute_skips_no_product_id(self, step, mock_api_client, pipeline_context_with_products, sample_calculation_result):
        """Test skips products without product_id."""
        pipeline_context_with_products.dry_run = False
        pipeline_context_with_products.products[0].product_id = None
        pipeline_context_with_products.calculation_results["TEST-001"] = sample_calculation_result

        await step.execute(pipeline_context_with_products)

        mock_api_client.update_prices.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_skips_no_result(self, step, mock_api_client, pipeline_context_full):
        """Test skips products without calculation result."""
        pipeline_context_full.dry_run = False

        await step.execute(pipeline_context_full)

        mock_api_client.update_prices.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_api_error(self, step, mock_api_client, pipeline_context_full, sample_calculation_result):
        """Test handling of API errors."""
        pipeline_context_full.dry_run = False
        pipeline_context_full.calculation_results["TEST-001"] = sample_calculation_result
        mock_api_client.update_prices.return_value = {
            12345: {"updated": False, "errors": [{"message": "Price too low"}]},
        }

        await step.execute(pipeline_context_full)

        assert len(pipeline_context_full.errors) == 1
        assert "Price too low" in pipeline_context_full.errors[0]

    @pytest.mark.asyncio
    async def test_execute_exception_handling(self, step, mock_api_client, pipeline_context_full, sample_calculation_result):
        """Test exception handling during API call."""
        pipeline_context_full.dry_run = False
        pipeline_context_full.calculation_results["TEST-001"] = sample_calculation_result
        mock_api_client.update_prices.side_effect = Exception("API Error")

        await step.execute(pipeline_context_full)

        assert len(pipeline_context_full.errors) == 1
        assert "Failed to submit prices" in pipeline_context_full.errors[0]