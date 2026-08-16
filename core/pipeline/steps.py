"""
Pipeline шаги для процесса репрайсинга (Pipeline Pattern).

Каждый шаг - изолированная единица работы, легко тестируемая и заменяемая.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import time
from typing import Any, Generic, TypeVar

from core.domain.product import PricingStrategy, Product
from core.domain.value_objects import SKU, Money
from core.entities import PriceCalculationResult, PricingData
from core.protocols.api import IApiClient
from core.protocols.loader import ILoader
from core.protocols.notifier import INotifier
from core.protocols.repository import (
    IAnalyticsRepository,
    IMaintenanceRepository,
    IMarginalityRepository,
    IPriceHistoryRepository,
    IProductRepository,
)
from core.services.price_calculation import PriceCalculationService
from infrastructure.logger import logger

T = TypeVar("T")


@dataclass
class PipelineContext:
    """Контекст выполнения pipeline - передает данные между шагами."""

    products: list[Product] = field(default_factory=list)
    pricing_data: dict[int, PricingData] = field(default_factory=dict)
    calculation_results: dict[str, PriceCalculationResult] = field(default_factory=dict)
    price_updates: list[dict[str, Any]] = field(default_factory=list)
    api_results: dict[int, dict] = field(default_factory=dict)
    updates_for_excel: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    dry_run: bool = False
    current_time: time | None = None
    should_stop: bool = False

    def add_error(self, message: str) -> None:
        self.errors.append(message)
        logger.error(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)
        logger.warning(message)


class PipelineStep(ABC, Generic[T]):
    """Базовый класс шага pipeline."""

    @abstractmethod
    async def execute(self, context: PipelineContext) -> None:
        """Выполняет шаг, изменяя контекст."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Название шага для логирования."""
        pass


class LoadProductsStep(PipelineStep):
    """Шаг 1: Загрузка товаров из Excel."""

    def __init__(self, loader: ILoader):
        self.loader = loader

    @property
    def name(self) -> str:
        return "LoadProducts"

    async def execute(self, context: PipelineContext) -> None:
        logger.info("Pipeline: Loading products from Excel")
        products_data, warnings = self.loader.load()

        for warning in warnings:
            context.add_warning(warning)

        if not products_data:
            context.add_warning("No products loaded from Excel")
            # Не останавливаем pipeline - пусть продолжает для отправки отчёта
            return

        # Конвертируем в доменные объекты
        for p in products_data:
            product = Product(
                sku=SKU(p.sku),
                product_id=p.product_id,
                offer_id=p.offer_id,
                product_name=p.product_name,
                cost_price=Money.from_rubles(p.cost_price),
                min_price=Money.from_rubles(p.min_price),
                current_price=Money.from_rubles(p.current_price)
                if p.current_price
                else Money.from_rubles(0),
                old_price=Money.from_rubles(p.old_price) if p.old_price else None,
                competitor_min_price=Money.from_rubles(p.competitor_min_price)
                if p.competitor_min_price
                else None,
            )

            # Загружаем стратегии из Excel
            intervals = self.loader.get_strategy_intervals(p)
            strategies = []
            for interval in intervals:
                # Конвертируем из StrategyInterval (core.entities) в TimeInterval (domain)
                from core.domain.value_objects import TimeInterval

                time_interval = TimeInterval.from_string(interval.start, interval.end)
                # percent в StrategyInterval - это float в процентах (10.0 = 10%)
                from core.domain.value_objects import Percentage

                percent = Percentage.from_percent(interval.percent)
                strategies.append(
                    PricingStrategy(
                        interval=time_interval,
                        strategy_type=interval.strategy_type,
                        percent=percent,
                    )
                )
            product.set_strategies(strategies)

            context.products.append(product)

        logger.info(f"Pipeline: Loaded {len(context.products)} products")


class EnrichProductIdsStep(PipelineStep):
    """Шаг 2: Обогащение товаров product_id и offer_id из Ozon API."""

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


class FetchPricingDataStep(PipelineStep):
    """Шаг 3: Получение цен, индексов и комиссий из Ozon API."""

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
            # Не останавливаем pipeline - пусть отправляется отчёт
            return

        try:
            pricing_list = await self.api_client.get_product_prices(product_ids)

            for pricing in pricing_list:
                context.pricing_data[pricing.product_id] = pricing

            logger.info(f"Pipeline: Fetched pricing data for {len(context.pricing_data)} products")
        except Exception as e:
            context.add_error(f"Failed to fetch pricing data: {e}")
            context.should_stop = True


class CalculatePricesStep(PipelineStep):
    """Шаг 4: Расчёт целевых цен и маржинальности."""

    def __init__(self, calculator: PriceCalculationService):
        self.calculator = calculator

    @property
    def name(self) -> str:
        return "CalculatePrices"

    async def execute(self, context: PipelineContext) -> None:
        logger.info("Pipeline: Calculating target prices")
        from core.domain.pricing_rules import get_pricing_rules

        rules = get_pricing_rules()

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
                from datetime import datetime

                from config.settings import TIMEZONE

                current_time = datetime.now(TIMEZONE).time()

            try:
                result = product.calculate_target_price(pricing, rules, current_time)
                context.calculation_results[str(product.sku)] = result
            except Exception as e:
                context.add_error(f"Calculation failed for {product.sku}: {e}")

        logger.info(f"Pipeline: Calculated prices for {len(context.calculation_results)} products")


class PersistToExcelStep(PipelineStep):
    """Шаг 5: Сохранение результатов в Excel."""

    def __init__(self, loader: ILoader):
        self.loader = loader

    @property
    def name(self) -> str:
        return "PersistToExcel"

    async def execute(self, context: PipelineContext) -> None:
        logger.info("Pipeline: Persisting results to Excel")
        from core.domain.pricing_rules import get_pricing_rules

        rules = get_pricing_rules()

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
                    rules.calculate_old_price(
                        Money.from_rubles(result.result_target_price), product.old_price
                    ).rubles_float
                )
            )

            updates = {
                "current_price": real_price,
                "min_price": int(
                    round(product.min_price.rubles_float / product.discount_coefficient.value_float)
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


class SubmitPricesToOzonStep(PipelineStep):
    """Шаг 6: Отправка новых цен в Ozon API."""

    def __init__(self, api_client: IApiClient):
        self.api_client = api_client

    @property
    def name(self) -> str:
        return "SubmitPricesToOzon"

    async def execute(self, context: PipelineContext) -> None:
        if context.dry_run:
            logger.info("Pipeline: Dry run - skipping Ozon price submission")
            return

        logger.info("Pipeline: Submitting prices to Ozon API")
        from core.domain.pricing_rules import get_pricing_rules

        rules = get_pricing_rules()

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
            min_price_for_api = rules.validate_min_price(
                target_price,
                Money.from_rubles(
                    product.min_price.rubles_float / product.discount_coefficient.value_float
                ),
            )

            old_price = rules.calculate_old_price(target_price, product.old_price)

            price_updates.append(
                {
                    "product_id": product.product_id,
                    "offer_id": product.offer_id or "",
                    "price": int(round(target_price.rubles_float)),
                    "min_price": int(round(min_price_for_api.rubles_float)),
                    "net_price": int(round(product.cost_price.rubles_float)),
                    "old_price": int(round(old_price.rubles_float)),
                    "manage_elastic_boosting_through_price": rules.manage_elastic_boosting,
                }
            )

        if not price_updates:
            context.add_warning("No price updates to submit")
            return

        try:
            api_results = await self.api_client.update_prices(price_updates)
            context.api_results = api_results

            # Подсчет успешных обновлений
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


class SaveHistoryStep(PipelineStep):
    """Шаг 7: Сохранение истории цен и дневных агрегатов в БД."""

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

            pricing = context.pricing_data.get(product.product_id) if product.product_id else None
            if not pricing:
                continue

            # Вычисляем real_price для истории
            discount_coef = result.log_details.get("discount_coef", 1.0)
            real_price = round(result.result_target_price * discount_coef)

            # Всегда сохраняем/обновляем товар в БД (даже в dry_run)
            try:
                from core.entities import ProductInfo

                product_info = ProductInfo(
                    sku=str(product.sku),
                    product_id=product.product_id,
                    offer_id=product.offer_id,
                    product_name=product.product_name,
                    min_price=product.min_price.rubles_float,
                    cost_price=product.cost_price.rubles_float,
                )
                self.product_repo.upsert_product(product_info)
            except Exception as e:
                context.add_error(f"Failed to save product for {product.sku}: {e}")

            # Сохраняем историю цен (даже в dry_run, так как тесты ожидают этого)
            try:
                self.history_repo.save_price_history(
                    sku=str(product.sku), pricing=pricing, result=result, real_price=real_price
                )
                self.analytics_repo.save_daily_aggregates(
                    sku=str(product.sku), result=result, real_price=real_price
                )
            except Exception as e:
                context.add_error(f"Failed to save history for {product.sku}: {e}")

        # Сохраняем маржинальность
        for product in context.products:
            result = context.calculation_results.get(str(product.sku))
            if not result:
                continue

            try:
                # TODO: получать средние из репозитория
                marginality_week = 0.0
                marginality_month = 0.0

                self.marginality_repo.save_marginality(
                    sku=str(product.sku),
                    marginality=result.marginality,
                    marginality_week=marginality_week,
                    marginality_month=marginality_month,
                )
            except Exception as e:
                context.add_error(f"Failed to save marginality for {product.sku}: {e}")

        logger.info("Pipeline: History and aggregates saved")


class SendReportStep(PipelineStep):
    """Шаг 8: Отправка email отчёта."""

    def __init__(self, notifier: INotifier):
        self.notifier = notifier

    @property
    def name(self) -> str:
        return "SendReport"

    async def execute(self, context: PipelineContext) -> None:
        logger.info("Pipeline: Sending email report")

        # Формируем данные для отчёта
        updates = []
        errors = []

        for product in context.products:
            result = context.calculation_results.get(str(product.sku))
            if not result:
                continue

            api_result = (
                context.api_results.get(product.product_id, {}) if product.product_id else {}
            )
            updated = api_result.get("updated", False) if not context.dry_run else True

            updates.append(
                {
                    "sku": str(product.sku),
                    "name": product.product_name or "",
                    "old_price": product.current_price.rubles_float if product.current_price else 0,
                    "new_price": int(
                        round(
                            result.result_target_price
                            * result.log_details.get("discount_coef", 1.0)
                        )
                    ),
                    "min_price": int(
                        round(
                            product.min_price.rubles_float
                            / product.discount_coefficient.value_float
                        )
                    ),
                    "marginality": result.marginality,
                    "updated": updated,
                    "strategy": result.log_details.get("strategy_type_name", "Unknown"),
                    "discount_coef": result.log_details.get("discount_coef", 0),
                }
            )

            if not updated and not context.dry_run:
                for err in api_result.get("errors", []):
                    errors.append(f"{product.sku}: {err.get('message', 'Unknown error')}")

        try:
            if hasattr(self.notifier, "send_detailed_report"):
                self.notifier.send_detailed_report(updates, errors, dry_run=context.dry_run)
            else:
                self.notifier.notify_cycle_complete(updates, errors, dry_run=context.dry_run)
            logger.info("Pipeline: Email report sent")
        except Exception as e:
            context.add_error(f"Failed to send email report: {e}")


class CleanupDatabaseStep(PipelineStep):
    """Шаг 9: Очистка старых записей в БД (auto cleanup)."""

    def __init__(self, maintenance_repo: IMaintenanceRepository):
        self.maintenance_repo = maintenance_repo

    @property
    def name(self) -> str:
        return "CleanupDatabase"

    async def execute(self, context: PipelineContext) -> None:
        logger.info("Pipeline: Running database cleanup")
        try:
            deleted = self.maintenance_repo.auto_cleanup_if_needed()
            if deleted > 0:
                logger.info(f"Pipeline: Cleaned up {deleted} old records")
        except Exception as e:
            context.add_warning(f"Database cleanup failed: {e}")
