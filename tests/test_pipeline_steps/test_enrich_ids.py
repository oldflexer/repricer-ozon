"""
Tests for EnrichProductIdsStep.
"""
import pytest
from unittest.mock import AsyncMock
from core.pipeline.steps.enrich_ids import EnrichProductIdsStep
from core.pipeline.steps.base import PipelineContext
from core.domain.product import Product
from core.domain.value_objects import SKU, Money


class TestEnrichProductIdsStep:
    """Tests for EnrichProductIdsStep."""

    @pytest.fixture
    def step(self, mock_api_client):
        return EnrichProductIdsStep(api_client=mock_api_client)

    @pytest.mark.asyncio
    async def test_execute_success(self, step, mock_api_client, pipeline_context_with_products):
        """Test successful enrichment with Ozon IDs."""
        mock_api_client.get_product_ids_by_skus.return_value = {
            "TEST-001": {"product_id": 12345, "offer_id": 67890, "product_name": "Updated Name"},
        }

        await step.execute(pipeline_context_with_products)

        product = pipeline_context_with_products.products[0]
        assert product.product_id == 12345
        assert product.offer_id == 67890
        assert product.product_name == "Updated Name"
        mock_api_client.get_product_ids_by_skus.assert_called_once_with(["TEST-001"])

    @pytest.mark.asyncio
    async def test_execute_partial_match(self, step, mock_api_client, pipeline_context_with_products):
        """Test when some SKUs not found in API response."""
        mock_api_client.get_product_ids_by_skus.return_value = {
            "TEST-001": {"product_id": 12345, "offer_id": 67890},
        }
        # Add a second product that won't be found
        from core.domain.product import Product
        from core.domain.value_objects import SKU, Money
        product2 = Product(
            sku=SKU("TEST-002"),
            product_id=None,
            offer_id=None,
            product_name="Test 2",
            cost_price=Money.from_rubles(100.0),
            min_price=Money.from_rubles(120.0),
            current_price=Money.from_rubles(150.0),
        )
        pipeline_context_with_products.products.append(product2)

        await step.execute(pipeline_context_with_products)

        assert pipeline_context_with_products.products[0].product_id == 12345
        assert pipeline_context_with_products.products[1].product_id is None
        assert len(pipeline_context_with_products.warnings) == 1
        assert "not found in Ozon API response" in pipeline_context_with_products.warnings[0]

    @pytest.mark.asyncio
    async def test_execute_error_handling(self, step, mock_api_client, pipeline_context_with_products):
        """Test error handling when API call fails."""
        mock_api_client.get_product_ids_by_skus.side_effect = Exception("API Error")

        await step.execute(pipeline_context_with_products)

        assert len(pipeline_context_with_products.errors) == 1
        assert "Failed to enrich product IDs" in pipeline_context_with_products.errors[0]
        assert pipeline_context_with_products.should_stop is True

    @pytest.mark.asyncio
    async def test_execute_empty_products(self, step, mock_api_client, pipeline_context):
        """Test with empty products list."""
        await step.execute(pipeline_context)
        mock_api_client.get_product_ids_by_skus.assert_called_once_with([])