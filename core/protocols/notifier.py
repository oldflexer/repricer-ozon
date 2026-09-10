"""
Протоколы (Interfaces) для уведомлений.

Определяют контракты для отправки email и других уведомлений.
"""

from abc import abstractmethod
from typing import Any, Protocol


class INotifier(Protocol):
    """Интерфейс сервиса уведомлений."""

    @abstractmethod
    def send_detailed_report(
        self, updates: list[dict[str, Any]], errors: list[str], dry_run: bool = False
    ) -> None:
        """
        Отправляет детальный отчёт по результатам репрайсинга.

        Args:
            updates: Список обновлений цен.
            errors: Список ошибок.
            dry_run: Флаг тестового режима.
        """
        ...

    @abstractmethod
    def notify_cycle_complete(
        self, updated_count: int, errors: list[str] | None = None
    ) -> None:
        """
        Уведомляет о завершении цикла репрайсинга.

        Args:
            updated_count: Количество обновлённых товаров.
            errors: Список ошибок (опционально).
        """
        ...

    @abstractmethod
    def notify_critical_event(self, event: str) -> None:
        """
        Отправляет уведомление о критическом событии.

        Args:
            event: Текст события.
        """
        ...
