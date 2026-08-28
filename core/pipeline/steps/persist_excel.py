"""
Шаг 6: Сохранение результатов в Excel.
"""

from core.domain.pricing_rules import OzonPricingRules
from core.domain.value_objects import Money
from core.pipeline.steps.base import PipelineContext, PipelineStep
from core.protocols.loader import ILoader
from infrastructure.logger import logger


class PersistToExcelStep(PipelineStep):
    """Шаг 6: Сохранение результатов в Excel."""

    def __init__(self, loader: ILoader, pricing_rules: OzonPricingRules):
        self.loader = loader
        self.pricing_rules = pricing_rules

    @property
    def name(self) -> str:
        return "PersistToExcel"

    async def execute(self, context: PipelineContext) -> None:
        logger.info("Pipeline: Persisting results to Excel")

        for product in context.products:
            result = context.calculation_results.get(str(product.sku))
            if not result:
                continue

            # Подготовка данных для Excel
            real_price = int(
                round(result.result_target_price * result.log_details.get("discount_coef", 1.0))
            )
            marginality_week = 0.0  # TODO: получить из репозитория
            marginality_month = 0.0  # TODO: получить из репозитория
            old_price_excel = int(
                round(
                    self.pricing_rules.calculate_old_price(
                        Money.from_rubles(result.result_target_price), product.old_price
                    ).rubles_float
                )
            )

            updates = {
                "current_price": real_price,
                "min_price": int(
                    round(product.min_price.rubles_float / result.log_details.get("discount_coef", 1.0))
                ),
                "margin": result.marginality,
                "margin_week": marginality_week,
                "margin_month": marginality_month,
                "old_price": old_price_excel,
            }

            try:
                success = self.loader.update_product_in_file(str(product.sku), updates)
                if not success:
                    context.add_warning(f"Failed to update Excel for {product.sku}")
            except Exception as e:
                context.add_error(f"Excel update failed for {product.sku}: {e}")

        logger.info("Pipeline: Excel persistence completed")
