"""
Tests for SendReportStep.
"""
import pytest
from unittest.mock import MagicMock
from core.pipeline.steps.send_report import SendReportStep
from core.pipeline.steps.base import PipelineContext
from core.entities import PriceCalculationResult
from core.domain.product import Product
from core.domain.value_objects import SKU, Money, Percentage, TimeInterval
from core.enums import StrategyType


class TestSendReportStep:
    """Tests for SendReportStep."""

    @pytest.fixture
    def step(self, mock_notifier):
        return SendReportStep(notifier=mock_notifier)

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
            },
        )

    @pytest.mark.asyncio
    async def test_execute_with_detailed_report(self, step, mock_notifier, pipeline_context_full, sample_calculation_result):
        """Test sending detailed report."""
        mock_notifier.send_detailed_report.return_value = None
        pipeline_context_full.calculation_results["TEST-001"] = sample_calculation_result

        await step.execute(pipeline_context_full)

        mock_notifier.send_detailed_report.assert_called_once()
        call_args = mock_notifier.send_detailed_report.call_args
        updates = call_args[0][0]
        errors = call_args[0][1]
        dry_run = call_args[1]["dry_run"]
        assert len(updates) == 1
        assert updates[0]["sku"] == "TEST-001"
        assert dry_run is True

    @pytest.mark.asyncio
    async def test_execute_fallback_notify(self, step, mock_notifier, pipeline_context_full, sample_calculation_result):
        """Test fallback to notify_cycle_complete when send_detailed_report not available."""
        # Remove send_detailed_report method
        del mock_notifier.send_detailed_report
        pipeline_context_full.calculation_results["TEST-001"] = sample_calculation_result

        await step.execute(pipeline_context_full)

        mock_notifier.notify_cycle_complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_dry_run(self, step, mock_notifier, pipeline_context_full, sample_calculation_result):
        """Test dry run mode marks all as updated."""
        pipeline_context_full.calculation_results["TEST-001"] = sample_calculation_result

        await step.execute(pipeline_context_full)

        call_args = mock_notifier.send_detailed_report.call_args
        updates = call_args[0][0]
        assert updates[0]["updated"] is True

    @pytest.mark.asyncio
    async def test_execute_error_handling(self, step, mock_notifier, pipeline_context_full, sample_calculation_result):
        """Test error handling when sending report fails."""
        mock_notifier.send_detailed_report.side_effect = Exception("Email error")
        pipeline_context_full.calculation_results["TEST-001"] = sample_calculation_result

        await step.execute(pipeline_context_full)

        assert len(pipeline_context_full.errors) == 1
        assert "Failed to send email report" in pipeline_context_full.errors[0]