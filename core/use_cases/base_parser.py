"""
Базовый интерфейс для всех парсеров.

Определяет контракт для выполнения парсинга с поддержкой dry-run.
"""

from abc import ABC, abstractmethod


class BaseParserUseCase(ABC):
    """Абстрактный базовый класс для всех парсеров."""

    @abstractmethod
    async def execute(self, dry_run: bool = False) -> dict[str, int]:
        """
        Запускает парсинг.

        Args:
            dry_run: Если True, данные не сохраняются.

        Returns:
            Словарь со статистикой:
                - updated: количество успешно обновлённых записей
                - errors: количество ошибок
                - skipped: количество пропущенных записей
        """
        pass
