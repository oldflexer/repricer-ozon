"""
Value Objects для доменного слоя.

Неизменяемые объекты-значения, инкапсулирующие бизнес-логику валидации
и операций над примитивными типами.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Self

# Константы для валидации времени
MAX_HOUR = 23
MAX_MINUTE = 59


@dataclass(frozen=True, slots=True)
class SKU:
    """Артикул товара (Stock Keeping Unit)."""

    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValueError("SKU cannot be empty")
        object.__setattr__(self, "value", self.value.strip())

    def __str__(self) -> str:
        return self.value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SKU):
            return False
        return self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)


@dataclass(frozen=True, slots=True)
class Money:
    """Денежная сумма в рублях с копейками (хранится в копейках для точности)."""

    _kopecks: int

    @classmethod
    def from_rubles(cls, rubles: float | int | str) -> Self:
        """Создаёт Money из рублей (float)."""
        if isinstance(rubles, str):
            rubles_decimal = Decimal(rubles)
        elif isinstance(rubles, float):
            rubles_decimal = Decimal(str(rubles))
        elif isinstance(rubles, int):
            rubles_decimal = Decimal(rubles)
        kopecks = int((rubles_decimal * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        return cls(kopecks)

    @classmethod
    def from_kopecks(cls, kopecks: int) -> Self:
        """Создаёт Money из копеек."""
        return cls(kopecks)

    @property
    def rubles(self) -> Decimal:
        """Возвращает сумму в рублях как Decimal."""
        return Decimal(self._kopecks) / 100

    @property
    def rubles_float(self) -> float:
        """Возвращает сумму в рублях как float (для совместимости)."""
        return float(self.rubles)

    @property
    def kopecks(self) -> int:
        """Возвращает сумму в копейках."""
        return self._kopecks

    def __add__(self, other: Self) -> Self:
        if not isinstance(other, Money):
            return NotImplemented
        return self.__class__(self._kopecks + other._kopecks)

    def __sub__(self, other: Self) -> Self:
        if not isinstance(other, Money):
            return NotImplemented
        return self.__class__(self._kopecks - other._kopecks)

    def __mul__(self, factor: float | int | Decimal) -> Self:
        if isinstance(factor, float):
            factor = Decimal(str(factor))
        elif isinstance(factor, int):
            factor = Decimal(factor)
        result = (Decimal(self._kopecks) * factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return self.__class__(int(result))

    def __truediv__(self, divisor: float | int | Decimal) -> Self:
        if isinstance(divisor, float):
            divisor = Decimal(str(divisor))
        elif isinstance(divisor, int):
            divisor = Decimal(divisor)
        result = (Decimal(self._kopecks) / divisor).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return self.__class__(int(result))

    def __lt__(self, other: Self) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self._kopecks < other._kopecks

    def __le__(self, other: Self) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self._kopecks <= other._kopecks

    def __gt__(self, other: Self) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self._kopecks > other._kopecks

    def __ge__(self, other: Self) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self._kopecks >= other._kopecks

    def max(self, other: Self) -> Self:
        """Возвращает максимальное значение."""
        return self if self >= other else other

    def min(self, other: Self) -> Self:
        """Возвращает минимальное значение."""
        return self if self <= other else other

    def round_to(self, step: int) -> Self:
        """Округляет до ближайшего кратного step (в рублях)."""
        step_kopecks = step * 100
        rounded = ((self._kopecks + step_kopecks - 1) // step_kopecks) * step_kopecks
        return self.__class__(rounded)

    def __str__(self) -> str:
        return f"{self.rubles:.2f} ₽"

    def __repr__(self) -> str:
        return f"Money({self.rubles:.2f})"


@dataclass(frozen=True, slots=True)
class Percentage:
    """Процентное значение (0.0 - 1.0 для долей, 0-100 для процентов)."""

    _value: Decimal  # Хранится как доля (0.15 = 15%)

    @classmethod
    def from_percent(cls, percent: float | int | str) -> Self:
        """Создаёт из процентов (15 -> 0.15)."""
        if isinstance(percent, str):
            percent_decimal = Decimal(percent)
        elif isinstance(percent, float):
            percent_decimal = Decimal(str(percent))
        else:
            percent_decimal = Decimal(percent)
        return cls(percent_decimal / 100)

    @classmethod
    def from_ratio(cls, ratio: float | int | str) -> Self:
        """Создаёт из доли (0.15 -> 0.15)."""
        if isinstance(ratio, str):
            ratio_decimal = Decimal(ratio)
        elif isinstance(ratio, float):
            ratio_decimal = Decimal(str(ratio))
        else:
            ratio_decimal = Decimal(ratio)
        return cls(ratio_decimal)

    @property
    def percent(self) -> Decimal:
        """Возвращает в процентах (15%)."""
        return self._value * 100

    @property
    def ratio(self) -> Decimal:
        """Возвращает как долю (0.15)."""
        return self._value

    @property
    def percent_float(self) -> float:
        return float(self.percent)

    @property
    def ratio_float(self) -> float:
        return float(self._value)

    def apply_to(self, money: Money) -> Money:
        """Применяет процент к денежной сумме."""
        return money * self._value

    def __mul__(self, other: float | int | Decimal) -> Self:
        if isinstance(other, float):
            other = Decimal(str(other))
        elif isinstance(other, int):
            other = Decimal(other)
        return self.__class__(self._value * other)

    def __add__(self, other: Self) -> Self:
        if not isinstance(other, Percentage):
            return NotImplemented
        return self.__class__(self._value + other._value)

    def __str__(self) -> str:
        return f"{self.percent:.2f}%"

    def __repr__(self) -> str:
        return f"Percentage({self.percent:.2f}%)"


@dataclass(frozen=True, slots=True)
class DiscountCoefficient:
    """Коэффициент дисконта (реальная_цена / маркетинговая_цена). Всегда 0 < coef <= 1."""

    _value: Decimal

    def __post_init__(self) -> None:
        if self._value <= 0 or self._value > 1:
            raise ValueError(f"Discount coefficient must be in (0, 1], got {self._value}")

    @classmethod
    def from_ratio(cls, ratio: float | int | str) -> Self:
        if isinstance(ratio, str):
            ratio_decimal = Decimal(ratio)
        elif isinstance(ratio, float):
            ratio_decimal = Decimal(str(ratio))
        else:
            ratio_decimal = Decimal(ratio)
        return cls(ratio_decimal)

    @property
    def value(self) -> Decimal:
        return self._value

    @property
    def value_float(self) -> float:
        return float(self._value)

    def apply_to(self, marketing_price: Money) -> Money:
        """Вычисляет реальную цену: marketing_price * discount_coef."""
        return marketing_price * self._value

    def reverse(self, real_price: Money) -> Money:
        """Вычисляет маркетинговую цену из реальной: real_price / discount_coef."""
        return real_price / self._value

    def __str__(self) -> str:
        return f"{self._value:.4f}"

    def __repr__(self) -> str:
        return f"DiscountCoefficient({self._value:.4f})"


@dataclass(frozen=True, slots=True)
class TimeInterval:
    """Временной интервал (HH:MM - HH:MM)."""

    start_hour: int
    start_minute: int
    end_hour: int
    end_minute: int

    def __post_init__(self) -> None:
        for name, value in [
            ("start_hour", self.start_hour),
            ("start_minute", self.start_minute),
            ("end_hour", self.end_hour),
            ("end_minute", self.end_minute),
        ]:
            if not isinstance(value, int):
                raise ValueError(f"{name} must be int")
        if not (0 <= self.start_hour <= MAX_HOUR and 0 <= self.start_minute <= MAX_MINUTE):
            raise ValueError("Invalid start time")
        if not (0 <= self.end_hour <= MAX_HOUR and 0 <= self.end_minute <= MAX_MINUTE):
            raise ValueError("Invalid end time")

    @classmethod
    def from_string(cls, start: str, end: str) -> Self:
        """Создаёт из строк 'HH:MM'."""
        sh, sm = map(int, start.split(":"))
        eh, em = map(int, end.split(":"))
        return cls(sh, sm, eh, em)

    @property
    def start_minutes(self) -> int:
        return self.start_hour * 60 + self.start_minute

    @property
    def end_minutes(self) -> int:
        return self.end_hour * 60 + self.end_minute

    def contains(self, hour: int, minute: int) -> bool:
        """Проверяет, входит ли время в интервал (учитывая переход через полночь)."""
        current = hour * 60 + minute
        if self.start_minutes <= self.end_minutes:
            return self.start_minutes <= current <= self.end_minutes
        # Интервал через полночь (например, 22:00 - 06:00)
        return current >= self.start_minutes or current <= self.end_minutes

    def __str__(self) -> str:
        return f"{self.start_hour:02d}:{self.start_minute:02d}-{self.end_hour:02d}:{self.end_minute:02d}"
