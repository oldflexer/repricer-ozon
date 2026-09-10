import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.ozon_api import OzonApiClient


@pytest.mark.asyncio
async def test_get_product_ids():
    client = OzonApiClient()
    mock_response = {
        "items": [
            {"id": 123, "offer_id": "off1", "price": "999", "name": "Test Product", "sku": "sku1"}
        ]
    }
    with patch.object(client, "_post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await client.get_product_ids_by_skus(["sku1"])
        assert "sku1" in result
        assert result["sku1"]["product_id"] == 123
        assert result["sku1"]["product_name"] == "Test Product"
    await client.close()


@pytest.mark.asyncio
async def test_get_product_prices():
    client = OzonApiClient()
    mock_response = {
        "items": [
            {
                "product_id": 123,
                "price": {
                    "price": 1000.0,
                    "old_price": 1100.0,
                    "marketing_seller_price": 950.0,
                    "net_price": 850.0,
                    "min_price": 800.0,
                },
                "price_indexes": {
                    "external_index_data": {"min_price": 1020.0, "price_index_value": 1.05},
                    "ozon_index_data": {"min_price": 1010.0, "price_index_value": 0.9},
                    "self_marketplaces_index_data": {
                        "min_price": 1000.0,
                        "price_index_value": 0.95,
                    },
                },
            }
        ],
        "cursor": "",
        "total": 1,
    }
    with patch.object(client, "_post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        prices = await client.get_product_prices([123])
        assert len(prices) == 1
        assert prices[0].price == 1000.0
        assert prices[0].old_price == 1100.0
    await client.close()
