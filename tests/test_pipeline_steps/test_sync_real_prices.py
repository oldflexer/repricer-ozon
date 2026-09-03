"""
Tests for SyncRealPricesStep.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from core.pipeline.steps.sync_real_prices import SyncRealPricesStep
from core.pipeline.steps.base import PipelineContext
from core.domain.product import Product
from core.domain.value_objects import SKU, Money
from core.enums import StrategyType


class TestSyncRealPricesStep:
    """Tests for SyncRealPricesStep."""

    @pytest.fixture
    def step(self, mock_sync_service, mock_product_repo):
        return SyncRealPricesStep(
            sync_service=mock_sync_service,
            product_repo=mock_product_repo,
            dry_run=False,
        )

    @pytest.mark.asyncio
    async def test_execute_success(self, step, mock_sync_service, pipeline_context_with_products):
        """Test successful sync of real prices."""
        # Setup
        mock_sync_service.sync_real_prices_async.return_value = {
            "TEST-001": Money.from_rubles(145.0),
        }
        pipeline_context_with_products.products[0].product_id = 12345

        # Execute
        await step.execute(pipeline_context_with_products)

        # Verify
        mock_sync_service.sync_real_prices_async.assert_called_once()
        assert pipeline_context_with_products.products[0].real_customer_price == Money.from_rubles(145.0)

    @pytest.mark.asyncio
    async def test_execute_dry_run(self, step, mock_sync_service, pipeline_context_with_products):
        """Test dry run mode keeps file."""
        step.dry_run = True
        pipeline_context_with_products.dry_run = True
        pipeline_context_with_products.products[0].product_id = 12345

        await step.execute(pipeline_context_with_products)

        mock_sync_service.sync_real_prices_async.assert_called_once_with(
            dry_run=True,
            keep_file=True,
        )

    @pytest.mark.asyncio
    async def test_execute_error_handling(self, step, mock_sync_service, pipeline_context_with_products):
        """Test error handling when sync fails."""
        mock_sync_service.sync_real_prices_async.side_effect = Exception("API Error")
        pipeline_context_with_products.products[0].product_id = 12345

        await step.execute(pipeline_context_with_products)

        assert len(pipeline_context_with_products.errors) == 1
        assert "Failed to sync real prices" in pipeline_context_with_products.errors[0]
        assert pipeline_context_with_products.should_stop is True

    @pytest.mark.asyncio
    async def test_execute_no_products(self, step, mock_sync_service, pipeline_context):
        """Test with empty products list."""
        await step.execute(pipeline_context)
        mock_sync_service.sync_real_prices_async.assert_called_once()