import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.use_cases import RepricingUseCase
from core.entities import ProductInfo, PricingData, StrategyInterval
from core.enums import StrategyType


@pytest.mark.asyncio
async def test_execute_dry_run():
    repo = MagicMock()
    api = AsyncMock()
    notifier = MagicMock()
    loader = MagicMock()

    product = ProductInfo(sku="123", min_price=200.0, cost_price=150.0)
    # load() returns tuple (products, warnings)
    loader.load.return_value = ([product], [])

    api.get_product_ids_by_skus.return_value = {
        "123": {"product_id": 1, "offer_id": "off1", "product_name": "Test Product"}
    }

    pricing = PricingData(
        product_id=1,
        price=1000.0,
        old_price=1200.0,
        marketing_seller_price=950.0,
        net_price=700.0,
        min_price=800.0,
        external_index_data_price=950.0,
        external_index_data_index=0.85,
        ozon_index_data_price=910.0,
        ozon_index_data_index=0.88,
        self_marketplaces_index_data_price=920.0,
        self_marketplaces_index_data_index=0.87
    )
    api.get_product_prices.return_value = [pricing]

    repo.get_strategies.return_value = [StrategyInterval(start="00:00", end="23:59", strategy_type=StrategyType.EQUAL, percent=0.0)]

    repo.upsert_product.return_value = True
    repo.set_strategies.return_value = True
    repo.save_price_history.return_value = True
    repo.save_marginality.return_value = True
    repo.get_average_marginality.return_value = None
    loader.update_product_in_file.return_value = True

    use_case = RepricingUseCase(repo, api, notifier, loader)
    stats = await use_case.execute(dry_run=True)

    assert stats["products_loaded"] == 1
    assert stats["prices_updated"] == 1
    assert stats["errors"] == []
    api.update_prices.assert_not_called()
    loader.update_product_in_file.assert_called()
    notifier.send_detailed_report.assert_called_once()


@pytest.mark.asyncio
async def test_execute_without_products():
    repo = MagicMock()
    api = AsyncMock()
    notifier = MagicMock()
    loader = MagicMock()
    # load() returns tuple (products, warnings)
    loader.load.return_value = ([], [])

    use_case = RepricingUseCase(repo, api, notifier, loader)
    stats = await use_case.execute(dry_run=False)

    assert stats["products_loaded"] == 0
    assert stats["prices_updated"] == 0
    assert stats["errors"] == []
    api.update_prices.assert_not_called()
    notifier.send_detailed_report.assert_called_once_with([], [], dry_run=False)