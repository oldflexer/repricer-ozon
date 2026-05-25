import logging
from typing import Dict, Any
from .orchestrator import PricingOrchestrator


class RepricingUseCase:
    def __init__(self, repository, api_client, mail_notifier, loader):
        self.orchestrator = PricingOrchestrator(repository, api_client, mail_notifier, loader)

    async def execute(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Запускает полный цикл репрайсинга.
        
        :param dry_run: Если True, цены не отправляются в Ozon, только расчёт и логирование.
        :return: Словарь со статистикой: количество загруженных товаров, обновлённых цен, ошибки.
        """
        return await self.orchestrator.run(dry_run=dry_run)