"""
Шаг 5: Расчёт целевых цен и маржинальности.
"""

from datetime import datetime

from config.settings import TIMEZONE
from core.domain.pricing_rules import OzonPricingRules
from core.entities import StrategyInterval
from core.pipeline.steps.base import PipelineContext, PipelineStep
from core.services.price_calculation import PriceCalculationService
from infrastructure.logger import logger


class CalculatePricesStep(PipelineStep):
    """Шаг 5: Расчёт целевых цен и маржинальности."""

    def __init__(self, calculator: PriceCalculationService, pricing_rules: OzonPricingRules):
        self.calculator = calculator
        self.pricing_rules = pricing_rules

    @property
    def name(self) -> str:
        return "CalculatePrices"

    async def execute(self, context: PipelineContext) -> None:
        logger.info("Pipeline: Calculating target prices")

        for product in context.products:
            if product.product_id is None:
                context.add_warning(
                    f"Product {product.sku} has no product_id, skipping calculation"
                )
                continue

            pricing = context.pricing_data.get(product.product_id)
            if not pricing:
                context.add_warning(f"No pricing data for product {product.sku}, skipping")
                continue

            # Определяем текущее время для стратегии
            current_time = context.current_time
            if current_time is None:
                current_time = datetime.now(TIMEZONE).time()

            try:
                # Convert domain strategies to StrategyInterval entities
                intervals = [
                    StrategyInterval(
                        start=f"{s.interval.start_hour:02d}:{s.interval.start_minute:02d}",
                        end=f"{s.interval.end_hour:02d}:{s.interval.end_minute:02d}",
                        strategy_type=s.strategy_type,
                        percent=s.percent.percent_float,
                    )
                    for s in product.strategies
                ]

                result = self.calculator.calculate(
                    sku=str(product.sku),
                    pricing=pricing,
                    rip=product.min_price.rubles_float,
                    intervals=intervals,
                    competitor_min_price=product.competitor_min_price.rubles_float
                    if product.competitor_min_price
                    else None,
                    real_customer_price=product.real_customer_price.rubles_float
                    if product.real_customer_price
                    else None,
                )
                context.calculation_results[str(product.sku)] = result
            except Exception as e:
                context.add_error(f"Calculation failed for {product.sku}: {e}")

        logger.info(f"Pipeline: Calculated prices for {len(context.calculation_results)} products")
