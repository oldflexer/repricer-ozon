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
    ) -> bool:
        """
        Отправляет детальный отчёт по результатам репрайсинга.

        Args:
            updates: Список обновлений цен.
            errors: Список ошибок.
            dry_run: Флаг тестового режима.

        Returns:
            True в случае успеха.
        """
        ...

    @abstractmethod
    def notify_cycle_complete(
        self, updates: list[dict[str, Any]], errors: list[str], dry_run: bool = False
    ) -> bool:
        """
        Уведомляет о завершении цикла репрайсинга.

        Args:
            updates: Список обновлений цен.
            errors: Список ошибок.
            dry_run: Флаг тестового режима.

        Returns:
            True в случае успеха.
        """
        ...

    @abstractmethod
    def notify_critical_event(self, message: str, details: dict[str, Any] | None = None) -> bool:
        """
        Отправляет уведомление о критическом событии.

        Args:
            message: Текст сообщения.
            details: Дополнительные детали.

        Returns:
            True в случае успеха.
        """
        ...
