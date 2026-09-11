"""
Шаг 3: Обогащение товаров product_id и offer_id из Ozon API.
"""

from core.pipeline.steps.base import PipelineContext, PipelineStep
from core.protocols.api import IApiClient
from infrastructure.logger import logger


class EnrichProductIdsStep(PipelineStep):
    """Шаг 3: Обогащение товаров product_id и offer_id из Ozon API."""

    def __init__(self, api_client: IApiClient):
        self.api_client = api_client

    @property
    def name(self) -> str:
        return "EnrichProductIds"

    async def execute(self, context: PipelineContext) -> None:
        logger.info("Pipeline: Enriching products with Ozon IDs")
        skus = [str(p.sku) for p in context.products]

        try:
            id_map = await self.api_client.get_product_ids_by_skus(skus)

            for product in context.products:
                sku_str = str(product.sku)
                if sku_str in id_map:
                    data = id_map[sku_str]
                    product.update_ozon_ids(
                        product_id=data["product_id"],
                        offer_id=data["offer_id"],
                        name=data.get("product_name"),
                    )
                else:
                    context.add_warning(f"Product {sku_str} not found in Ozon API response")

            logger.info(f"Pipeline: Enriched {len(id_map)} products with Ozon IDs")
        except Exception as e:
            context.add_error(f"Failed to enrich product IDs: {e}")
            context.should_stop = True
