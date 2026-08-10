"""
Перечисления (Enums) для доменных сущностей.

Заменяет магические числа на типобезопасные значения.
"""

from enum import IntEnum

from infrastructure.logger import logger


class StrategyType(IntEnum):
    """
    Тип стратегии ценообразования.

    Значения соответствуют кодам в БД и Excel:
    - 1: BELOW (ниже индекса/конкурента)
    - 2: ABOVE (выше индекса/конкурента)
    - 3: EQUAL (равна индексу/РИЦ)
    """

    BELOW = 1  # "Ниже" - цена ниже базовой на заданный процент
    ABOVE = 2  # "Выше" - цена выше базовой на заданный процент
    EQUAL = 3  # "Равная" - цена равна целевой минимальной (РИЦ / discount_coef)


class StrategyDirection(IntEnum):
    """Направление отклонения для стратегий BELOW/ABOVE."""

    NEGATIVE = -1  # Для BELOW: base_price * (1 - percent/100)
    POSITIVE = 1  # Для ABOVE: base_price * (1 + percent/100)


def parse_strategy_value(value) -> StrategyType:
    """
    Преобразует значение из Excel/БД в StrategyType.

    Поддерживает:
        - числа 1, 2, 3
        - текстовые варианты: 'ниже', 'выше', 'равная' (любой регистр)
        - строковые представления чисел

    Args:
        value: Значение из ячейки (строка, число, None).

    Returns:
        StrategyType: Соответствующий тип стратегии (по умолчанию EQUAL).
    """
    import pandas as pd

    if pd.isna(value):
        return StrategyType.EQUAL

    # Числовые значения
    try:
        num = int(float(value))
        if num in (1, 2, 3):
            return StrategyType(num)
    except (ValueError, TypeError):
        pass

    # Текстовые значения
    str_val = str(value).strip().lower()
    if str_val in ("ниже", "ниже индекса", "1", "below"):
        return StrategyType.BELOW
    if str_val in ("выше", "выше индекса", "2", "above"):
        return StrategyType.ABOVE
    if str_val in ("равная", "равно", "равна", "равен", "3", "equal"):
        return StrategyType.EQUAL
    logger.warning(f"Неизвестное значение стратегии '{value}', используется 'Равная' (EQUAL)")
    return StrategyType.EQUAL


def strategy_to_display_name(strategy: StrategyType) -> str:
    """Возвращает русское название стратегии для отображения в UI/логах."""
    names = {
        StrategyType.BELOW: "Ниже",
        StrategyType.ABOVE: "Выше",
        StrategyType.EQUAL: "Равная",
    }
    return names.get(strategy, "Неизвестно")


def strategy_to_english(strategy: StrategyType) -> str:
    """Возвращает английское название стратегии для API/логов."""
    names = {
        StrategyType.BELOW: "below",
        StrategyType.ABOVE: "above",
        StrategyType.EQUAL: "equal",
    }
    return names.get(strategy, "unknown")
