"""
Декоратор для повторных попыток HTTP-запросов с экспоненциальной задержкой.
"""

import asyncio
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from infrastructure.logger import logger

F = TypeVar("F", bound=Callable[..., Any])


def retry_on_error(max_retries: int = 3, backoff_base: float = 2.0) -> Callable[[F], F]:
    """
    Декоратор для повторных попыток при ошибках HTTP-запросов.

    Args:
        max_retries: Максимальное количество попыток (включая первую).
        backoff_base: Базовое значение для экспоненциальной задержки (сек).

    Returns:
        Декорированная асинхронная функция.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any | None:
            last_exception = None
            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(f"HTTP request failed (attempt {attempt}/{max_retries}): {e}")
                    if attempt < max_retries:
                        delay = backoff_base ** (attempt - 1)
                        await asyncio.sleep(delay)
            logger.error(f"All {max_retries} attempts failed: {last_exception}")
            return None

        return wrapper  # type: ignore[return-value]

    return decorator
