"""
Шаг 1: Парсинг своих товаров для получения real_customer_price и discount_coef.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.pipeline.steps.base import PipelineContext, PipelineStep
from infrastructure.logger import logger

if TYPE_CHECKING:
    from core.use_cases.parse_own_products import ParseOwnProductsUseCase


class ParseOwnProductsStep(PipelineStep):
    """Шаг 1: Парсинг своих товаров для получения real_customer_price и discount_coef."""

    def __init__(
        self,
        parse_use_case: "ParseOwnProductsUseCase",  # Forward reference to avoid circular import
        dry_run: bool = False,
    ):
        self.parse_use_case = parse_use_case
        self.dry_run = dry_run

    @property
    def name(self) -> str:
        return "ParseOwnProducts"

    async def execute(self, context: PipelineContext) -> None:
        logger.info("Pipeline: Parsing own products for real_customer_price and discount_coef")

        try:
            stats = await self.parse_use_case.execute(dry_run=self.dry_run)

            logger.info(
                f"Pipeline: Parsed own products: updated={stats.get('updated', 0)}, "
                f"errors={stats.get('errors', 0)}, skipped={stats.get('skipped', 0)}"
            )

            if stats.get("errors", 0) > 0:
                context.add_warning(f"Own products parsing had {stats['errors']} errors")

        except Exception as e:
            context.add_error(f"Failed to parse own products: {e}")
            context.should_stop = True