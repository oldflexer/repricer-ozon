import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.entities import PricingData, StrategyInterval, PriceCalculationResult
from core.services import PriceCalculationService

def test_calculation_service():
    service = PriceCalculationService(default_coefficient=0.5)

    raw_data = {
        "product_id": 1,
        "price": {"price": 900.0, "old_price": 1200.0, "marketing_seller_price": 850.0,
                  "net_price": 700.0, "min_price": 700.0},
        "price_indexes": {
            "external_index_data": {"min_price": 950.0, "price_index_value": 0.85},
            "ozon_index_data": {"min_price": 910.0, "price_index_value": 0.88},
            "self_marketplaces_index_data": {"min_price": 920.0, "price_index_value": 0.87}
        }
    }
    pricing = PricingData.from_api_response(raw_data)

    intervals = [StrategyInterval(start="00:00", end="23:59", strategy_type=3, percent=0.0)]
    rip = 800.0

    result = service.calculate(sku="test_sku", pricing=pricing, rip=rip, intervals=intervals)

    assert isinstance(result, PriceCalculationResult)
    assert result.result_target_price > 0
    assert result.marginality is not None
    assert result.log_details["discount_coef"] > 0
    print("✅ Сервис расчёта цен работает корректно")

if __name__ == "__main__":
    test_calculation_service()