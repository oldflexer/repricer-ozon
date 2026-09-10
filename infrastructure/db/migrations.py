"""
Функции для работы с миграциями Alembic.
"""

import subprocess
import sys
from pathlib import Path

from infrastructure.logger import logger


def run_migrations_once() -> None:
    """
    Запускает миграции Alembic один раз при старте приложения.

    Вызывается из скрипта scripts/upgrade_db.py при деплое.
    При ошибке логирует и выбрасывает RuntimeError.
    """
    root_dir = Path(__file__).resolve().parent.parent.parent  # до корня проекта
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=root_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            logger.error(f"Ошибка выполнения миграций: {result.stderr}")
            raise RuntimeError(f"Не удалось применить миграции: {result.stderr}")
        logger.info("Миграции успешно применены.")
    except Exception as e:
        logger.error(f"Не удалось запустить alembic: {e}")
        raise
