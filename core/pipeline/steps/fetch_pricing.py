"""
Шаг 4: Получение цен, индексов и комиссий из Ozon API.
"""

from core.pipeline.steps.base import PipelineContext, PipelineStep
from core.protocols.api import IApiClient
from infrastructure.logger import logger


class FetchPricingDataStep(PipelineStep):
    """Шаг 4: Получение цен, индексов и комиссий из Ozon API."""

    def __init__(self, api_client: IApiClient):
        self.api_client = api_client

    @property
    def name(self) -> str:
        return "FetchPricingData"

    async def execute(self, context: PipelineContext) -> None:
        logger.info("Pipeline: Fetching pricing data from Ozon API")
        product_ids = [p.product_id for p in context.products if p.product_id is not None]

        if not product_ids:
            context.add_warning("No product IDs available for pricing data fetch")
            return

        try:
            pricing_list = await self.api_client.get_product_prices(product_ids)

            for pricing in pricing_list:
                context.pricing_data[pricing.product_id] = pricing

            logger.info(f"Pipeline: Fetched pricing data for {len(context.pricing_data)} products")
        except Exception as e:
            context.add_error(f"Failed to fetch pricing data: {e}")
            context.should_stop = True
