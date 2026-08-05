"""
Use‑case для запуска полного цикла репрайсинга.

Делегирует выполнение PriceUpdateCoordinator.
"""

from typing import Any, Dict

from core.price_coordinator import PriceUpdateCoordinator
from core.repository import IProductRepository


class RepricingUseCase:
    """
    Use‑case для репрайсинга товаров.

    Инкапсулирует вызов координатора, предоставляя единый интерфейс
    для запуска процесса обновления цен.
    """

    def __init__(self, repository: IProductRepository, api_client, mail_notifier, loader) -> None:
        """
        Инициализирует use‑case.

        Args:
            repository: Репозиторий для работы с БД.
            api_client: Клиент Ozon API.
            mail_notifier: Сервис для отправки email‑уведомлений.
            loader: Загрузчик данных из Excel.
        """
        self.coordinator = PriceUpdateCoordinator(
            repository, api_client, loader, mail_notifier
        )

    async def execute(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Запускает полный цикл репрайсинга.

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
        return await self.coordinator.run(dry_run=dry_run)