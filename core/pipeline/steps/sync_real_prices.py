"""
Шаг 1: Синхронизация реальных цен покупателя с панели управления Ozon.
"""

from core.pipeline.steps.base import PipelineContext, PipelineStep
from core.protocols.repository import IProductRepository
from core.services.real_price_sync import RealPriceSyncService
from infrastructure.logger import logger


class SyncRealPricesStep(PipelineStep):
    """Шаг 1: Синхронизация реальных цен покупателя с панели управления Ozon."""

    def __init__(
        self,
        sync_service: RealPriceSyncService,
        product_repo: IProductRepository,
        dry_run: bool = False,
    ):
        self.sync_service = sync_service
        self.product_repo = product_repo
        self.dry_run = dry_run

    @property
    def name(self) -> str:
        return "SyncRealPrices"

    async def execute(self, context: PipelineContext) -> None:
        logger.info("Pipeline: Syncing real prices from Ozon price management page")

        try:
            # Запускаем синхронизацию
            stats = await self.sync_service.sync_real_prices_async(
                dry_run=context.dry_run,
                keep_file=context.dry_run,  # в dry-run не удаляем файл
            )

            # Обновляем товары в контексте реальными ценами
            for product in context.products:
                sku_str = str(product.sku)
                if sku_str in stats:
                    product.update_real_customer_price(stats[sku_str])

            logger.info(f"Pipeline: Synced real prices for {len(stats)} products")

        except Exception as e:
            context.add_error(f"Failed to sync real prices: {e}")
            context.should_stop = True
