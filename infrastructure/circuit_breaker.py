"""
Circuit Breaker pattern implementation for HTTP requests.

Prevents cascading failures by stopping requests to failing services
and allowing them time to recover.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TypeVar

from config.settings import settings

T = TypeVar("T")


class CircuitState(Enum):
    """Состояния Circuit Breaker."""

    CLOSED = "closed"  # Нормальная работа, запросы проходят
    OPEN = "open"  # Цепь разомкнута, запросы блокируются
    HALF_OPEN = "half_open"  # Пробный режим после восстановления


class CircuitOpenError(Exception):
    """Исключение, когда Circuit Breaker в состоянии OPEN."""

    def __init__(self, message: str = "Circuit breaker is OPEN - service unavailable"):
        super().__init__(message)


@dataclass
class CircuitBreaker:
    """
    Circuit Breaker для защиты от каскадных отказов.

    Args:
        failure_threshold: Количество ошибок до открытия цепи (default: 5)
        recovery_timeout: Время в секундах перед переходом в HALF_OPEN (default: 30.0)
        success_threshold: Количество успешных вызовов в HALF_OPEN для закрытия (default: 2)
    """

    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    success_threshold: int = 2

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failures: int = field(default=0, init=False)
    _successes: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    @property
    def state(self) -> CircuitState:
        """Текущее состояние Circuit Breaker."""
        return self._state

    def _reset(self) -> None:
        """Сброс счетчиков при закрытии цепи."""
        self._failures = 0
        self._successes = 0
        self._state = CircuitState.CLOSED

    async def call(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        """
        Выполняет функцию с защитой Circuit Breaker.

        Args:
            func: Асинхронная функция для вызова
            *args, **kwargs: Аргументы для функции

        Returns:
            Результат функции

        Raises:
            CircuitOpenError: Если цепь открыта
            Exception: Любое исключение из вызываемой функции
        """
        async with self._lock:
            # Проверяем состояние
            if self._state == CircuitState.OPEN:
                # Проверяем, не пора ли перейти в HALF_OPEN
                if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._successes = 0
                else:
                    raise CircuitOpenError(
                        f"Circuit breaker is OPEN. Retry after "
                        f"{self.recovery_timeout - (time.monotonic() - self._last_failure_time):.1f}s"
                    )

        try:
            result = await func(*args, **kwargs)

            # Успешный вызов
            async with self._lock:
                if self._state == CircuitState.HALF_OPEN:
                    self._successes += 1
                    if self._successes >= self.success_threshold:
                        self._reset()
                elif self._state == CircuitState.CLOSED:
                    self._failures = 0  # Сброс счетчика ошибок при успехе

            return result

        except Exception:
            # Ошибка при вызове
            async with self._lock:
                self._failures += 1
                self._last_failure_time = time.monotonic()

                if self._state == CircuitState.HALF_OPEN:
                    # Любая ошибка в HALF_OPEN возвращает в OPEN
                    self._state = CircuitState.OPEN
                elif self._state == CircuitState.CLOSED:
                    if self._failures >= self.failure_threshold:
                        self._state = CircuitState.OPEN

            raise


# Глобальные экземпляры для разных сервисов
ozon_api_circuit_breaker = CircuitBreaker(
    failure_threshold=settings.API_CB_FAILURE_THRESHOLD,
    recovery_timeout=settings.API_CB_RECOVERY_TIMEOUT,
    success_threshold=settings.API_CB_SUCCESS_THRESHOLD
)

ozon_parser_circuit_breaker = CircuitBreaker(
    failure_threshold=settings.PARSER_CB_FAILURE_THRESHOLD,
    recovery_timeout=settings.PARSER_CB_RECOVERY_TIMEOUT,
    success_threshold=settings.PARSER_CB_SUCCESS_THRESHOLD
)

