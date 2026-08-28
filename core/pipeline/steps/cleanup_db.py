"""
Шаг 10: Очистка старых записей в БД (auto cleanup).
"""

from core.pipeline.steps.base import PipelineContext, PipelineStep
from core.protocols.repository import IMaintenanceRepository
from infrastructure.logger import logger


class CleanupDatabaseStep(PipelineStep):
    """Шаг 10: Очистка старых записей в БД (auto cleanup)."""

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
