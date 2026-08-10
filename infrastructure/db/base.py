"""
Базовый класс для всех миксинов, предоставляющий метод получения соединения с БД.
"""

import sqlite3
from abc import ABC, abstractmethod


class DBConnectionMixin(ABC):
    """Абстрактный базовый класс, требующий реализации метода _get_connection."""

    @abstractmethod
    def _get_connection(self) -> sqlite3.Connection:
        """Возвращает соединение с SQLite."""
        pass
