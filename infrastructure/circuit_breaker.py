"""
Circuit Breaker pattern implementation for HTTP requests.

Prevents cascading failures by stopping requests to failing services
and allowing them time to recover.

Includes metrics export for monitoring and manual reset capability.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

from config.settings import settings
from core.metrics import (
    circuit_breaker_state,
    circuit_breaker_failures_total,
    circuit_breaker_successes_total,
    circuit_breaker_state_changes_total,
)

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
        name: Имя circuit breaker для метрик
    """

    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    success_threshold: int = 2
    name: str = "default"

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failures: int = field(default=0, init=False)
    _successes: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    _total_calls: int = field(default=0, init=False)
    _total_failures: int = field(default=0, init=False)
    _total_successes: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        """Initialize metrics after creation."""
        self._update_metrics()

    @property
    def state(self) -> CircuitState:
        """Текущее состояние Circuit Breaker."""
        return self._state

    def _reset(self) -> None:
        """Сброс счетчиков при закрытии цепи."""
        self._failures = 0
        self._successes = 0
        self._state = CircuitState.CLOSED
        self._update_metrics()

    def _update_metrics(self) -> None:
        """Update Prometheus metrics."""
        state_value = {"closed": 0, "open": 1, "half_open": 2}.get(self._state.value, 0)
        circuit_breaker_state.labels(name=self.name).set(state_value)
        circuit_breaker_failures_total.labels(name=self.name).inc(0)  # Initialize
        circuit_breaker_successes_total.labels(name=self.name).inc(0)  # Initialize

# Circuit Breaker methods to append to circuit_breaker.py

    async def call(self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
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
                    self._update_metrics()
                else:
                    raise CircuitOpenError(
                        f"Circuit breaker is OPEN. Retry after "
                        f"{self.recovery_timeout - (time.monotonic() - self._last_failure_time):.1f}s"
                    )

        try:
            result = await func(*args, **kwargs)

            # Успешный вызов
            async with self._lock:
                self._total_calls += 1
                self._total_successes += 1
                circuit_breaker_successes_total.labels(name=self.name).inc()

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
                self._total_calls += 1
                self._total_failures += 1
                self._failures += 1
                self._last_failure_time = time.monotonic()
                circuit_breaker_failures_total.labels(name=self.name).inc()

                if self._state == CircuitState.HALF_OPEN:
                    # Любая ошибка в HALF_OPEN возвращает в OPEN
                    self._state = CircuitState.OPEN
                    self._update_metrics()
                    circuit_breaker_state_changes_total.labels(
                        name=self.name, from_state="half_open", to_state="open"
                    ).inc()
                elif (
                    self._state == CircuitState.CLOSED and self._failures >= self.failure_threshold
                ):
                    self._state = CircuitState.OPEN
                    self._update_metrics()
                    circuit_breaker_state_changes_total.labels(
                        name=self.name, from_state="closed", to_state="open"
                    ).inc()

            raise

    def get_metrics(self) -> dict[str, Any]:
        """Возвращает текущие метрики circuit breaker."""
        return {
            "name": self.name,
            "state": self._state.value,
            "failures": self._failures,
            "successes": self._successes,
            "total_calls": self._total_calls,
            "total_failures": self._total_failures,
            "total_successes": self._total_successes,
            "last_failure_time": self._last_failure_time,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "success_threshold": self.success_threshold,
        }

    def reset(self) -> None:
        """Ручной сброс circuit breaker в состояние CLOSED."""
        async def _reset() -> None:
            async with self._lock:
                old_state = self._state
                self._reset()
                if old_state != CircuitState.CLOSED:
                    circuit_breaker_state_changes_total.labels(
                        name=self.name, from_state=old_state.value, to_state="closed"
                    ).inc()
        # Run the async reset
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_reset())
            else:
                loop.run_until_complete(_reset())
        except RuntimeError:
            # No event loop, run directly
            asyncio.run(_reset())

    def force_open(self) -> None:
        """Принудительно открывает circuit breaker."""
        async def _force_open() -> None:
            async with self._lock:
                old_state = self._state
                self._state = CircuitState.OPEN
                self._last_failure_time = time.monotonic()
                self._update_metrics()
                if old_state != CircuitState.OPEN:
                    circuit_breaker_state_changes_total.labels(
                        name=self.name, from_state=old_state.value, to_state="open"
                    ).inc()
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_force_open())
            else:
                loop.run_until_complete(_force_open())
        except RuntimeError:
            asyncio.run(_force_open())


# Глобальные экземпляры для разных сервисов
ozon_api_circuit_breaker = CircuitBreaker(
    failure_threshold=settings.API_CB_FAILURE_THRESHOLD,
    recovery_timeout=settings.API_CB_RECOVERY_TIMEOUT,
    success_threshold=settings.API_CB_SUCCESS_THRESHOLD,
    name="ozon_api",
)

ozon_parser_circuit_breaker = CircuitBreaker(
    failure_threshold=settings.PARSER_CB_FAILURE_THRESHOLD,
    recovery_timeout=settings.PARSER_CB_RECOVERY_TIMEOUT,
    success_threshold=settings.PARSER_CB_SUCCESS_THRESHOLD,
    name="ozon_parser",
)