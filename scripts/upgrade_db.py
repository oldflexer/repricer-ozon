#!/usr/bin/env python3
"""
Отдельный скрипт для применения миграций Alembic.

Вызывается один раз при деплое новой версии (например, из systemd или вручную).
Не должен вызываться из cron или основных скриптов.
"""

import sys
from pathlib import Path

# Добавляем корень проекта в sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.db import run_migrations_once
from infrastructure.logger import setup_logging

logger = setup_logging("migrate.log", mode="a")


def main() -> None:
    """Применяет миграции к БД."""
    logger.info("=== Запуск миграций БД ===")
    try:
        run_migrations_once()
        logger.info("Миграции успешно применены.")
    except Exception as e:
        logger.error(f"Ошибка применения миграций: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
