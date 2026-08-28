"""
Шаг 8: Сохранение истории цен и дневных агрегатов в БД.
"""

from core.domain.product import Product
from core.entities import ProductInfo, StrategyInterval
from core.pipeline.steps.base import PipelineContext, PipelineStep
from core.protocols.repository import (
    IAnalyticsRepository,
    IMarginalityRepository,
    IPriceHistoryRepository,
    IProductRepository,
)
from infrastructure.logger import logger


def _convert_product_to_product_info(product: "Product") -> ProductInfo:
    """Конвертирует доменный Product в ProductInfo entity для сохранения в БД."""
    return ProductInfo(
        sku=str(product.sku),
        product_id=product.product_id,
        offer_id=product.offer_id,
        product_name=product.product_name,
        cost_price=product.cost_price.rubles_float,
        min_price=product.min_price.rubles_float,
        current_price=product.current_price.rubles_float,
        old_price=product.old_price.rubles_float if product.old_price else None,
        real_customer_price=product.real_customer_price.rubles_float if product.real_customer_price else None,
        competitor_min_price=product.competitor_min_price.rubles_float if product.competitor_min_price else None,
    )


def _convert_pricing_strategies_to_intervals(strategies: list) -> list:
    """Конвертирует доменные PricingStrategy в StrategyInterval entities для БД."""

    intervals = []
    for s in strategies:
        intervals.append(
            StrategyInterval(
                start=f"{s.interval.start_hour:02d}:{s.interval.start_minute:02d}",
                end=f"{s.interval.end_hour:02d}:{s.interval.end_minute:02d}",
                strategy_type=s.strategy_type,
                percent=s.percent.percent_float,
            )
        )
    return intervals


class SaveHistoryStep(PipelineStep):
    """Шаг 8: Сохранение истории цен и дневных агрегатов в БД."""

    def __init__(
        self,
        product_repo: IProductRepository,
        history_repo: IPriceHistoryRepository,
        analytics_repo: IAnalyticsRepository,
        marginality_repo: IMarginalityRepository,
    ):
        self.product_repo = product_repo
        self.history_repo = history_repo
        self.analytics_repo = analytics_repo
        self.marginality_repo = marginality_repo

    @property
    def name(self) -> str:
        return "SaveHistory"

    async def execute(self, context: PipelineContext) -> None:
        logger.info("Pipeline: Saving products and price history")

        for product in context.products:
            result = context.calculation_results.get(str(product.sku))
            if not result:
                continue

            try:
                # Конвертируем доменный Product в ProductInfo для БД
                product_info = _convert_product_to_product_info(product)

                # Сохраняем/обновляем товар
                self.product_repo.upsert_product(product_info)

                # Сохраняем стратегии
                if product.strategies:
                    entity_intervals = _convert_pricing_strategies_to_intervals(product.strategies)
                    self.product_repo.set_strategies(str(product.sku), entity_intervals)

                # Сохраняем историю цен
                if product.product_id is not None:
                    pricing_data = context.pricing_data.get(product.product_id)
                    if pricing_data is not None:
                        self.history_repo.save_price_history(
                            sku=str(product.sku),
                            pricing=pricing_data,
                            result=result,
                        )

                # Сохраняем маржинальность
                self.marginality_repo.save_marginality(
                    sku=str(product.sku),
                    marginality=result.marginality,
                    marginality_week=0.0,  # TODO: получить из репозитория
                    marginality_month=0.0,  # TODO: получить из репозитория
                )

            except Exception as e:
                context.add_error(f"Failed to save history for {product.sku}: {e}")

        logger.info("Pipeline: History and aggregates saved")
