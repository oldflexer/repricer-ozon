"""
Шаг 7: Отправка новых цен в Ozon API.
"""

from core.domain.pricing_rules import OzonPricingRules
from core.domain.value_objects import Money
from core.pipeline.steps.base import PipelineContext, PipelineStep
from core.protocols.api import IApiClient
from infrastructure.logger import logger


class SubmitPricesToOzonStep(PipelineStep):
    """Шаг 7: Отправка новых цен в Ozon API."""

    def __init__(self, api_client: IApiClient, pricing_rules: OzonPricingRules):
        self.api_client = api_client
        self.pricing_rules = pricing_rules

    @property
    def name(self) -> str:
        return "SubmitPricesToOzon"

    async def execute(self, context: PipelineContext) -> None:
        if context.dry_run:
            logger.info("Pipeline: Dry run - skipping Ozon price submission")
            return

        logger.info("Pipeline: Submitting prices to Ozon API")

        # Формируем payload для API
        price_updates = []
        for product in context.products:
            if product.product_id is None:
                continue

            result = context.calculation_results.get(str(product.sku))
            if not result:
                continue

            # Валидация min_price по правилам Ozon
            target_price = Money.from_rubles(result.result_target_price)
            min_price_for_api = self.pricing_rules.validate_min_price(
                target_price,
                Money.from_rubles(
                    product.min_price.rubles_float / result.log_details.get("discount_coef", 1.0)
                ),
            )

            old_price = self.pricing_rules.calculate_old_price(target_price, product.old_price)

            price_updates.append(
                {
                    "product_id": product.product_id,
                    "offer_id": product.offer_id or "",
                    "price": str(int(round(target_price.rubles_float))),
                    "min_price": str(int(round(min_price_for_api.rubles_float))),
                    "net_price": str(int(round(product.cost_price.rubles_float))),
                    "old_price": str(int(round(old_price.rubles_float))),
                    "manage_elastic_boosting_through_price": self.pricing_rules.manage_elastic_boosting,
                }
            )

        if not price_updates:
            context.add_warning("No price updates to submit")
            return

        try:
            api_results = await self.api_client.update_prices(price_updates)
            context.api_results = api_results

            # Подсчёт успешных обновлений
            success_count = sum(1 for r in api_results.values() if r.get("updated", False))
            logger.info(
                f"Pipeline: Successfully updated {success_count}/{len(price_updates)} prices in Ozon"
            )

            # Логирование ошибок
            for product in context.products:
                if product.product_id and product.product_id in api_results:
                    res = api_results[product.product_id]
                    if not res.get("updated", False):
                        errors = res.get("errors", [])
                        for err in errors:
                            context.add_error(
                                f"Ozon API error for {product.sku}: {err.get('message', 'Unknown')}"
                            )

        except Exception as e:
            context.add_error(f"Failed to submit prices to Ozon: {e}")
