"""
Сервис для управления миграциями базы данных.
"""

from infrastructure.db import run_migrations_once
from infrastructure.logger import logger


class MigrationService:
    """Сервис для применения миграций Alembic."""

    @staticmethod
    def run_migrations() -> None:
        """
        Применяет миграции к БД.
        Вызывается при деплое (один раз).
        """
        logger.info("=== Запуск миграций БД ===")
        try:
            run_migrations_once()
            logger.info("Миграции успешно применены.")
        except Exception as e:
            logger.error(f"Ошибка применения миграций: {e}")
            raise