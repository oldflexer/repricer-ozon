"""
Use‑case для запуска полного цикла репрайсинга.

Использует Pipeline Pattern вместо монолитного координатора.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from core.domain.pricing_rules import OzonPricingRules
from core.pipeline.orchestrator import (
    PipelineDependencies,
    create_repricing_pipeline,
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


@dataclass(slots=True)
class RepricingUseCaseDependencies:
    """Зависимости RepricingUseCase (группировка для PLR0913)."""

    product_repo: IProductRepository
    history_repo: IPriceHistoryRepository
    analytics_repo: IAnalyticsRepository
    marginality_repo: IMarginalityRepository
    maintenance_repo: IMaintenanceRepository
    api_client: IApiClient
    mail_notifier: INotifier
    loader: ILoader
    pricing_rules: OzonPricingRules
    calculator: PriceCalculationService | None = None
    progress_callback: Callable[[int, int, str], None] | None = None


class RepricingUseCase:
    """
    Use‑case для репрайсинга товаров.

    Инкапсулирует выполнение pipeline репрайсинга.
    """

    def __init__(
        self,
        deps: RepricingUseCaseDependencies,
    ) -> None:
        """
        Инициализирует use‑case.

        Args:
            deps: Все зависимости, сгруппированные в dataclass.
        """
        self._deps = deps

    async def execute(self, dry_run: bool = False) -> dict[str, Any]:
        """
        Запускает полный цикл репрайсинга через pipeline.

        Args:
            dry_run: Если True, цены не отправляются в Ozon,
                     только расчёт и логирование.

        Returns:
            Словарь со статистикой:
                - products_loaded: количество загруженных товаров.
                - prices_updated: количество успешно обновлённых товаров.
                - errors: список ошибок.
                - warnings: список предупреждений.
        """
        # Создаём pipeline с переданными зависимостями
        pipeline_deps = PipelineDependencies(
            loader=self._deps.loader,
            api_client=self._deps.api_client,
            product_repo=self._deps.product_repo,
            history_repo=self._deps.history_repo,
            analytics_repo=self._deps.analytics_repo,
            marginality_repo=self._deps.marginality_repo,
            maintenance_repo=self._deps.maintenance_repo,
            notifier=self._deps.mail_notifier,
            calculator=self._deps.calculator or PriceCalculationService(self._deps.pricing_rules),
            pricing_rules=self._deps.pricing_rules,
            dry_run=dry_run,
            progress_callback=self._deps.progress_callback,
        )
        orchestrator, context = create_repricing_pipeline(pipeline_deps)

        # Выполняем pipeline
        result = await orchestrator.execute(context)

        return {
            "products_loaded": result.products_loaded,
            "prices_updated": result.prices_updated,
            "errors": result.errors,
            "warnings": result.warnings,
        }
