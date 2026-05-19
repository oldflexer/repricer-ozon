import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.ozon_api import OzonApiClient

@patch('infrastructure.ozon_api.requests.post')
def test_get_product_ids(mock_post):
    client = OzonApiClient()
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "items": [
            {"id": 123, "offer_id": "off1", "price": "999", "name": "Test Product", "sku": "sku1"}
        ]
    }
    result = client.get_product_ids_by_skus(["sku1"])
    assert "sku1" in result
    assert result["sku1"]["product_id"] == 123
    assert result["sku1"]["product_name"] == "Test Product"

@patch('infrastructure.ozon_api.requests.post')
def test_get_product_prices(mock_post):
    client = OzonApiClient()
    mock_post.return_value.status_code = 200
    # Реальный ответ API не содержит обёртки "result"
    mock_post.return_value.json.return_value = {
        "items": [
            {
                "product_id": 123,
                "price": {"price": 1000.0, "old_price": 1100.0, "marketing_seller_price": 950.0,
                          "net_price": 850.0, "min_price": 800.0},
                "price_indexes": {
                    "external_index_data": {"min_price": 1020.0, "price_index_value": 1.05},
                    "ozon_index_data": {"min_price": 1010.0, "price_index_value": 0.9},
                    "self_marketplaces_index_data": {"min_price": 1000.0, "price_index_value": 0.95}
                }
            }
        ],
        "cursor": "",
        "total": 1
    }
    prices = client.get_product_prices([123])
    assert len(prices) == 1
    assert prices[0].price == 1000.0
    assert prices[0].old_price == 1100.0