"""
Общие утилиты для скриптов (repricer, parser, и др.).

Централизует:
- обработчики сигналов для graceful shutdown
- настройку логирования
"""

import signal
import types
from typing import Any

from config.settings import settings
from infrastructure.logger import logger, setup_logging
from infrastructure.logger import setup_parser_logging as _setup_parser_logging

# Глобальный флаг для graceful shutdown (используется в скриптах)
_shutdown_requested = False


def _signal_handler(signum: int, _frame: types.FrameType | None) -> None:
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


def setup_script_logging(script_name: str, mode: str = "a") -> Any:
    """
    Настраивает логирование для скрипта с учётом INSTANCE_NAME.

    Args:
        script_name: Имя скрипта (например, "repricer", "parser").
        mode: Режим открытия файла лога ('a' для append, 'w' для перезаписи).

    Returns:
        Настроенный логгер.
    """
    return setup_logging(f"{script_name}-{settings.INSTANCE_NAME}.log", mode=mode)


def setup_parser_logging(script_name: str, mode: str = "a") -> Any:
    """
    Настраивает логирование для парсера с учётом INSTANCE_NAME.

    Args:
        script_name: Имя скрипта (например, "parser").
        mode: Режим открытия файла лога.

    Returns:
        Настроенный логгер.
    """
    return _setup_parser_logging(f"{script_name}-{settings.INSTANCE_NAME}.log", mode=mode)
