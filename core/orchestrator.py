"""
Оркестратор репрайсинга (устаревший, для обратной совместимости).

Делегирует выполнение PriceUpdateCoordinator.
"""

from typing import Any, Dict

from core.price_coordinator import PriceUpdateCoordinator
from core.repository import IProductRepository
from infrastructure.logger import logger


class PricingOrchestrator:
    """
    Устаревший класс-обёртка, оставлен для обратной совместимости.

    Вся логика перенесена в PriceUpdateCoordinator. Этот класс только
    создаёт экземпляр координатора и делегирует вызов run().
    """

    def __init__(self, repository: IProductRepository, api_client, mail_notifier, loader) -> None:
        """
        Инициализирует оркестратор.

        Args:
            repository: Репозиторий для работы с БД.
            api_client: Клиент Ozon API.
            mail_notifier: Сервис для отправки email-уведомлений.
            loader: Загрузчик данных из Excel.
        """
        self.coordinator = PriceUpdateCoordinator(repository, api_client, loader, mail_notifier)

    async def run(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Запускает полный цикл репрайсинга (делегирует координатору).

        Args:
            dry_run: Если True, цены не отправляются в Ozon.

        Returns:
            Словарь со статистикой выполнения.
        """
        logger.info("PricingOrchestrator.run() делегирован в PriceUpdateCoordinator")
        return await self.coordinator.run(dry_run=dry_run)