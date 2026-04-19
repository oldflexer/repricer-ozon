import sys
from pathlib import Path
from datetime import datetime, timedelta
import json

sys.path.insert(0, str(Path(__file__).parent))

from src.calculator import PriceCalculator, MarginCalculator


def test_price_strategies():
    """Тест базовых стратегий ценообразования"""
    calc = PriceCalculator()
    
    # Цены конкурентов
    comp_prices = [1000.0, 1050.0, 980.0]
    min_price = 900.0
    
    # Стратегия 1: ниже конкурента на 5%
    target = calc.calculate_target_price(comp_prices, 1, 5.0, min_price)
    expected = max(min_price, min(comp_prices) * 0.95)  # 980 * 0.95 = 931
    print(f"Стратегия 1 (ниже на 5%): {target} (ожидаем ~931) - {'✅' if abs(target - expected) < 0.01 else '❌'}")
    
    # Стратегия 2: выше конкурента на 10%
    target = calc.calculate_target_price(comp_prices, 2, 10.0, min_price)
    expected = max(min_price, min(comp_prices) * 1.10)  # 980 * 1.10 = 1078
    print(f"Стратегия 2 (выше на 10%): {target} (ожидаем ~1078) - {'✅' if abs(target - expected) < 0.01 else '❌'}")
    
    # Стратегия 3: равная цена
    target = calc.calculate_target_price(comp_prices, 3, 0.0, min_price)
    expected = min(comp_prices)  # 980
    print(f"Стратегия 3 (равная): {target} (ожидаем 980) - {'✅' if abs(target - expected) < 0.01 else '❌'}")
    
    # Проверка ограничения min_price (цена не может быть ниже минимальной)
    high_min = 1500.0
    target = calc.calculate_target_price(comp_prices, 1, 50.0, high_min)
    print(f"С ограничением min_price=1500: {target} (ожидаем 1500) - {'✅' if target == 1500 else '❌'}")
    
    # Пустой список цен конкурентов - возвращаем min_price
    target = calc.calculate_target_price([], 1, 5.0, min_price)
    print(f"Пустой список конкурентов: {target} (ожидаем {min_price}) - {'✅' if target == min_price else '❌'}")
    print()


def test_time_schedule():
    """Тест стратегии 4 (временные интервалы)"""
    calc = PriceCalculator()
    comp_prices = [1000.0]
    min_price = 900.0
    base_strategy = 3
    base_percent = 0.0
    
    # Создаём расписание, где текущее время должно попасть в интервал
    now = datetime.now()
    # Интервал на весь день с текущим временем внутри
    schedule = [
        {
            "start": (now - timedelta(hours=1)).strftime("%H:%M"),
            "end": (now + timedelta(hours=1)).strftime("%H:%M"),
            "strategy": 1,
            "percent": 10
        }
    ]
    schedule_json = json.dumps(schedule)
    
    target = calc.calculate_target_price(comp_prices, base_strategy, base_percent, min_price, schedule_json)
    expected = max(min_price, 1000 * 0.9)  # 900
    print(f"Расписание (активный интервал, стратегия 1, 10%): {target} (ожидаем 900) - {'✅' if abs(target - expected) < 0.01 else '❌'}")
    
    # Расписание, где текущее время НЕ попадает - используется базовая стратегия
    schedule_past = [
        {
            "start": "03:00",
            "end": "04:00",
            "strategy": 1,
            "percent": 10
        }
    ]
    target = calc.calculate_target_price(comp_prices, base_strategy, base_percent, min_price, json.dumps(schedule_past))
    expected = min(comp_prices)  # базовая стратегия 3
    print(f"Расписание (неактивный интервал): {target} (ожидаем 1000) - {'✅' if abs(target - expected) < 0.01 else '❌'}")
    print()


def test_margin_calculation():
    """Тест расчёта маржинальности"""
    # Создаём mock-объект БД (не используется в calculate_margin)
    class MockDB:
        pass
    
    calc = MarginCalculator(MockDB())
    
    # Стандартные комиссии: 15% + 50 руб логистика
    price = 2000.0
    cost = 1000.0
    margin = calc.calculate_margin(price, cost)
    # Ожидаемая прибыль: 2000 - 1000 - 2000*0.15 - 50 = 2000 - 1000 - 300 - 50 = 650
    # Маржинальность: (650 / 2000) * 100 = 32.5%
    expected = 32.5
    print(f"Маржа стандартная (цена={price}, себест={cost}): {margin:.2f}% (ожидаем {expected}%) - {'✅' if abs(margin - expected) < 0.01 else '❌'}")
    
    # Проверка нулевой цены
    margin_zero = calc.calculate_margin(0, cost)
    print(f"Цена = 0: {margin_zero}% (ожидаем 0) - {'✅' if margin_zero == 0 else '❌'}")
    
    # Проверка отрицательной маржи
    margin_neg = calc.calculate_margin(1000, 1200)
    # 1000 - 1200 - 150 - 50 = -400, маржа = -40%
    expected_neg = -40.0
    print(f"Отрицательная маржа: {margin_neg:.2f}% (ожидаем {expected_neg}%) - {'✅' if abs(margin_neg - expected_neg) < 0.01 else '❌'}")
    print()


if __name__ == "__main__":
    test_price_strategies()
    test_time_schedule()
    test_margin_calculation()