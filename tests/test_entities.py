import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.entities import ProductInfo, PricingData, StrategyInterval, PriceCalculationResult

def test_product_info():
    p = ProductInfo(sku="123", product_name="Test", min_price=199.0)
    assert p.sku == "123"
    assert p.min_price == 199.0

def test_pricing_data_from_api():
    raw = {
        "product_id": 111,
        "price": {"price": 1000.0, "old_price": 1200.0, "marketing_seller_price": 950.0,
                  "net_price": 850.0, "min_price": 800.0},
        "price_indexes": {
            "external_index_data": {"min_price": 1050.0, "price_index_value": 0.85},
            "ozon_index_data": {"min_price": 1020.0, "price_index_value": 0.88},
            "self_marketplaces_index_data": {"min_price": 1010.0, "price_index_value": 0.87}
        }
    }
    p = PricingData.from_api_response(raw)
    assert p.product_id == 111
    assert p.marketing_seller_price == 950.0
    assert p.external_index_data_price == 1050.0