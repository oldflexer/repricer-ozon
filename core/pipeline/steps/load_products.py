"""
Шаг 2: Загрузка товаров из Excel и БД.
"""

from core.domain.product import PricingStrategy, Product
from core.domain.value_objects import Money, Percentage, TimeInterval, SKU
from core.entities import ProductInfo, StrategyInterval
from core.pipeline.steps.base import PipelineContext, PipelineStep
from core.protocols.loader import ILoader
from core.protocols.repository import IProductRepository
from infrastructure.logger import logger


def _convert_product_info_to_product(info: ProductInfo, strategies: list[StrategyInterval] | None = None) -> Product:
    """Конвертирует ProductInfo (entity) в Product (domain)."""
    domain_strategies = []
    if strategies:
        for interval in strategies:
            domain_strategies.append(
                PricingStrategy(
                    interval=TimeInterval(
                        start_hour=interval.start_time.hour,
                        start_minute=interval.start_time.minute,
                        end_hour=interval.end_time.hour,
                        end_minute=interval.end_time.minute,
                    ),
                    strategy_type=interval.strategy_type,
                    percent=Percentage.from_ratio(interval.percent / 100.0),
                )
            )

    return Product(
        sku=SKU(info.sku),
        product_id=info.product_id,
        offer_id=info.offer_id,
        product_name=info.product_name,
        cost_price=Money.from_rubles(info.cost_price),
        min_price=Money.from_rubles(info.min_price),
        current_price=Money.from_rubles(info.current_price),
        old_price=Money.from_rubles(info.old_price) if info.old_price else None,
        competitor_min_price=Money.from_rubles(info.competitor_min_price) if info.competitor_min_price else None,
        real_customer_price=Money.from_rubles(info.real_customer_price) if info.real_customer_price else None,
        strategies=domain_strategies,
    )


class LoadProductsStep(PipelineStep):
    """Шаг 2: Загрузка товаров из Excel и обогащение из БД."""

    def __init__(self, loader: ILoader, product_repo: IProductRepository):
        self.loader = loader
        self.product_repo = product_repo

    @property
    def name(self) -> str:
        return "LoadProducts"

    async def execute(self, context: PipelineContext) -> None:
        logger.info("Pipeline: Loading products from Excel")

        try:
            product_infos, warnings = self.loader.load()

            # Получаем стратегии из загрузчика (если он их сохраняет)
            loader_strategies = getattr(self.loader, '_strategies', {})

            context.products = [
                _convert_product_info_to_product(p, loader_strategies.get(p.sku))
                for p in product_infos
            ]

            for warning in warnings:
                context.add_warning(warning)

            # Обогащаем из БД (стратегии, исторические данные)
            for product in context.products:
                entity_strategies = self.product_repo.get_strategies(str(product.sku))
                if entity_strategies:
                    domain_strategies = [
                        PricingStrategy(
                            interval=TimeInterval(
                                start_hour=s.start_time.hour,
                                start_minute=s.start_time.minute,
                                end_hour=s.end_time.hour,
                                end_minute=s.end_time.minute,
                            ),
                            strategy_type=s.strategy_type,
                            percent=Percentage.from_ratio(s.percent / 100.0),
                        )
                        for s in entity_strategies
                    ]
                    product.set_strategies(domain_strategies)

            logger.info(f"Pipeline: Loaded {len(context.products)} products")

        except Exception as e:
            context.add_error(f"Failed to load products: {e}")
            context.should_stop = True
