"""
Tests for PersistToExcelStep.
"""
import pytest
from unittest.mock import MagicMock
from core.pipeline.steps.persist_excel import PersistToExcelStep
from core.pipeline.steps.base import PipelineContext
from core.entities import PriceCalculationResult
from core.domain.product import Product
from core.domain.value_objects import SKU, Money, Percentage, TimeInterval
from core.domain.pricing_rules import OzonPricingRules
from core.enums import StrategyType


class TestPersistToExcelStep:
    """Tests for PersistToExcelStep."""

    @pytest.fixture
    def step(self, mock_loader, pricing_rules):
        return PersistToExcelStep(loader=mock_loader, pricing_rules=pricing_rules)

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
            log_details={
                "strategy_type_name": "BELOW",
                "discount_coef": 1.0,
                "min_price_validated": 100.0,
            },
        )

    @pytest.mark.asyncio
    async def test_execute_success(self, step, mock_loader, pipeline_context_full, sample_calculation_result):
        """Test successful Excel persistence."""
        # Add calculation result
        pipeline_context_full.calculation_results["TEST-001"] = sample_calculation_result

        await step.execute(pipeline_context_full)

        mock_loader.update_product_in_file.assert_called_once()
        call_args = mock_loader.update_product_in_file.call_args
        assert call_args[0][0] == "TEST-001"
        updates = call_args[0][1]
        assert "current_price" in updates
        assert "min_price" in updates
        assert "margin" in updates
        assert "old_price" in updates

    @pytest.mark.asyncio
    async def test_execute_skips_no_result(self, step, mock_loader, pipeline_context_full):
        """Test skips products without calculation result."""
        # No calculation result added

        await step.execute(pipeline_context_full)

        mock_loader.update_product_in_file.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_update_failure(self, step, mock_loader, pipeline_context_full, sample_calculation_result):
        """Test handling of Excel update failure."""
        mock_loader.update_product_in_file.return_value = False
        pipeline_context_full.calculation_results["TEST-001"] = sample_calculation_result

        await step.execute(pipeline_context_full)

        assert len(pipeline_context_full.warnings) == 1
        assert "Failed to update Excel" in pipeline_context_full.warnings[0]

    @pytest.mark.asyncio
    async def test_execute_exception_handling(self, step, mock_loader, pipeline_context_full, sample_calculation_result):
        """Test exception handling during Excel update."""
        mock_loader.update_product_in_file.side_effect = Exception("Excel error")
        pipeline_context_full.calculation_results["TEST-001"] = sample_calculation_result

        await step.execute(pipeline_context_full)

        assert len(pipeline_context_full.errors) == 1
        assert "Excel update failed" in pipeline_context_full.errors[0]