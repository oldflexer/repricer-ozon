"""
Общие утилиты для скриптов (repricer, parser, и др.).

Централизует:
- запуск миграций (run_migrations_once)
- обработчики сигналов для graceful shutdown
- настройку логирования
"""

import signal
import subprocess
import sys
from pathlib import Path
from typing import Optional

from config.settings import settings
from infrastructure.logger import logger


# Глобальный флаг для graceful shutdown (используется в скриптах)
_shutdown_requested = False


def _signal_handler(signum: int, frame) -> None:
    """Стандартный обработчик сигналов для graceful shutdown."""
    global _shutdown_requested
    logger.warning(f"Received signal {signum}, initiating graceful shutdown...")
    _shutdown_requested = True


def register_signal_handlers() -> None:
    """
    Регистрирует обработчики SIGTERM и SIGINT.

    Вызывать в main() каждого скрипта перед основной логикой.
    """
    global _shutdown_requested
    _shutdown_requested = False
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)


def is_shutdown_requested() -> bool:
    """Возвращает True, если был получен сигнал завершения."""
    return _shutdown_requested


def run_migrations_once() -> None:
    """
    Запускает миграции Alembic один раз при старте приложения.

    Вызывается явно в точках входа: scripts/repricer.py, app.py, scripts/parser.py.
    При ошибке логирует и выбрасывает RuntimeError.
    """
    root_dir = Path(__file__).resolve().parent.parent
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


def setup_script_logging(script_name: str, mode: str = "a"):
    """
    Настраивает логирование для скрипта с учётом INSTANCE_NAME.

    Args:
        script_name: Имя скрипта (например, "repricer", "parser").
        mode: Режим открытия файла лога ('a' для append, 'w' для перезаписи).

    Returns:
        Настроенный логгер.
    """
    from infrastructure.logger import setup_logging
    return setup_logging(f"{script_name}-{settings.INSTANCE_NAME}.log", mode=mode)


def setup_parser_logging(script_name: str, mode: str = "a"):
    """
    Настраивает логирование для парсера с учётом INSTANCE_NAME.

    Args:
        script_name: Имя скрипта (например, "parser").
        mode: Режим открытия файла лога.

    Returns:
        Настроенный логгер.
    """
    from infrastructure.logger import setup_parser_logging
    return setup_parser_logging(f"{script_name}-{settings.INSTANCE_NAME}.log", mode=mode)