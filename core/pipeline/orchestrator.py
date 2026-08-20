"""
Pipeline Orchestrator - управляет выполнением последовательности шагов.
"""

from dataclasses import dataclass

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
from infrastructure.logger import logger


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
        logger.info(f"Starting pipeline with {len(self.steps)} steps")

        for step in self.steps:
            if context.should_stop:
                logger.warning(f"Pipeline stopped before step {step.name} due to critical error")
                break

            logger.info(f"Executing pipeline step: {step.name}")
            try:
                await step.execute(context)
            except Exception as e:
                logger.exception(f"Pipeline step {step.name} failed with exception")
                context.add_error(f"Step {step.name} failed: {e}")
                context.should_stop = True

        # Подсчет статистики
        prices_updated = 0
        if context.dry_run:
            # В dry_run считаем успешными все расчётные результаты
            prices_updated = len(context.calculation_results)
        elif context.api_results:
            prices_updated = sum(1 for r in context.api_results.values() if r.get("updated", False))

        result = PipelineResult(
            products_loaded=len(context.products),
            prices_updated=prices_updated,
            errors=context.errors,
            warnings=context.warnings,
        )

        logger.info(
            f"Pipeline completed: loaded={result.products_loaded}, "
            f"updated={result.prices_updated}, errors={len(result.errors)}, warnings={len(result.warnings)}"
        )

        return result


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
    dry_run: bool = False


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

    Returns:
        Tuple (orchestrator, context)
    """

    steps = [
        LoadProductsStep(deps.loader, deps.product_repo),
        EnrichProductIdsStep(deps.api_client),
        FetchPricingDataStep(deps.api_client),
        CalculatePricesStep(deps.calculator),
        PersistToExcelStep(deps.loader),
        SubmitPricesToOzonStep(deps.api_client),
        SaveHistoryStep(
            deps.product_repo, deps.history_repo, deps.analytics_repo, deps.marginality_repo
        ),
        SendReportStep(deps.notifier),
        CleanupDatabaseStep(deps.maintenance_repo),
    ]

    context = PipelineContext(dry_run=deps.dry_run)

    return PipelineOrchestrator(steps), context
