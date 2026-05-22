import logging
from typing import Dict, Any
from .orchestrator import PricingOrchestrator
from infrastructure.logger import logger


class RepricingUseCase:
    def __init__(self, repository, api_client, mail_notifier, loader):
        self.orchestrator = PricingOrchestrator(repository, api_client, mail_notifier, loader)

    async def execute(self, dry_run: bool = False) -> Dict[str, Any]:
        return await self.orchestrator.run(dry_run=dry_run)