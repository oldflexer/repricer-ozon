"""
Pipeline Orchestrator - управляет выполнением последовательности шагов.
"""

from collections.abc import Callable
from dataclasses import dataclass
import time

from core.domain.pricing_rules import OzonPricingRules
from core.metrics import (
    record_cycle_duration,
    record_products_loaded,
    record_prices_updated,
    record_error,
    record_marginality,
)
from core.pipeline.steps import (
    CalculatePricesStep,
    CleanupDatabaseStep,
    EnrichProductIdsStep,
    FetchPricingDataStep,
    LoadProductsStep,
    PersistToExcelStep,
    PipelineContext,
    PipelineStep,
    SaveHistoryStep,
    SendReportStep,
    SubmitPricesToOzonStep,
    SyncRealPricesStep,
)
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
from core.services.real_price_sync import RealPriceSyncService
from infrastructure.logger import logger, set_request_id, clear_request_id
import uuid


@dataclass
class PipelineResult:
    """Результат выполнения pipeline."""

    products_loaded: int
    prices_updated: int
    errors: list[str]
    warnings: list[str]


class PipelineOrchestrator:
    """
    Оркестратор pipeline репрайсинга.

    Выполняет последовательность шагов, передавая контекст между ними.
    Поддерживает остановку при критических ошибках.
    """

    def __init__(self, steps: list[PipelineStep]):
        self.steps = steps

    async def execute(self, context: PipelineContext) -> PipelineResult:
        """
        Запускает pipeline.

        Args:
            context: Начальный контекст (с dry_run флагом)

        Returns:
            PipelineResult со статистикой выполнения
        """
        start_time = time.time()
        
        # Generate and set request_id for correlation
        request_id = context.request_id or str(uuid.uuid4())[:8]
        context.request_id = request_id
        set_request_id(request_id)

        logger.info("Starting pipeline", steps=len(self.steps), request_id=request_id)

        try:
            for i, step in enumerate(self.steps, start=1):
                if context.should_stop:
                    logger.warning("Pipeline stopped before step", step=step.name, request_id=request_id)
                    break

                context.report_progress(i, f"Executing: {step.name}")
                logger.info("Executing pipeline step", step=step.name, request_id=request_id)
                try:
                    await step.execute(context)
                except Exception as e:
                    logger.exception("Pipeline step failed with exception", step=step.name, request_id=request_id)
                    context.add_error(f"Step {step.name} failed: {e}")
                    record_error(type(e).__name__, step.name)
                    context.should_stop = True
        finally:
            clear_request_id()
            # Record metrics
            duration = time.time() - start_time
            record_cycle_duration(duration)
            record_products_loaded(len(context.products))
            
            prices_updated = 0
            if context.dry_run:
                prices_updated = len(context.calculation_results)
                record_prices_updated("dry_run", prices_updated)
            elif context.api_results:
                prices_updated = sum(1 for r in context.api_results.values() if r.get("updated", False))
                record_prices_updated("success", prices_updated)
                failed = sum(1 for r in context.api_results.values() if not r.get("updated", False))
                if failed:
                    record_prices_updated("failed", failed)
            
            # Record marginality for each product
            for product in context.products:
                result = context.calculation_results.get(str(product.sku))
                if result:
                    record_marginality(str(product.sku), result.marginality)

        # Подсчет статистики
        prices_updated = 0
        if context.dry_run:
            # В dry_run считаем успешными все расчётные результаты
            prices_updated = len(context.calculation_results)
        elif context.api_results:
            prices_updated = sum(1 for r in context.api_results.values() if r.get("updated", False))

        pipeline_result = PipelineResult(
            products_loaded=len(context.products),
            prices_updated=prices_updated,
            errors=context.errors,
            warnings=context.warnings,
        )

        logger.info(
            f"Pipeline completed: loaded={pipeline_result.products_loaded}, "
            f"updated={pipeline_result.prices_updated}, errors={len(pipeline_result.errors)}, warnings={len(pipeline_result.warnings)}"
        )

        return pipeline_result


@dataclass
class PipelineDependencies:
    """Зависимости для создания pipeline."""

    loader: ILoader
    api_client: IApiClient
    product_repo: IProductRepository
    history_repo: IPriceHistoryRepository
    analytics_repo: IAnalyticsRepository
    marginality_repo: IMarginalityRepository
    maintenance_repo: IMaintenanceRepository
    notifier: INotifier
    calculator: PriceCalculationService
    sync_service: RealPriceSyncService
    pricing_rules: OzonPricingRules
    dry_run: bool = False
    progress_callback: Callable[[int, int, str], None] | None = None


def create_repricing_pipeline(
    deps: PipelineDependencies,
) -> tuple[PipelineOrchestrator, PipelineContext]:
    """
    Фабрика для создания настроенного pipeline репрайсинга.

    Args:
        loader: ILoader - загрузчик Excel
        api_client: IApiClient - клиент Ozon API
        repository: IProductRepository - репозиторий БД
        notifier: INotifier - сервис уведомлений
        calculator: PriceCalculationService - сервис расчёта цен
        dry_run: Режим тестового запуска
        progress_callback: Опциональный колбэк для отображения прогресса (current, total, message)

    Returns:
        Tuple (orchestrator, context)
    """

    steps = [
        SyncRealPricesStep(deps.sync_service, deps.product_repo, deps.dry_run),
        LoadProductsStep(deps.loader, deps.product_repo),
        EnrichProductIdsStep(deps.api_client),
        FetchPricingDataStep(deps.api_client),
        CalculatePricesStep(deps.calculator, deps.pricing_rules),
        PersistToExcelStep(deps.loader, deps.pricing_rules),
        SubmitPricesToOzonStep(deps.api_client, deps.pricing_rules),
        SaveHistoryStep(
            deps.product_repo, deps.history_repo, deps.analytics_repo, deps.marginality_repo
        ),
        SendReportStep(deps.notifier),
        CleanupDatabaseStep(deps.maintenance_repo),
    ]

    context = PipelineContext(
        dry_run=deps.dry_run,
        progress_callback=deps.progress_callback,
    )
    context.set_total_steps(len(steps))

    return PipelineOrchestrator(steps), context
