import sys
from pathlib import Path
from datetime import datetime, timedelta
import json

# Добавляем корень проекта (родитель tests/) в sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.calculator import PriceCalculator, MarginCalculator


def test_price_strategies():
    """Тест базовых стратегий ценообразования через calculate_strategy_price"""
    calc = PriceCalculator()

    comp_prices = [1000.0, 1050.0, 980.0]
    min_price = 900.0

    intervals = [{"start": "00:00", "end": "23:59", "strategy": 1, "percent": 5.0}]
    target = calc.calculate_strategy_price(comp_prices, intervals, min_price)
    expected = max(min_price, min(comp_prices) * 0.95)
    print(f"Стратегия 1 (ниже на 5%): {target} (ожидаем ~931) - {'✅' if abs(target - expected) < 0.01 else '❌'}")

    intervals = [{"start": "00:00", "end": "23:59", "strategy": 2, "percent": 10.0}]
    target = calc.calculate_strategy_price(comp_prices, intervals, min_price)
    expected = max(min_price, min(comp_prices) * 1.10)
    print(f"Стратегия 2 (выше на 10%): {target} (ожидаем ~1078) - {'✅' if abs(target - expected) < 0.01 else '❌'}")

    intervals = [{"start": "00:00", "end": "23:59", "strategy": 3, "percent": 0.0}]
    target = calc.calculate_strategy_price(comp_prices, intervals, min_price)
    expected = min(comp_prices)
    print(f"Стратегия 3 (равная): {target} (ожидаем 980) - {'✅' if abs(target - expected) < 0.01 else '❌'}")

    high_min = 1500.0
    target = calc.calculate_strategy_price(comp_prices, intervals, high_min)
    print(f"С ограничением min_price=1500: {target} (ожидаем 1500) - {'✅' if target == 1500 else '❌'}")

    target = calc.calculate_strategy_price([], intervals, min_price)
    print(f"Пустой список конкурентов: {target} (ожидаем {min_price}) - {'✅' if target == min_price else '❌'}")
    print()


def test_ozon_coefficient():
    """Тест коэффициента Ozon"""
    calc = PriceCalculator()

    coef = calc.calculate_ozon_coefficient(800.0, 1000.0)
    expected = 0.8
    print(f"Коэффициент при real_price=800, min_price=1000: {coef} (ожидаем {expected}) - {'✅' if abs(coef - expected) < 0.001 else '❌'}")

    coef = calc.calculate_ozon_coefficient(None, 1000.0)
    print(f"Коэффициент без real_price: {coef} (ожидаем 0.75) - {'✅' if abs(coef - 0.75) < 0.001 else '❌'}")

    coef = calc.calculate_ozon_coefficient(1200.0, 1000.0)
    print(f"Коэффициент при real_price > min_price: {coef} (ожидаем 0.75) - {'✅' if abs(coef - 0.75) < 0.001 else '❌'}")
    print()


def test_margin_calculation():
    """Тест расчёта маржинальности"""
    class MockDB:
        pass

    calc = MarginCalculator(MockDB())

    margin = calc.calculate_margin(2000.0, 1000.0)
    expected = 32.5
    print(f"Маржа стандартная: {margin:.2f}% (ожидаем {expected}%) - {'✅' if abs(margin - expected) < 0.01 else '❌'}")

    margin_zero = calc.calculate_margin(0, 1000.0)
    print(f"Цена = 0: {margin_zero}% (ожидаем 0) - {'✅' if margin_zero == 0 else '❌'}")

    margin_neg = calc.calculate_margin(1000, 1200)
    expected_neg = -40.0
    print(f"Отрицательная маржа: {margin_neg:.2f}% (ожидаем {expected_neg}%) - {'✅' if abs(margin_neg - expected_neg) < 0.01 else '❌'}")
    print()


if __name__ == "__main__":
    test_price_strategies()
    test_ozon_coefficient()
    test_margin_calculation()