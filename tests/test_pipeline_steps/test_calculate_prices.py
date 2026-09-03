"""
Tests for CalculatePricesStep.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import time
from core.pipeline.steps.calculate_prices import CalculatePricesStep
from core.pipeline.steps.base import PipelineContext
from core.entities import PricingData, PriceCalculationResult, StrategyInterval
from core.domain.product import Product
from core.domain.value_objects import SKU, Money, Percentage, TimeInterval
from core.domain.pricing_rules import OzonPricingRules
from core.services.price_calculation import PriceCalculationService
from core.enums import StrategyType


class TestCalculatePricesStep:
    """Tests for CalculatePricesStep."""

    @pytest.fixture
    def step(self, mock_calculator, pricing_rules):
        return CalculatePricesStep(calculator=mock_calculator, pricing_rules=pricing_rules)

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
    async def test_execute_success(self, step, mock_calculator, pipeline_context_full, sample_calculation_result):
        """Test successful price calculation."""
        mock_calculator.calculate.return_value = sample_calculation_result
        await step.execute(pipeline_context_full)

        assert "TEST-001" in pipeline_context_full.calculation_results
        result = pipeline_context_full.calculation_results["TEST-001"]
        assert isinstance(result, PriceCalculationResult)
        assert result.result_target_price == 150.0
        assert result.marginality == 25.0
        mock_calculator.calculate.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_skips_no_product_id(self, step, mock_calculator, pipeline_context_with_products):
        """Test skips products without product_id."""
        pipeline_context_with_products.products[0].product_id = None

        await step.execute(pipeline_context_with_products)

        assert len(pipeline_context_with_products.warnings) == 1
        assert "no product_id" in pipeline_context_with_products.warnings[0]
        mock_calculator.calculate.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_skips_no_pricing_data(self, step, mock_calculator, pipeline_context_with_products):
        """Test skips products without pricing data."""
        pipeline_context_with_products.products[0].product_id = 12345
        # No pricing data in context

        await step.execute(pipeline_context_with_products)

        assert len(pipeline_context_with_products.warnings) == 1
        assert "No pricing data" in pipeline_context_with_products.warnings[0]
        mock_calculator.calculate.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_error_handling(self, step, mock_calculator, pipeline_context_full):
        """Test error handling when calculation fails."""
        mock_calculator.calculate.side_effect = Exception("Calculation error")

        await step.execute(pipeline_context_full)

        assert len(pipeline_context_full.errors) == 1
        assert "Calculation failed" in pipeline_context_full.errors[0]

    @pytest.mark.asyncio
    async def test_execute_multiple_products(self, step, mock_calculator, pipeline_context, sample_pricing_data, sample_calculation_result):
        """Test with multiple products."""
        from core.domain.product import Product, PricingStrategy
        from core.domain.value_objects import SKU, Money

        product1 = Product(
            sku=SKU("TEST-001"),
            product_id=12345,
            offer_id="67890",
            product_name="Test 1",
            cost_price=Money.from_rubles(100.0),
            min_price=Money.from_rubles(120.0),
            current_price=Money.from_rubles(150.0),
            strategies=[
                PricingStrategy(
                    interval=TimeInterval(start_hour=9, start_minute=0, end_hour=18, end_minute=0),
                    strategy_type=StrategyType.BELOW,
                    percent=Percentage.from_ratio(0.05),
                )
            ],
        )
        product2 = Product(
            sku=SKU("TEST-002"),
            product_id=54321,
            offer_id="98765",
            product_name="Test 2",
            cost_price=Money.from_rubles(200.0),
            min_price=Money.from_rubles(220.0),
            current_price=Money.from_rubles(250.0),
            strategies=[
                PricingStrategy(
                    interval=TimeInterval(start_hour=9, start_minute=0, end_hour=18, end_minute=0),
                    strategy_type=StrategyType.ABOVE,
                    percent=Percentage.from_ratio(0.03),
                )
            ],
        )
        pipeline_context.products = [product1, product2]
        pipeline_context.pricing_data = {12345: sample_pricing_data}

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
        pipeline_context.pricing_data[54321] = pricing_data2

        mock_calculator.calculate.return_value = sample_calculation_result

        await step.execute(pipeline_context)

        assert "TEST-001" in pipeline_context.calculation_results
        assert "TEST-002" in pipeline_context.calculation_results
        assert mock_calculator.calculate.call_count == 2