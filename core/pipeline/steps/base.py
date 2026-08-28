"""
Pipeline base classes - PipelineStep, PipelineContext, PipelineResult.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import time
from typing import Any, TypeVar

from core.domain.product import Product
from core.entities import PriceCalculationResult, PricingData
from infrastructure.logger import logger

T = TypeVar("T")


@dataclass
class PipelineResult:
    """Результат выполнения pipeline."""

    products_loaded: int
    prices_updated: int
    errors: list[str]
    warnings: list[str]


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
    progress_callback: Callable[[int, int, str], None] | None = None
    request_id: str | None = None
    _current_step: int = field(default=0, init=False, repr=False)
    _total_steps: int = field(default=0, init=False, repr=False)

    def add_error(self, message: str) -> None:
        self.errors.append(message)
        logger.error(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)
        logger.warning(message)

    def set_total_steps(self, total: int) -> None:
        """Устанавливает общее количество шагов для прогресса."""
        self._total_steps = total

    def report_progress(self, step: int, message: str) -> None:
        """Вызывает callback прогресса, если задан."""
        self._current_step = step
        if self.progress_callback:
            self.progress_callback(step, self._total_steps, message)
        logger.info(f"Pipeline progress: step {step}/{self._total_steps} - {message}")


class PipelineStep[T](ABC):
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
