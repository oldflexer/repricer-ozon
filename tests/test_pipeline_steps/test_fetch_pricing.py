"""
Tests for FetchPricingDataStep.
"""
import pytest
from unittest.mock import AsyncMock
from core.pipeline.steps.fetch_pricing import FetchPricingDataStep
from core.pipeline.steps.base import PipelineContext
from core.entities import PricingData
from core.domain.product import Product
from core.domain.value_objects import SKU, Money


class TestFetchPricingDataStep:
    """Tests for FetchPricingDataStep."""

    @pytest.fixture
    def step(self, mock_api_client):
        return FetchPricingDataStep(api_client=mock_api_client)

    @pytest.fixture
    def sample_pricing_data(self) -> PricingData:
        """Sample PricingData entity with correct fields."""
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

    @pytest.mark.asyncio
    async def test_execute_success(self, step, mock_api_client, pipeline_context_with_products, sample_pricing_data):
        """Test successful pricing data fetch."""
        mock_api_client.get_product_prices.return_value = [sample_pricing_data]
        pipeline_context_with_products.products[0].product_id = 12345

        await step.execute(pipeline_context_with_products)

        assert 12345 in pipeline_context_with_products.pricing_data
        assert pipeline_context_with_products.pricing_data[12345] == sample_pricing_data
        mock_api_client.get_product_prices.assert_called_once_with([12345])

    @pytest.mark.asyncio
    async def test_execute_no_product_ids(self, step, mock_api_client, pipeline_context_with_products):
        """Test when products have no product_id."""
        pipeline_context_with_products.products[0].product_id = None

        await step.execute(pipeline_context_with_products)

        assert len(pipeline_context_with_products.warnings) == 1
        assert "No product IDs available" in pipeline_context_with_products.warnings[0]
        mock_api_client.get_product_prices.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_multiple_products(self, step, mock_api_client, pipeline_context, sample_pricing_data):
        """Test with multiple products."""
        from core.domain.product import Product
        from core.domain.value_objects import SKU, Money

        product1 = Product(
            sku=SKU("TEST-001"),
            product_id=12345,
            offer_id="67890",
            product_name="Test 1",
            cost_price=Money.from_rubles(100.0),
            min_price=Money.from_rubles(120.0),
            current_price=Money.from_rubles(150.0),
        )
        product2 = Product(
            sku=SKU("TEST-002"),
            product_id=54321,
            offer_id="98765",
            product_name="Test 2",
            cost_price=Money.from_rubles(200.0),
            min_price=Money.from_rubles(220.0),
            current_price=Money.from_rubles(250.0),
        )
        pipeline_context.products = [product1, product2]

        pricing_data2 = PricingData(
            product_id=54321,
            price=250.0,
            old_price=240.0,
            min_price=220.0,
            net_price=200.0,
            marketing_seller_price=245.0,
            acquiring=3.0,
            sales_percent_fbs=20.0,
            sales_percent_fbo=22.0,
            fbs_deliv_to_customer_amount=25.0,
            fbo_deliv_to_customer_amount=30.0,
        )
        mock_api_client.get_product_prices.return_value = [sample_pricing_data, pricing_data2]

        await step.execute(pipeline_context)

        assert 12345 in pipeline_context.pricing_data
        assert 54321 in pipeline_context.pricing_data
        mock_api_client.get_product_prices.assert_called_once_with([12345, 54321])

    @pytest.mark.asyncio
    async def test_execute_error_handling(self, step, mock_api_client, pipeline_context_with_products):
        """Test error handling when API call fails."""
        mock_api_client.get_product_prices.side_effect = Exception("API Error")
        pipeline_context_with_products.products[0].product_id = 12345

        await step.execute(pipeline_context_with_products)

        assert len(pipeline_context_with_products.errors) == 1
        assert "Failed to fetch pricing data" in pipeline_context_with_products.errors[0]
        assert pipeline_context_with_products.should_stop is True