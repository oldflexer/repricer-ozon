from typing import Dict, Any
from core.repository import IProductRepository
from core.price_coordinator import PriceUpdateCoordinator
from infrastructure.logger import logger


class PricingOrchestrator:
    """
    Устаревший класс, оставлен для обратной совместимости.
    Использует новый PriceUpdateCoordinator.
    """
    def __init__(self, repository: IProductRepository, api_client, mail_notifier, loader):
        self.coordinator = PriceUpdateCoordinator(repository, api_client, loader, mail_notifier)

    async def run(self, dry_run: bool = False) -> Dict[str, Any]:
        logger.info("PricingOrchestrator.run() делегирован в PriceUpdateCoordinator")
        return await self.coordinator.run(dry_run=dry_run)